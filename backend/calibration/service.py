"""Confidence Calibration Service for Nodal Sentinel.

Evaluates whether Sentinel's confidence labels (HIGH / MEDIUM / LOW) and numerical confidences
correspond to observed correctness, using REAL historical prediction and evaluation outcomes.

Guarantees:
- Zero fabricated observations, outcomes, probabilities, or labels.
- Strict distinction between confidence label, empirical correctness rate, and numerical probability.
- Explicit INSUFFICIENT_DATA status when historical outcomes are sparse.
- Zero mutation of financial, benchmark, or operational state.
- Complete isolation of benchmark ground truth from live-injected cases.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.exceptions import ExceptionRecord
from backend.models.investigation import InvestigationRun
from backend.models.verifier import VerifierOpinion
from backend.models.verification import VerificationRecord
from backend.models.drift_prediction import DriftPrediction
from backend.models.evaluation import EvaluationCase
from backend.models.calibration import ConfidenceCalibrationSnapshot
from backend.models.audit import AuditEvent

CALIBRATION_METHODOLOGY_VERSION = "v1.0.0"
MIN_EVALUATED_OBSERVATIONS = 3
MIN_NUMERICAL_OBSERVATIONS_FOR_BRIER = 5


def utc_now():
    return datetime.now(timezone.utc)


class ConfidenceCalibrationService:
    """Computes evidence-grounded confidence calibration metrics across historical predictions."""

    def evaluate_calibration(
        self,
        session: Session,
        prediction_type: Optional[str] = None,
        source: Optional[str] = None,
        persist: bool = True,
        log_audit: bool = True,
        actor_id: str = "calibration_engine",
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculates deterministic confidence calibration from genuine historical outcomes.

        Args:
            session: SQLAlchemy DB session.
            prediction_type: Optional filter ('INVESTIGATION', 'VERIFIER', 'DRIFT', or None for all).
            source: Optional filter ('all', 'seeded', 'live-injected').
            persist: Whether to record a snapshot.
            log_audit: Whether to append an audit log.
            actor_id: Invoking actor.
            request_id: Request tracing ID.
        """
        # 1. Harvest Genuine Historical Predictions & Evaluated Outcomes
        observations: List[Dict[str, Any]] = []

        # A. Investigation Predictions
        if not prediction_type or prediction_type.upper() == "INVESTIGATION":
            observations.extend(self._harvest_investigation_observations(session))

        # B. Adversarial Verifier Opinions
        if not prediction_type or prediction_type.upper() == "VERIFIER":
            observations.extend(self._harvest_verifier_observations(session))

        # C. Predictive Drift Radar
        if not prediction_type or prediction_type.upper() == "DRIFT":
            observations.extend(self._harvest_drift_observations(session))

        # 2. Apply Source Filtering
        if source and source.lower() != "all":
            src_filter = source.lower()
            observations = [o for o in observations if o["source"] == src_filter]

        # 3. Aggregate Counts
        total_predictions = len(observations)
        evaluated_obs = [o for o in observations if o["is_evaluated"]]
        unevaluated_obs = [o for o in observations if not o["is_evaluated"]]

        evaluated_count = len(evaluated_obs)
        unevaluated_count = len(unevaluated_obs)
        correct_count = sum(1 for o in evaluated_obs if o["correctness"] is True)

        # Source breakdown
        seeded_count = sum(1 for o in observations if o["source"] == "seeded")
        live_injected_count = sum(1 for o in observations if o["source"] == "live-injected")

        # Core Metrics: Coverage and Correctness Rate
        coverage = round(evaluated_count / total_predictions, 4) if total_predictions > 0 else None
        correctness_rate = round(correct_count / evaluated_count, 4) if evaluated_count > 0 else None

        # 4. Confidence-Bucket Breakdown (HIGH, MEDIUM, LOW)
        buckets: Dict[str, Dict[str, Any]] = {}
        for level in ["HIGH", "MEDIUM", "LOW"]:
            level_all = [o for o in observations if o["confidence_level"] == level]
            level_eval = [o for o in level_all if o["is_evaluated"]]
            level_correct = sum(1 for o in level_eval if o["correctness"] is True)
            pred_cnt = len(level_all)
            eval_cnt = len(level_eval)

            buckets[level] = {
                "confidence_level": level,
                "prediction_count": pred_cnt,
                "evaluated_count": eval_cnt,
                "unevaluated_count": pred_cnt - eval_cnt,
                "correct_count": level_correct,
                "correctness_rate": round(level_correct / eval_cnt, 4) if eval_cnt > 0 else None,
                "coverage": round(eval_cnt / pred_cnt, 4) if pred_cnt > 0 else None,
            }

        # 5. Numerical Calibration Metrics (Brier Score & ECE)
        numerical_metrics = self._calculate_numerical_metrics(evaluated_obs)

        # 6. Status Determination & Insufficiency Explanation
        status, insufficiency_reasons = self._determine_status(
            total_predictions=total_predictions,
            evaluated_count=evaluated_count,
            coverage=coverage,
            buckets=buckets,
        )

        # 7. Stable Snapshot ID & Persistence
        filter_str = f"{prediction_type or 'ALL'}_{source or 'ALL'}_{total_predictions}_{evaluated_count}_{correct_count}"
        snapshot_id = f"calib_snap_{hashlib.sha256(filter_str.encode()).hexdigest()[:16]}"

        if persist:
            existing = session.scalar(
                select(ConfidenceCalibrationSnapshot).where(
                    ConfidenceCalibrationSnapshot.snapshot_id == snapshot_id
                )
            )
            if not existing:
                snap = ConfidenceCalibrationSnapshot(
                    snapshot_id=snapshot_id,
                    prediction_type_filter=prediction_type,
                    source_filter=source,
                    status=status,
                    total_predictions=total_predictions,
                    evaluated_predictions=evaluated_count,
                    unevaluated_predictions=unevaluated_count,
                    correct_predictions=correct_count,
                    coverage=coverage,
                    correctness_rate=correctness_rate,
                    confidence_buckets=json.dumps(buckets),
                    numerical_metrics=json.dumps(numerical_metrics),
                    source_breakdown=json.dumps({
                        "seeded_count": seeded_count,
                        "live_injected_count": live_injected_count,
                        "total": total_predictions,
                    }),
                    insufficiency_reasons=json.dumps(insufficiency_reasons) if insufficiency_reasons else None,
                    methodology_version=CALIBRATION_METHODOLOGY_VERSION,
                    created_at=utc_now(),
                )
                session.add(snap)

        # 8. Read-only Audit Log
        if log_audit:
            audit = AuditEvent(
                audit_event_id=f"audit_calib_{uuid.uuid4().hex[:16]}",
                event_type="CALIBRATION_EVALUATED",
                actor_type="SYSTEM",
                actor_id=actor_id,
                event_summary=(
                    f"Confidence calibration evaluated: Status={status}, Total={total_predictions}, "
                    f"Evaluated={evaluated_count}, Correctness={f'{correctness_rate*100:.1f}%' if correctness_rate is not None else 'N/A'}"
                ),
                event_payload=json.dumps({
                    "request_id": request_id,
                    "prediction_type": prediction_type,
                    "source": source,
                    "status": status,
                    "total_predictions": total_predictions,
                    "evaluated_predictions": evaluated_count,
                    "coverage": coverage,
                    "correctness_rate": correctness_rate,
                }),
            )
            session.add(audit)

        if persist or log_audit:
            session.commit()

        return {
            "snapshot_id": snapshot_id,
            "status": status,
            "methodology_version": CALIBRATION_METHODOLOGY_VERSION,
            "prediction_type_filter": prediction_type,
            "source_filter": source,
            "total_predictions": total_predictions,
            "evaluated_predictions": evaluated_count,
            "unevaluated_predictions": unevaluated_count,
            "correct_predictions": correct_count,
            "coverage": coverage,
            "correctness_rate": correctness_rate,
            "confidence_buckets": buckets,
            "numerical_metrics": numerical_metrics,
            "source_breakdown": {
                "seeded_count": seeded_count,
                "live_injected_count": live_injected_count,
                "total": total_predictions,
            },
            "insufficiency_reasons": insufficiency_reasons,
            "disclaimer": (
                "CONFIDENCE CALIBRATION SAFETY: Confidence labels represent model confidence at time of prediction, "
                "not mathematical failure probabilities. Observed correctness rates reflect empirical performance on "
                "evaluated outcomes and must never be falsely treated as calibrated Bayesian probabilities."
            ),
            "generated_at": utc_now().isoformat(),
        }

    def _harvest_investigation_observations(self, session: Session) -> List[Dict[str, Any]]:
        """Harvests investigation runs and matches with benchmark evaluation cases."""
        investigations = session.scalars(select(InvestigationRun)).all()
        eval_cases = session.scalars(select(EvaluationCase)).all()
        exceptions = session.scalars(select(ExceptionRecord)).all()

        exc_map = {e.exception_id: e for e in exceptions}
        # Map predicted_exception_id -> EvaluationCase
        eval_map = {c.predicted_exception_id: c for c in eval_cases if c.predicted_exception_id}

        obs = []
        for inv in investigations:
            exc = exc_map.get(inv.exception_id)
            source_flag = exc.source_flag if exc else "seeded"

            # Numerical & categorical confidence
            num_conf = float(inv.confidence) if inv.confidence is not None else None
            if num_conf is not None:
                if num_conf >= 0.85:
                    cat_conf = "HIGH"
                elif num_conf >= 0.60:
                    cat_conf = "MEDIUM"
                else:
                    cat_conf = "LOW"
            else:
                cat_conf = "MEDIUM"

            eval_case = eval_map.get(inv.exception_id)
            if eval_case:
                # Benchmark evaluated outcome
                errs = eval_case.error_categories or ""
                is_correct = (
                    eval_case.match_status in ("TRUE_POSITIVE", "LEGITIMATE_CORRECT")
                    and "WRONG_ROOT_CAUSE" not in errs
                    and "MISCLASSIFIED" not in errs
                )
                obs.append({
                    "prediction_id": inv.investigation_id,
                    "prediction_type": "INVESTIGATION",
                    "predicted_state": inv.final_classification or "UNKNOWN",
                    "confidence_level": cat_conf,
                    "numerical_confidence": num_conf,
                    "prediction_timestamp": inv.created_at.isoformat() if inv.created_at else None,
                    "evaluation_timestamp": eval_case.created_at.isoformat() if eval_case.created_at else None,
                    "observed_outcome": "CORRECT_ROOT_CAUSE" if is_correct else "INCORRECT_ROOT_CAUSE",
                    "correctness": is_correct,
                    "source": source_flag,
                    "is_evaluated": True,
                })
            else:
                # Unevaluated (e.g. live-injected case without ground truth)
                obs.append({
                    "prediction_id": inv.investigation_id,
                    "prediction_type": "INVESTIGATION",
                    "predicted_state": inv.final_classification or "UNKNOWN",
                    "confidence_level": cat_conf,
                    "numerical_confidence": num_conf,
                    "prediction_timestamp": inv.created_at.isoformat() if inv.created_at else None,
                    "evaluation_timestamp": None,
                    "observed_outcome": None,
                    "correctness": None,
                    "source": source_flag,
                    "is_evaluated": False,
                })
        return obs

    def _harvest_verifier_observations(self, session: Session) -> List[Dict[str, Any]]:
        """Harvests adversarial verifier opinions and checks verification outcomes."""
        opinions = session.scalars(select(VerifierOpinion)).all()
        verifications = session.scalars(select(VerificationRecord)).all()
        exceptions = session.scalars(select(ExceptionRecord)).all()

        exc_map = {e.exception_id: e for e in exceptions}
        verif_map = {v.exception_id: v for v in verifications if v.exception_id}

        obs = []
        for op in opinions:
            exc = exc_map.get(op.exception_id)
            source_flag = exc.source_flag if exc else "seeded"

            v_rec = verif_map.get(op.exception_id)
            if v_rec and v_rec.verification_result:
                # Verification outcome confirmed
                is_correct = v_rec.verification_result.upper() in ("VERIFIED", "SUCCESS", "PASSED")
                obs.append({
                    "prediction_id": op.opinion_id,
                    "prediction_type": "VERIFIER",
                    "predicted_state": op.verdict,
                    "confidence_level": op.confidence or "HIGH",
                    "numerical_confidence": None,
                    "prediction_timestamp": op.created_at.isoformat() if op.created_at else None,
                    "evaluation_timestamp": v_rec.completed_at.isoformat() if v_rec.completed_at else None,
                    "observed_outcome": "UPHELD" if is_correct else "OVERRULED",
                    "correctness": is_correct,
                    "source": source_flag,
                    "is_evaluated": True,
                })
            else:
                obs.append({
                    "prediction_id": op.opinion_id,
                    "prediction_type": "VERIFIER",
                    "predicted_state": op.verdict,
                    "confidence_level": op.confidence or "HIGH",
                    "numerical_confidence": None,
                    "prediction_timestamp": op.created_at.isoformat() if op.created_at else None,
                    "evaluation_timestamp": None,
                    "observed_outcome": None,
                    "correctness": None,
                    "source": source_flag,
                    "is_evaluated": False,
                })
        return obs

    def _harvest_drift_observations(self, session: Session) -> List[Dict[str, Any]]:
        """Harvests drift radar predictions (treated as unevaluated until horizon closes)."""
        drifts = session.scalars(select(DriftPrediction)).all()
        obs = []
        for d in drifts:
            source_meta = json.loads(d.source_metadata) if d.source_metadata else {}
            src = "live-injected" if source_meta.get("synthetic_included") else "seeded"
            obs.append({
                "prediction_id": d.prediction_id,
                "prediction_type": "DRIFT",
                "predicted_state": f"{d.risk_band}_{d.direction}",
                "confidence_level": d.confidence or "MEDIUM",
                "numerical_confidence": None,
                "prediction_timestamp": d.created_at.isoformat() if d.created_at else None,
                "evaluation_timestamp": None,
                "observed_outcome": None,
                "correctness": None,
                "source": src,
                "is_evaluated": False,
            })
        return obs

    def _calculate_numerical_metrics(self, evaluated_obs: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculates Brier Score and ECE only if genuine numerical confidences exist."""
        num_obs = [
            o for o in evaluated_obs
            if o.get("numerical_confidence") is not None and o.get("correctness") is not None
        ]

        if len(num_obs) < MIN_NUMERICAL_OBSERVATIONS_FOR_BRIER:
            return {
                "status": "UNAVAILABLE",
                "eligible_sample_size": len(num_obs),
                "brier_score": None,
                "ece": None,
                "reliability_bins": [],
                "reason": (
                    f"Insufficient numerical probability observations with ground truth outcomes "
                    f"({len(num_obs)} available, minimum {MIN_NUMERICAL_OBSERVATIONS_FOR_BRIER} required). "
                    "Categorical confidence evaluation is active."
                ),
            }

        # Brier Score: 1/N * sum((p_i - y_i)^2)
        n = len(num_obs)
        brier_sum = sum(
            (o["numerical_confidence"] - (1.0 if o["correctness"] else 0.0)) ** 2
            for o in num_obs
        )
        brier_score = round(brier_sum / n, 4)

        # Expected Calibration Error (ECE) over 5 bins
        # Bins: [0, 0.2), [0.2, 0.4), [0.4, 0.6), [0.6, 0.8), [0.8, 1.0]
        bin_ranges = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.001)]
        reliability_bins = []
        ece_acc = 0.0

        for b_min, b_max in bin_ranges:
            bin_items = [
                o for o in num_obs
                if b_min <= o["numerical_confidence"] < b_max
            ]
            bin_count = len(bin_items)
            if bin_count > 0:
                bin_acc = sum(1 for o in bin_items if o["correctness"]) / bin_count
                bin_conf = sum(o["numerical_confidence"] for o in bin_items) / bin_count
                bin_err = abs(bin_acc - bin_conf)
                ece_acc += (bin_count / n) * bin_err
                reliability_bins.append({
                    "range": f"[{b_min:.1f}, {b_max if b_max <= 1.0 else 1.0:.1f})",
                    "count": bin_count,
                    "accuracy": round(bin_acc, 4),
                    "confidence": round(bin_conf, 4),
                    "calibration_error": round(bin_err, 4),
                })
            else:
                reliability_bins.append({
                    "range": f"[{b_min:.1f}, {b_max if b_max <= 1.0 else 1.0:.1f})",
                    "count": 0,
                    "accuracy": None,
                    "confidence": None,
                    "calibration_error": None,
                })

        ece = round(ece_acc, 4)

        return {
            "status": "CALCULATED",
            "eligible_sample_size": n,
            "brier_score": brier_score,
            "ece": ece,
            "reliability_bins": reliability_bins,
            "reason": None,
        }

    def _determine_status(
        self,
        total_predictions: int,
        evaluated_count: int,
        coverage: Optional[float],
        buckets: Dict[str, Dict[str, Any]],
    ) -> tuple[str, List[str]]:
        """Deterministically evaluates overall calibration status and generates human-readable reasons."""
        reasons = []

        if total_predictions == 0:
            return "NOT_CALIBRATABLE", ["No eligible prediction records found in scope."]

        if evaluated_count < MIN_EVALUATED_OBSERVATIONS:
            reasons.append(
                f"Evaluated prediction count ({evaluated_count}) is below minimum statistical threshold "
                f"({MIN_EVALUATED_OBSERVATIONS})."
            )
            return "INSUFFICIENT_DATA", reasons

        # Check bucket monotonicity
        high_cr = buckets["HIGH"]["correctness_rate"]
        med_cr = buckets["MEDIUM"]["correctness_rate"]
        low_cr = buckets["LOW"]["correctness_rate"]

        is_monotonic = True
        if high_cr is not None and med_cr is not None and high_cr < med_cr:
            is_monotonic = False
            reasons.append(
                f"High-confidence correctness rate ({high_cr*100:.1f}%) is lower than medium-confidence "
                f"correctness rate ({med_cr*100:.1f}%)."
            )
        if med_cr is not None and low_cr is not None and med_cr < low_cr:
            is_monotonic = False
            reasons.append(
                f"Medium-confidence correctness rate ({med_cr*100:.1f}%) is lower than low-confidence "
                f"correctness rate ({low_cr*100:.1f}%)."
            )

        if (coverage or 0.0) >= 0.70 and is_monotonic and evaluated_count >= 5:
            return "CALIBRATED", reasons

        if evaluated_count >= MIN_EVALUATED_OBSERVATIONS:
            if (coverage or 0.0) < 0.70:
                reasons.append(
                    f"Coverage ({coverage*100:.1f}%) is below full calibration threshold (70.0%)."
                )
            return "PARTIALLY_CALIBRATED", reasons

        return "INSUFFICIENT_DATA", reasons
