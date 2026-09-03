"""Ask Sentinel read-only tool registry and permission boundary.

Enforces strict read-only access to operational financial repositories.
Zero mutation authority (no remediation execution, transaction creation,
ledger modification, policy override, or ground-truth access).
"""
import json
from typing import Any, Callable, Dict, List, Optional
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.exceptions import ExceptionRecord, ExceptionStateTransition, ExceptionAffectedRecord
from backend.models.risk import RiskAssessment
from backend.models.policy import PolicyDecisionRecord
from backend.models.audit import AuditEvent
from backend.agent.tools.control_findings import lookup_control_findings


class AskSentinelToolRegistry:
    """Explicit permission registry exposing strictly read-only operational tools for Ask Sentinel."""

    ASK_SENTINEL_ALLOWED_TOOLS = [
        "get_exception",
        "search_exceptions",
        "get_payment",
        "get_settlement",
        "get_ledger_entries",
        "get_merchant",
        "get_order",
        "get_control_findings",
        "get_risk_assessment",
        "get_policy_decision",
        "get_verifier_opinion",
        "get_clusters",
        "get_merchant_trust_score",
        "get_business_impact",
        "get_drift_prediction",
        "get_confidence_calibration",
        "get_escalation_status",
        "get_audit_events",
        "get_aggregate_summary",
    ]

    def __init__(self, max_tool_calls: int = 15):
        self.max_tool_calls = max_tool_calls
        self.call_count = 0
        self._tools: Dict[str, Callable] = {
            "get_exception": self.get_exception,
            "search_exceptions": self.search_exceptions,
            "get_payment": self.get_payment,
            "get_settlement": self.get_settlement,
            "get_ledger_entries": self.get_ledger_entries,
            "get_merchant": self.get_merchant,
            "get_order": self.get_order,
            "get_control_findings": self.get_control_findings,
            "get_risk_assessment": self.get_risk_assessment,
            "get_policy_decision": self.get_policy_decision,
            "get_verifier_opinion": self.get_verifier_opinion,
            "get_clusters": self.get_clusters,
            "get_merchant_trust_score": self.get_merchant_trust_score,
            "get_business_impact": self.get_business_impact,
            "get_drift_prediction": self.get_drift_prediction,
            "get_confidence_calibration": self.get_confidence_calibration,
            "get_escalation_status": self.get_escalation_status,
            "get_audit_events": self.get_audit_events,
            "get_aggregate_summary": self.get_aggregate_summary,
        }

    def reset_call_counter(self):
        self.call_count = 0

    def sanitize_field_value(self, val: Any) -> Any:
        """Sanitizes text fields to neutralize prompt injection while preserving factual operational data."""
        if isinstance(val, str):
            clean = val.replace("\r\n", " ").replace("\n", " ").strip()
            return clean
        elif isinstance(val, dict):
            return {k: self.sanitize_field_value(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [self.sanitize_field_value(item) for item in val]
        return val

    def execute_tool(self, tool_name: str, session: Session, **kwargs) -> Dict[str, Any]:
        """Executes a registered read-only tool within execution and safety limits."""
        if tool_name not in self.ASK_SENTINEL_ALLOWED_TOOLS:
            return {
                "status": "error",
                "tool_name": tool_name,
                "error": f"Tool '{tool_name}' is not in Ask Sentinel read-only allowlist.",
            }

        if self.call_count >= self.max_tool_calls:
            return {
                "status": "error",
                "tool_name": tool_name,
                "error": f"Maximum copilot tool execution limit ({self.max_tool_calls}) reached.",
            }

        self.call_count += 1
        fn = self._tools[tool_name]
        try:
            raw_result = fn(session=session, **kwargs)
            sanitized = self.sanitize_field_value(raw_result)
            return {
                "status": "success",
                "tool_name": tool_name,
                "data": sanitized,
            }
        except Exception as err:
            return {
                "status": "error",
                "tool_name": tool_name,
                "error": str(err),
            }

    # --- Tool Implementations ---

    def get_exception(self, session: Session, exception_id: str) -> Dict[str, Any]:
        """Retrieves detailed operational exception record."""
        stmt = select(ExceptionRecord).where(
            or_(
                func.upper(ExceptionRecord.exception_id) == func.upper(exception_id),
                func.upper(ExceptionRecord.primary_payment_id) == func.upper(exception_id),
            )
        )
        rec = session.scalars(stmt).first()
        if not rec:
            return {"found": False, "message": f"Exception '{exception_id}' not found."}

        # Retrieve affected record links
        aff_stmt = select(ExceptionAffectedRecord).where(ExceptionAffectedRecord.exception_id == rec.exception_id)
        affected_records = [
            {"record_type": r.record_type, "record_id": r.record_identifier}
            for r in session.scalars(aff_stmt).all()
        ]

        return {
            "found": True,
            "exception_id": rec.exception_id,
            "exception_type": rec.exception_type,
            "severity": rec.severity,
            "state": rec.state,
            "exposure_minor_units": rec.exposure,
            "description": rec.description,
            "primary_payment_id": rec.primary_payment_id,
            "primary_order_id": rec.primary_order_id,
            "source_flag": rec.source_flag,
            "detected_at": rec.detected_at.isoformat() if rec.detected_at else None,
            "affected_records": affected_records,
        }

    def search_exceptions(
        self,
        session: Session,
        family: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Searches open or historical exceptions by type, state, or limit."""
        stmt = select(ExceptionRecord)
        if family:
            stmt = stmt.where(ExceptionRecord.exception_type == family)
        if state:
            stmt = stmt.where(ExceptionRecord.state == state)

        stmt = stmt.order_by(ExceptionRecord.detected_at.desc()).limit(min(limit, 50))
        recs = session.scalars(stmt).all()

        return {
            "count": len(recs),
            "exceptions": [
                {
                    "exception_id": r.exception_id,
                    "type": r.exception_type,
                    "state": r.state,
                    "severity": r.severity,
                    "exposure_minor_units": r.exposure,
                    "primary_payment_id": r.primary_payment_id,
                    "source_flag": r.source_flag,
                    "detected_at": r.detected_at.isoformat() if r.detected_at else None,
                }
                for r in recs
            ],
        }

    def get_payment(self, session: Session, payment_id: str) -> Dict[str, Any]:
        """Retrieves gateway payment transaction details."""
        stmt = select(GatewayTransaction).where(GatewayTransaction.payment_id == payment_id)
        gtx = session.scalars(stmt).first()
        if not gtx:
            return {"found": False, "message": f"Payment transaction '{payment_id}' not found."}

        return {
            "found": True,
            "payment_id": gtx.payment_id,
            "merchant_id": gtx.merchant_id,
            "amount_minor_units": gtx.amount,
            "currency": gtx.currency,
            "status": gtx.status,
            "method": gtx.method,
            "card_type": gtx.card_type,
            "auth_code": gtx.auth_code,
            "error_code": gtx.error_code,
            "created_at": gtx.created_at.isoformat() if gtx.created_at else None,
        }

    def get_settlement(self, session: Session, settlement_id: str) -> Dict[str, Any]:
        """Retrieves bank settlement batch details by settlement_id or payment_id."""
        stmt = select(BankSettlementBatch).where(
            or_(
                BankSettlementBatch.settlement_id == settlement_id,
                BankSettlementBatch.payment_id == settlement_id,
            )
        )
        batches = session.scalars(stmt).all()
        if not batches:
            return {"found": False, "message": f"Settlement batch record for '{settlement_id}' not found."}

        return {
            "found": True,
            "count": len(batches),
            "settlements": [
                {
                    "settlement_id": b.settlement_id,
                    "payment_id": b.payment_id,
                    "utr_number": b.utr_number,
                    "acquirer_id": b.acquirer_id,
                    "net_amount_minor_units": b.net_amount,
                    "interchange_fee_deducted": b.interchange_fee_deducted,
                    "tax_deducted": b.tax_deducted,
                    "clearing_timestamp": b.clearing_timestamp.isoformat() if b.clearing_timestamp else None,
                }
                for b in batches
            ],
        }

    def get_ledger_entries(
        self,
        session: Session,
        payment_id: Optional[str] = None,
        account_id: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Retrieves nodal ledger double-entry audit records."""
        stmt = select(NodalLedgerEntry)
        if payment_id:
            stmt = stmt.where(NodalLedgerEntry.payment_id == payment_id)
        if account_id:
            stmt = stmt.where(NodalLedgerEntry.nodal_account_id == account_id)

        stmt = stmt.order_by(NodalLedgerEntry.entry_timestamp.desc()).limit(min(limit, 50))
        entries = session.scalars(stmt).all()

        return {
            "count": len(entries),
            "ledger_entries": [
                {
                    "entry_id": e.entry_id,
                    "payment_id": e.payment_id,
                    "account_id": e.nodal_account_id,
                    "entry_type": e.entry_type,
                    "debit_minor_units": e.debit_amount,
                    "credit_minor_units": e.credit_amount,
                    "running_balance_minor_units": e.running_balance,
                    "timestamp": e.entry_timestamp.isoformat() if e.entry_timestamp else None,
                }
                for e in entries
            ],
        }

    def get_merchant(self, session: Session, merchant_id: str) -> Dict[str, Any]:
        """Retrieves merchant overview and exception summary."""
        stmt_pay = select(GatewayTransaction).where(GatewayTransaction.merchant_id == merchant_id)
        gtxs = session.scalars(stmt_pay).all()
        payment_ids = [g.payment_id for g in gtxs]

        exc_count = 0
        open_exc = []
        if payment_ids:
            stmt_exc = select(ExceptionRecord).where(ExceptionRecord.primary_payment_id.in_(payment_ids))
            excs = session.scalars(stmt_exc).all()
            exc_count = len(excs)
            open_exc = [e.exception_id for e in excs if e.state not in ("VERIFIED_CLOSED", "REMEDIATED")]

        return {
            "merchant_id": merchant_id,
            "total_transactions_found": len(gtxs),
            "total_exceptions_found": exc_count,
            "unresolved_exception_ids": open_exc,
        }

    def get_order(self, session: Session, order_id: str) -> Dict[str, Any]:
        """Retrieves merchant order fulfillment details."""
        stmt = select(MerchantOrder).where(MerchantOrder.order_id == order_id)
        ord_rec = session.scalars(stmt).first()
        if not ord_rec:
            return {"found": False, "message": f"Merchant order '{order_id}' not found."}

        return {
            "found": True,
            "order_id": ord_rec.order_id,
            "merchant_id": ord_rec.merchant_id,
            "payment_id": ord_rec.payment_id,
            "gross_amount_minor_units": ord_rec.gross_amount,
            "fulfillment_status": ord_rec.fulfillment_status,
            "created_at": ord_rec.created_at.isoformat() if ord_rec.created_at else None,
        }

    def get_control_findings(self, session: Session, exception_id: str) -> Dict[str, Any]:
        """Retrieves deterministic control findings for an exception."""
        # Delegates to existing lookup_control_findings tool
        findings = lookup_control_findings(session=session, exception_id=exception_id)
        return {"exception_id": exception_id, "findings": findings}

    def get_risk_assessment(self, session: Session, exception_id: str) -> Dict[str, Any]:
        """Retrieves exposure quantification and risk assessment for an exception."""
        stmt = select(RiskAssessment).where(RiskAssessment.exception_id == exception_id)
        risk = session.scalars(stmt).first()
        if not risk:
            return {"found": False, "message": f"No risk assessment recorded for exception '{exception_id}'."}

        return {
            "found": True,
            "assessment_id": risk.assessment_id,
            "exception_id": risk.exception_id,
            "risk_score": risk.risk_score,
            "priority": risk.priority,
            "materiality": risk.materiality,
            "exposure_type": risk.exposure_type,
            "quantitative_exposure": risk.quantitative_exposure,
            "explanation": risk.deterministic_explanation,
            "created_at": risk.created_at.isoformat() if risk.created_at else None,
        }

    def get_policy_decision(self, session: Session, exception_id: str) -> Dict[str, Any]:
        """Retrieves policy decision records for an exception."""
        stmt = select(PolicyDecisionRecord).where(PolicyDecisionRecord.exception_id == exception_id)
        decisions = session.scalars(stmt).all()
        if not decisions:
            return {"found": False, "message": f"No policy decision recorded for exception '{exception_id}'."}

        return {
            "found": True,
            "decisions": [
                {
                    "decision_id": d.decision_id,
                    "requested_action": d.requested_action,
                    "decision": d.decision,
                    "approval_required": d.approval_required,
                    "required_role": d.required_role,
                    "reasoning": d.reasoning,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in decisions
            ],
        }

    def get_verifier_opinion(self, session: Session, exception_id: str) -> Dict[str, Any]:
        """Retrieves independent adversarial verifier opinion for an exception."""
        from backend.models.verifier import VerifierOpinion
        stmt = (
            select(VerifierOpinion)
            .where(func.upper(VerifierOpinion.exception_id) == func.upper(exception_id))
            .order_by(VerifierOpinion.created_at.desc())
        )
        opinion = session.scalars(stmt).first()
        if not opinion:
            return {"found": False, "message": f"No verifier opinion recorded for exception '{exception_id}'."}

        return {
            "found": True,
            "opinion_id": opinion.opinion_id,
            "exception_id": opinion.exception_id,
            "verdict": opinion.verdict,
            "confidence": opinion.confidence,
            "reasoning_summary": opinion.reasoning_summary,
            "evidence_refs": json.loads(opinion.evidence_refs) if opinion.evidence_refs else [],
            "recommended_action": opinion.recommended_action,
            "original_policy_decision": opinion.original_policy_decision,
            "final_policy_decision": opinion.final_policy_decision,
            "verifier_version": opinion.verifier_version,
            "created_at": opinion.created_at.isoformat() if opinion.created_at else None,
        }

    def get_clusters(
        self,
        session: Session,
        pattern_type: Optional[str] = None,
        exception_family: Optional[str] = None,
        merchant_id: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Retrieves structured recurring pattern clusters from the Pattern Miner."""
        from backend.patterns.miner import PatternMinerService
        service = PatternMinerService()
        clusters = service.get_clusters(
            session=session,
            pattern_type=pattern_type,
            exception_family=exception_family,
            merchant_id=merchant_id,
            limit=limit,
        )
        return {
            "total_clusters": len(clusters),
            "clusters": clusters,
        }

    def get_merchant_trust_score(self, session: Session, merchant_id: str) -> Dict[str, Any]:
        """Retrieves deterministic Merchant Trust & Impact Score."""
        from sqlalchemy import func
        from backend.api.merchants import _format_merchant_response
        from backend.models.merchant_score import MerchantScore
        from backend.merchants.scoring import MerchantScoringService
        
        m_id_clean = merchant_id.strip()
        score = session.query(MerchantScore).filter(func.lower(MerchantScore.merchant_id) == m_id_clean.lower()).first()
        if not score:
            scoring_service = MerchantScoringService()
            scoring_service.calculate_all_scores(session)
            score = session.query(MerchantScore).filter(func.lower(MerchantScore.merchant_id) == m_id_clean.lower()).first()
            
        if not score:
            return {"found": False, "message": f"Merchant score for '{merchant_id}' not found."}
            
        return {"found": True, "score": _format_merchant_response(score)}

    def get_business_impact(self, session: Session) -> Dict[str, Any]:
        """Retrieves deterministic Business Impact and ROI analytics from persisted records."""
        from backend.impact.roi_service import BusinessImpactService
        service = BusinessImpactService()
        result = service.calculate_impact(session=session, log_audit=True, actor_type="AI_AGENT", actor_id="ask_sentinel")
        return {
            "found": True,
            "impact": result,
        }

    def get_drift_prediction(self, session: Session, nodal_account_id: str = "nodal_escrow_main") -> Dict[str, Any]:
        """Retrieves deterministic leading early-warning operational drift signals for a nodal account."""
        from backend.predictions.drift_service import PredictiveDriftService
        service = PredictiveDriftService()
        result = service.evaluate_drift(
            session=session,
            nodal_account_id=nodal_account_id,
            persist=True,
            log_audit=True,
            actor_id="ask_sentinel",
        )
        return {
            "found": True,
            "drift": result,
        }

    def get_confidence_calibration(
        self,
        session: Session,
        prediction_type: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves deterministic confidence calibration and empirical correctness metrics."""
        from backend.calibration.service import ConfidenceCalibrationService
        service = ConfidenceCalibrationService()
        result = service.evaluate_calibration(
            session=session,
            prediction_type=prediction_type,
            source=source,
            persist=True,
            log_audit=True,
            actor_id="ask_sentinel",
        )
        return {
            "found": True,
            "calibration": result,
        }

    def get_audit_events(self, session: Session, entity_id: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """Retrieves append-only audit event trail."""
        stmt = select(AuditEvent)
        if entity_id:
            stmt = stmt.where(
                or_(
                    AuditEvent.exception_id == entity_id,
                    AuditEvent.investigation_id == entity_id,
                    AuditEvent.event_payload.like(f"%{entity_id}%"),
                )
            )

        stmt = stmt.order_by(AuditEvent.timestamp.desc()).limit(min(limit, 50))
        events = session.scalars(stmt).all()

        return {
            "count": len(events),
            "events": [
                {
                    "audit_event_id": e.audit_event_id,
                    "event_type": e.event_type,
                    "actor_id": e.actor_id,
                    "summary": e.event_summary,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                }
                for e in events
            ],
        }

    def get_aggregate_summary(self, session: Session) -> Dict[str, Any]:
        """Retrieves deterministic aggregate stats on open exceptions and exposure."""
        stmt_tot = select(func.count(ExceptionRecord.id))
        total_exceptions = session.scalar(stmt_tot) or 0

        stmt_open = select(
            func.count(ExceptionRecord.id),
            func.sum(ExceptionRecord.exposure)
        ).where(
            ExceptionRecord.state.not_in(["VERIFIED_CLOSED", "REMEDIATED"])
        )
        row_open = session.execute(stmt_open).fetchone()
        open_count = row_open[0] if row_open else 0
        open_exposure = row_open[1] if row_open and row_open[1] is not None else 0

        # Breakdown by family
        stmt_fam = select(
            ExceptionRecord.exception_type,
            func.count(ExceptionRecord.id),
            func.sum(ExceptionRecord.exposure)
        ).where(
            ExceptionRecord.state.not_in(["VERIFIED_CLOSED", "REMEDIATED"])
        ).group_by(ExceptionRecord.exception_type)

        fam_rows = session.execute(stmt_fam).fetchall()
        family_breakdown = [
            {"family": r[0], "open_count": r[1], "exposure_minor_units": r[2] or 0}
            for r in fam_rows
        ]

        return {
            "total_exceptions": total_exceptions,
            "open_exceptions_count": open_count,
            "open_exposure_minor_units": open_exposure,
            "family_breakdown": family_breakdown,
        }

    def get_escalation_status(self, session: Session, exception_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves safe escalation webhook delivery status and masked configuration."""
        from backend.escalation.service import EscalationWebhookService
        svc = EscalationWebhookService()
        cfg = svc.get_webhook_configuration()
        recent = svc.get_recent_deliveries(session=session, limit=10)

        specific = None
        if exception_id:
            for d in recent:
                if d["exception_id"] == exception_id:
                    specific = d
                    break

        return {
            "configuration": cfg,
            "specific_delivery": specific,
            "recent_deliveries_count": len(recent),
            "recent_deliveries": recent[:5],
        }
