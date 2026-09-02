"""Adversarial Verifier read-only tool registry and permission boundary.

Enforces strict read-only access to operational repositories for independent
evidence inspection. Zero mutation authority — no remediation execution,
policy override, ledger modification, approval, or ground-truth access.
"""
import json
from typing import Any, Callable, Dict, List, Optional
from sqlalchemy import select, or_, func
from sqlalchemy.orm import Session

from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.exceptions import ExceptionRecord, ExceptionAffectedRecord
from backend.models.risk import RiskAssessment
from backend.models.policy import PolicyDecisionRecord
from backend.models.audit import AuditEvent
from backend.agent.tools.control_findings import lookup_control_findings


VERIFIER_ALLOWED_TOOLS = [
    "get_exception",
    "get_payment",
    "get_settlement",
    "get_ledger_entries",
    "get_order",
    "get_merchant",
    "get_control_findings",
    "get_risk_assessment",
    "get_policy_decision",
    "get_audit_events",
]


class VerifierToolRegistry:
    """Explicit read-only tool registry for the Adversarial Verifier.

    The verifier MUST NOT have access to:
    - Remediation execution / approval
    - Policy override
    - Ledger / settlement / transaction mutation
    - Exception state mutation
    - Ground-truth or benchmark modification
    """

    def __init__(self, max_tool_calls: int = 20):
        self.max_tool_calls = max_tool_calls
        self.call_count = 0
        self._tools: Dict[str, Callable] = {
            "get_exception": self._get_exception,
            "get_payment": self._get_payment,
            "get_settlement": self._get_settlement,
            "get_ledger_entries": self._get_ledger_entries,
            "get_order": self._get_order,
            "get_merchant": self._get_merchant,
            "get_control_findings": self._get_control_findings,
            "get_risk_assessment": self._get_risk_assessment,
            "get_policy_decision": self._get_policy_decision,
            "get_audit_events": self._get_audit_events,
        }

    def reset_call_counter(self):
        self.call_count = 0

    def sanitize_field(self, val: Any) -> Any:
        """Sanitizes text fields to neutralize prompt injection."""
        if isinstance(val, str):
            return val.replace("\r\n", " ").replace("\n", " ").strip()
        elif isinstance(val, dict):
            return {k: self.sanitize_field(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [self.sanitize_field(item) for item in val]
        return val

    def execute_tool(self, tool_name: str, session: Session, **kwargs) -> Dict[str, Any]:
        """Executes a registered read-only tool within the permission boundary."""
        if tool_name not in VERIFIER_ALLOWED_TOOLS:
            return {
                "status": "error",
                "tool_name": tool_name,
                "error": f"Tool '{tool_name}' is not in Adversarial Verifier read-only allowlist.",
            }

        if self.call_count >= self.max_tool_calls:
            return {
                "status": "error",
                "tool_name": tool_name,
                "error": f"Maximum verifier tool execution limit ({self.max_tool_calls}) reached.",
            }

        self.call_count += 1
        fn = self._tools[tool_name]
        try:
            raw_result = fn(session=session, **kwargs)
            return {"status": "success", "tool_name": tool_name, "data": self.sanitize_field(raw_result)}
        except Exception as err:
            return {"status": "error", "tool_name": tool_name, "error": str(err)}

    # --- Tool Implementations (Read-Only) ---

    def _get_exception(self, session: Session, exception_id: str) -> Dict[str, Any]:
        stmt = select(ExceptionRecord).where(
            or_(
                func.upper(ExceptionRecord.exception_id) == func.upper(exception_id),
                func.upper(ExceptionRecord.primary_payment_id) == func.upper(exception_id),
            )
        )
        rec = session.scalars(stmt).first()
        if not rec:
            return {"found": False}

        aff_stmt = select(ExceptionAffectedRecord).where(ExceptionAffectedRecord.exception_id == rec.exception_id)
        affected = [{"record_type": r.record_type, "record_id": r.record_identifier} for r in session.scalars(aff_stmt).all()]

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
            "affected_records": affected,
        }

    def _get_payment(self, session: Session, payment_id: str) -> Dict[str, Any]:
        gtx = session.scalars(select(GatewayTransaction).where(GatewayTransaction.payment_id == payment_id)).first()
        if not gtx:
            return {"found": False}
        return {
            "found": True,
            "payment_id": gtx.payment_id,
            "merchant_id": gtx.merchant_id,
            "amount_minor_units": gtx.amount,
            "currency": gtx.currency,
            "status": gtx.status,
            "method": gtx.method,
            "error_code": gtx.error_code,
            "created_at": gtx.created_at.isoformat() if gtx.created_at else None,
        }

    def _get_settlement(self, session: Session, settlement_id: str) -> Dict[str, Any]:
        batches = session.scalars(
            select(BankSettlementBatch).where(
                or_(BankSettlementBatch.settlement_id == settlement_id, BankSettlementBatch.payment_id == settlement_id)
            )
        ).all()
        if not batches:
            return {"found": False}
        return {
            "found": True,
            "count": len(batches),
            "settlements": [
                {
                    "settlement_id": b.settlement_id,
                    "payment_id": b.payment_id,
                    "net_amount_minor_units": b.net_amount,
                    "clearing_timestamp": b.clearing_timestamp.isoformat() if b.clearing_timestamp else None,
                }
                for b in batches
            ],
        }

    def _get_ledger_entries(self, session: Session, payment_id: Optional[str] = None, limit: int = 20) -> Dict[str, Any]:
        stmt = select(NodalLedgerEntry)
        if payment_id:
            stmt = stmt.where(NodalLedgerEntry.payment_id == payment_id)
        stmt = stmt.order_by(NodalLedgerEntry.entry_timestamp.desc()).limit(min(limit, 50))
        entries = session.scalars(stmt).all()
        return {
            "count": len(entries),
            "entries": [
                {
                    "entry_id": e.entry_id,
                    "payment_id": e.payment_id,
                    "entry_type": e.entry_type,
                    "debit_minor_units": e.debit_amount,
                    "credit_minor_units": e.credit_amount,
                    "running_balance": e.running_balance,
                }
                for e in entries
            ],
        }

    def _get_order(self, session: Session, order_id: str) -> Dict[str, Any]:
        rec = session.scalars(select(MerchantOrder).where(MerchantOrder.order_id == order_id)).first()
        if not rec:
            return {"found": False}
        return {
            "found": True,
            "order_id": rec.order_id,
            "merchant_id": rec.merchant_id,
            "payment_id": rec.payment_id,
            "gross_amount_minor_units": rec.gross_amount,
            "fulfillment_status": rec.fulfillment_status,
        }

    def _get_merchant(self, session: Session, merchant_id: str) -> Dict[str, Any]:
        gtxs = session.scalars(select(GatewayTransaction).where(GatewayTransaction.merchant_id == merchant_id)).all()
        return {"merchant_id": merchant_id, "total_transactions": len(gtxs)}

    def _get_control_findings(self, session: Session, exception_id: str) -> Dict[str, Any]:
        findings = lookup_control_findings(session=session, exception_id=exception_id)
        return {"exception_id": exception_id, "findings": findings}

    def _get_risk_assessment(self, session: Session, exception_id: str) -> Dict[str, Any]:
        risk = session.scalars(select(RiskAssessment).where(RiskAssessment.exception_id == exception_id)).first()
        if not risk:
            return {"found": False}
        return {
            "found": True,
            "risk_score": risk.risk_score,
            "priority": risk.priority,
            "materiality": risk.materiality,
            "exposure_type": risk.exposure_type,
            "quantitative_exposure": risk.quantitative_exposure,
            "explanation": risk.deterministic_explanation,
        }

    def _get_policy_decision(self, session: Session, exception_id: str) -> Dict[str, Any]:
        decisions = session.scalars(
            select(PolicyDecisionRecord)
            .where(PolicyDecisionRecord.exception_id == exception_id)
            .order_by(PolicyDecisionRecord.evaluated_at.desc())
        ).all()
        if not decisions:
            return {"found": False}
        return {
            "found": True,
            "decisions": [
                {
                    "decision_id": d.decision_id,
                    "requested_action": d.requested_action,
                    "decision": d.decision,
                    "approval_required": d.approval_required,
                    "rationale": d.rationale,
                    "risk_score": d.risk_score,
                    "priority": d.priority,
                    "exposure": d.exposure,
                }
                for d in decisions
            ],
        }

    def _get_audit_events(self, session: Session, exception_id: str, limit: int = 20) -> Dict[str, Any]:
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.exception_id == exception_id)
            .order_by(AuditEvent.timestamp.desc())
            .limit(min(limit, 50))
        )
        events = session.scalars(stmt).all()
        return {
            "count": len(events),
            "events": [
                {
                    "audit_event_id": e.audit_event_id,
                    "event_type": e.event_type,
                    "summary": e.event_summary,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                }
                for e in events
            ],
        }
