"""Predictive Nodal Drift Radar analytics service."""
import hashlib
import json
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.models.exceptions import ExceptionRecord
from backend.models.cluster import ExceptionCluster
from backend.models.audit import AuditEvent
from backend.models.drift_prediction import DriftPrediction
from backend.models.enums import ExceptionSeverity

DRIFT_SCORING_VERSION = "v1.0.0"


def utc_now():
    return datetime.now(timezone.utc)


class PredictiveDriftService:
    """Deterministic analytics engine for detecting leading early-warning operational drift."""

    def evaluate_drift(
        self,
        session: Session,
        nodal_account_id: str = "nodal_escrow_main",
        horizon: str = "NEXT_SETTLEMENT_CYCLE",
        persist: bool = True,
        log_audit: bool = True,
        actor_id: str = "drift_radar_engine",
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculates deterministic operational drift prediction comparing temporal windows.

        Guarantees:
        - 100% deterministic mathematical formulas without LLM calculation.
        - Zero synthetic future incidents fabricated.
        - Explicit INSUFFICIENT_DATA state when temporal evidence is sparse.
        - Idempotent persistence in drift_predictions table.
        - Complete provenance tracking for seeded vs live-injected records.
        """
        # 1. Query all persisted exception records
        exceptions = session.scalars(
            select(ExceptionRecord).order_by(ExceptionRecord.detected_at.asc())
        ).all()

        # Handle Insufficient Data condition
        if len(exceptions) < 2:
            return self._build_insufficient_data_response(
                nodal_account_id=nodal_account_id,
                horizon=horizon,
                reason="Fewer than 2 temporal exception observations available in operational database.",
                session=session,
                persist=persist,
                log_audit=log_audit,
                actor_id=actor_id,
                request_id=request_id,
            )

        t_min = exceptions[0].detected_at
        t_max = exceptions[-1].detected_at

        # Check temporal duration: if all exceptions occurred at the exact same sub-second
        time_span = (t_max - t_min).total_seconds()
        if time_span < 1.0:
            # If records were batch-created at identical timestamps, split deterministically by sequence index
            midpoint_idx = len(exceptions) // 2
            baseline_exceptions = exceptions[:midpoint_idx]
            current_exceptions = exceptions[midpoint_idx:]
            t_mid = t_min
        else:
            t_mid = t_min + (t_max - t_min) / 2
            baseline_exceptions = [e for e in exceptions if e.detected_at <= t_mid]
            current_exceptions = [e for e in exceptions if e.detected_at > t_mid]

        if not baseline_exceptions or not current_exceptions:
            # Fallback to index-based partition to guarantee valid comparison windows
            midpoint_idx = max(1, len(exceptions) // 2)
            baseline_exceptions = exceptions[:midpoint_idx]
            current_exceptions = exceptions[midpoint_idx:]
            t_mid = baseline_exceptions[-1].detected_at

        # 2. Extract baseline vs current metrics
        baseline_exc_count = len(baseline_exceptions)
        current_exc_count = len(current_exceptions)

        baseline_exposure = sum(e.exposure or 0 for e in baseline_exceptions)
        current_exposure = sum(e.exposure or 0 for e in current_exceptions)

        baseline_high_risk = sum(
            1 for e in baseline_exceptions
            if e.severity in (ExceptionSeverity.HIGH.value, ExceptionSeverity.CRITICAL.value)
        )
        current_high_risk = sum(
            1 for e in current_exceptions
            if e.severity in (ExceptionSeverity.HIGH.value, ExceptionSeverity.CRITICAL.value)
        )

        # Control/SLA failure indicators
        baseline_control_failures = sum(
            1 for e in baseline_exceptions
            if "SLA" in (e.exception_type or "") or "BALANCE" in (e.exception_type or "") or "VARIANCE" in (e.exception_type or "")
        )
        current_control_failures = sum(
            1 for e in current_exceptions
            if "SLA" in (e.exception_type or "") or "BALANCE" in (e.exception_type or "") or "VARIANCE" in (e.exception_type or "")
        )

        # Recurring pattern cluster membership
        clusters = session.scalars(select(ExceptionCluster).where(ExceptionCluster.exception_count >= 2)).all()
        clustered_ids = set()
        for cl in clusters:
            if cl.exception_ids:
                try:
                    c_ids = json.loads(cl.exception_ids)
                    if isinstance(c_ids, list):
                        clustered_ids.update(c_ids)
                except Exception:
                    pass

        baseline_cluster_activity = sum(1 for e in baseline_exceptions if e.exception_id in clustered_ids)
        current_cluster_activity = sum(1 for e in current_exceptions if e.exception_id in clustered_ids)

        # 3. Calculate 5 Leading Indicator Signals (Total Max = 100 pts)
        signals: List[Dict[str, Any]] = []

        # Signal 1: Exception Frequency Drift (Max 25 pts)
        delta_exc = current_exc_count - baseline_exc_count
        if baseline_exc_count > 0:
            exc_growth = delta_exc / baseline_exc_count
        else:
            exc_growth = 1.0 if current_exc_count > 0 else 0.0

        if delta_exc > 0:
            s1_contrib = min(25, int(exc_growth * 15) if baseline_exc_count > 0 else min(25, delta_exc * 3))
            s1_contrib = max(5, s1_contrib)
        else:
            s1_contrib = 0

        signals.append({
            "signal": "EXCEPTION_FREQUENCY_DRIFT",
            "name": "Exception Frequency Acceleration",
            "baseline": baseline_exc_count,
            "current": current_exc_count,
            "delta": delta_exc,
            "growth_rate": round(exc_growth, 4),
            "direction": "NEGATIVE" if delta_exc > 0 else "POSITIVE" if delta_exc < 0 else "NEUTRAL",
            "contribution": s1_contrib,
            "explanation": (
                f"Exception volume changed from {baseline_exc_count} to {current_exc_count} "
                f"({'+' if delta_exc > 0 else ''}{delta_exc} cases, {exc_growth * 100:+.1f}%)."
            ),
            "evidence_ids": [e.exception_id for e in current_exceptions[:5]],
        })

        # Signal 2: High-Risk Severity Concentration (Max 25 pts)
        delta_hr = current_high_risk - baseline_high_risk
        if delta_hr > 0:
            s2_contrib = min(25, delta_hr * 5)
        else:
            s2_contrib = 0

        signals.append({
            "signal": "HIGH_RISK_SEVERITY_DRIFT",
            "name": "Severe & Critical Anomaly Influx",
            "baseline": baseline_high_risk,
            "current": current_high_risk,
            "delta": delta_hr,
            "direction": "NEGATIVE" if delta_hr > 0 else "POSITIVE" if delta_hr < 0 else "NEUTRAL",
            "contribution": s2_contrib,
            "explanation": (
                f"High and critical severity exceptions shifted from {baseline_high_risk} to {current_high_risk} "
                f"({'+' if delta_hr > 0 else ''}{delta_hr} cases)."
            ),
            "evidence_ids": [
                e.exception_id for e in current_exceptions
                if e.severity in (ExceptionSeverity.HIGH.value, ExceptionSeverity.CRITICAL.value)
            ][:5],
        })

        # Signal 3: Financial Exposure Growth (Max 20 pts)
        delta_exp = current_exposure - baseline_exposure
        if delta_exp > 0:
            exp_ratio = delta_exp / max(baseline_exposure, 100000)
            s3_contrib = min(20, int(exp_ratio * 10) + min(10, int(delta_exp / 1000000)))
            s3_contrib = max(4, s3_contrib)
        else:
            s3_contrib = 0

        signals.append({
            "signal": "FINANCIAL_EXPOSURE_GROWTH",
            "name": "Financial Exposure Trajectory",
            "baseline": baseline_exposure,
            "current": current_exposure,
            "delta": delta_exp,
            "direction": "NEGATIVE" if delta_exp > 0 else "POSITIVE" if delta_exp < 0 else "NEUTRAL",
            "contribution": s3_contrib,
            "explanation": (
                f"Exposure shifted from ₹{baseline_exposure / 100:,.2f} to ₹{current_exposure / 100:,.2f} "
                f"({'+' if delta_exp > 0 else ''}₹{delta_exp / 100:,.2f})."
            ),
            "evidence_ids": [e.exception_id for e in current_exceptions if (e.exposure or 0) > 0][:5],
        })

        # Signal 4: Control Findings Deterioration (Max 15 pts)
        delta_ctrl = current_control_failures - baseline_control_failures
        if delta_ctrl > 0:
            s4_contrib = min(15, delta_ctrl * 5)
        else:
            s4_contrib = 0

        signals.append({
            "signal": "CONTROL_FINDINGS_DETERIORATION",
            "name": "SLA & Reconciliation Control Failures",
            "baseline": baseline_control_failures,
            "current": current_control_failures,
            "delta": delta_ctrl,
            "direction": "NEGATIVE" if delta_ctrl > 0 else "POSITIVE" if delta_ctrl < 0 else "NEUTRAL",
            "contribution": s4_contrib,
            "explanation": (
                f"Control failures (SLA breaches & balance variances) shifted from {baseline_control_failures} "
                f"to {current_control_failures} ({'+' if delta_ctrl > 0 else ''}{delta_ctrl} events)."
            ),
            "evidence_ids": [
                e.exception_id for e in current_exceptions
                if "SLA" in (e.exception_type or "") or "BALANCE" in (e.exception_type or "") or "VARIANCE" in (e.exception_type or "")
            ][:5],
        })

        # Signal 5: Recurring Pattern Concentration (Max 15 pts)
        delta_pat = current_cluster_activity - baseline_cluster_activity
        if delta_pat > 0:
            s5_contrib = min(15, delta_pat * 5)
        else:
            s5_contrib = 0

        signals.append({
            "signal": "RECURRING_PATTERN_CONCENTRATION",
            "name": "Systemic Pattern Miner Clusters",
            "baseline": baseline_cluster_activity,
            "current": current_cluster_activity,
            "delta": delta_pat,
            "direction": "NEGATIVE" if delta_pat > 0 else "POSITIVE" if delta_pat < 0 else "NEUTRAL",
            "contribution": s5_contrib,
            "explanation": (
                f"Cases linked to systemic recurring clusters shifted from {baseline_cluster_activity} "
                f"to {current_cluster_activity} ({'+' if delta_pat > 0 else ''}{delta_pat} cases)."
            ),
            "evidence_ids": [e.exception_id for e in current_exceptions if e.exception_id in clustered_ids][:5],
        })

        # 4. Total Bounded Drift Score
        raw_score = sum(s["contribution"] for s in signals)
        drift_score = min(100, max(0, raw_score))

        # 5. Risk Band
        if drift_score >= 75:
            risk_band = "HIGH_DRIFT"
        elif drift_score >= 50:
            risk_band = "ELEVATED"
        elif drift_score >= 25:
            risk_band = "WATCH"
        else:
            risk_band = "STABLE"

        # 6. Direction
        if drift_score >= 25 and any(s["contribution"] > 0 for s in signals):
            direction = "DETERIORATING"
        elif all(s["delta"] <= 0 for s in signals) and any(s["delta"] < 0 for s in signals):
            direction = "IMPROVING"
        else:
            direction = "STABLE"

        # 7. Confidence (based on sample size & evidence depth)
        total_sample = baseline_exc_count + current_exc_count
        if total_sample < 4:
            confidence = "LOW"
        elif total_sample < 16:
            confidence = "MEDIUM"
        else:
            confidence = "HIGH"

        # 8. Provenance Metadata
        seeded_count = sum(1 for e in exceptions if e.source_flag == "seeded")
        live_injected_count = sum(1 for e in exceptions if e.source_flag == "live-injected")

        observation_window = {
            "baseline_start": t_min.isoformat(),
            "baseline_end": t_mid.isoformat(),
            "current_start": t_mid.isoformat(),
            "current_end": t_max.isoformat(),
        }

        baseline_metrics = {
            "exception_count": baseline_exc_count,
            "exposure_minor_units": baseline_exposure,
            "high_risk_count": baseline_high_risk,
            "control_failures": baseline_control_failures,
            "cluster_activity": baseline_cluster_activity,
        }

        current_metrics = {
            "exception_count": current_exc_count,
            "exposure_minor_units": current_exposure,
            "high_risk_count": current_high_risk,
            "control_failures": current_control_failures,
            "cluster_activity": current_cluster_activity,
        }

        delta_metrics = {
            "delta_exceptions": delta_exc,
            "delta_exposure_minor_units": delta_exp,
            "delta_high_risk": delta_hr,
            "delta_control_failures": delta_ctrl,
            "delta_cluster_activity": delta_pat,
            "exception_growth_rate": round(exc_growth, 4),
        }

        # Deterministic Prediction ID based on account and window bounds
        window_hash = hashlib.sha256(f"{nodal_account_id}_{t_min.isoformat()}_{t_max.isoformat()}".encode()).hexdigest()[:16]
        prediction_id = f"pred_drift_{window_hash}"

        all_evidence_ids = list(dict.fromkeys([
            eid for s in signals for eid in s.get("evidence_ids", [])
        ]))

        source_metadata = {
            "seeded_count": seeded_count,
            "live_injected_count": live_injected_count,
            "total_observations": total_sample,
            "synthetic_included": live_injected_count > 0,
        }

        # 9. Persistence (Idempotent Upsert)
        if persist:
            existing = session.scalar(
                select(DriftPrediction).where(DriftPrediction.prediction_id == prediction_id)
            )
            if existing:
                existing.drift_score = drift_score
                existing.risk_band = risk_band
                existing.direction = direction
                existing.confidence = confidence
                existing.contributing_signals = json.dumps(signals)
                existing.baseline_metrics = json.dumps(baseline_metrics)
                existing.current_metrics = json.dumps(current_metrics)
                existing.delta_metrics = json.dumps(delta_metrics)
                existing.evidence_ids = json.dumps(all_evidence_ids)
                existing.source_metadata = json.dumps(source_metadata)
                existing.updated_at = utc_now()
            else:
                pred = DriftPrediction(
                    prediction_id=prediction_id,
                    nodal_account_id=nodal_account_id,
                    prediction_timestamp=utc_now(),
                    observation_window=json.dumps(observation_window),
                    horizon=horizon,
                    drift_score=drift_score,
                    risk_band=risk_band,
                    direction=direction,
                    confidence=confidence,
                    predicted_dimension="OPERATIONAL_HEALTH",
                    contributing_signals=json.dumps(signals),
                    baseline_metrics=json.dumps(baseline_metrics),
                    current_metrics=json.dumps(current_metrics),
                    delta_metrics=json.dumps(delta_metrics),
                    evidence_ids=json.dumps(all_evidence_ids),
                    source_metadata=json.dumps(source_metadata),
                    scoring_version=DRIFT_SCORING_VERSION,
                )
                session.add(pred)

        # 10. Audit Logging (Append-only)
        if log_audit:
            audit = AuditEvent(
                audit_event_id=f"audit_drift_{uuid.uuid4().hex[:16]}",
                event_type="DRIFT_PREDICTION_GENERATED",
                actor_type="SYSTEM",
                actor_id=actor_id,
                event_summary=(
                    f"Drift prediction generated for {nodal_account_id}: "
                    f"Score {drift_score}/100 ({risk_band}, {direction})"
                ),
                event_payload=json.dumps({
                    "request_id": request_id,
                    "prediction_id": prediction_id,
                    "nodal_account_id": nodal_account_id,
                    "drift_score": drift_score,
                    "risk_band": risk_band,
                    "direction": direction,
                    "confidence": confidence,
                    "scoring_version": DRIFT_SCORING_VERSION,
                }),
            )
            session.add(audit)

        if persist or log_audit:
            session.commit()

        return {
            "prediction_id": prediction_id,
            "nodal_account_id": nodal_account_id,
            "prediction_timestamp": utc_now().isoformat(),
            "observation_window": observation_window,
            "horizon": horizon,
            "drift_score": drift_score,
            "risk_band": risk_band,
            "direction": direction,
            "confidence": confidence,
            "predicted_dimension": "OPERATIONAL_HEALTH",
            "signals": signals,
            "baseline_metrics": baseline_metrics,
            "current_metrics": current_metrics,
            "delta_metrics": delta_metrics,
            "evidence_ids": all_evidence_ids,
            "source": source_metadata,
            "methodology_version": DRIFT_SCORING_VERSION,
            "disclaimer": (
                "PREDICTIVE / EARLY-WARNING: Indicates operational drift risk based on temporal leading signals. "
                "Does not constitute a guaranteed future failure or automated policy mutation."
            ),
        }

    def _build_insufficient_data_response(
        self,
        nodal_account_id: str,
        horizon: str,
        reason: str,
        session: Session,
        persist: bool,
        log_audit: bool,
        actor_id: str,
        request_id: Optional[str],
    ) -> Dict[str, Any]:
        """Builds explicit insufficient-data response rather than generating misleading zeros."""
        now_str = utc_now().isoformat()
        pred_id = f"pred_drift_insufficient_{uuid.uuid4().hex[:8]}"

        res = {
            "prediction_id": pred_id,
            "nodal_account_id": nodal_account_id,
            "prediction_timestamp": now_str,
            "observation_window": {
                "baseline_start": None,
                "baseline_end": None,
                "current_start": None,
                "current_end": None,
            },
            "horizon": horizon,
            "drift_score": 0,
            "risk_band": "STABLE",
            "direction": "INSUFFICIENT_DATA",
            "confidence": "LOW",
            "predicted_dimension": "OPERATIONAL_HEALTH",
            "signals": [],
            "baseline_metrics": {},
            "current_metrics": {},
            "delta_metrics": {},
            "evidence_ids": [],
            "source": {
                "seeded_count": 0,
                "live_injected_count": 0,
                "total_observations": 0,
                "synthetic_included": False,
            },
            "methodology_version": DRIFT_SCORING_VERSION,
            "disclaimer": (
                f"INSUFFICIENT DATA: {reason} "
                "Predictive drift assessment requires temporal exception history."
            ),
        }

        if log_audit:
            audit = AuditEvent(
                audit_event_id=f"audit_drift_{uuid.uuid4().hex[:16]}",
                event_type="DRIFT_PREDICTION_GENERATED",
                actor_type="SYSTEM",
                actor_id=actor_id,
                event_summary=f"Drift assessment for {nodal_account_id}: INSUFFICIENT_DATA",
                event_payload=json.dumps({
                    "request_id": request_id,
                    "nodal_account_id": nodal_account_id,
                    "direction": "INSUFFICIENT_DATA",
                    "reason": reason,
                }),
            )
            session.add(audit)
            session.commit()

        return res
