"""Entity Lineage and Provenance Reconstruction Service for Nodal Sentinel.

Provides complete, deterministic end-to-end traceability for any financial exception
from synthetic ingestion through controls, investigation, risk, policy, remediation,
and independent verification.
"""
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.exceptions import ExceptionRecord
from backend.models.financial_sources import (
    GatewayTransaction,
    MerchantOrder,
    BankSettlementBatch,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.investigation import InvestigationRun
from backend.models.risk import RiskAssessment
from backend.models.policy import PolicyDecisionRecord
from backend.models.remediation import RemediationAction
from backend.models.verification import VerificationRecord
from backend.models.audit import AuditEvent


class EntityLineageService:
    """Reconstructs complete explainability and lineage traces."""

    @staticmethod
    def get_exception_lineage(session: Session, exception_id: str) -> Dict[str, Any]:
        """Traces the complete lifecycle, affected financial records, and decisions for an exception."""
        exc = session.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)).first()
        if not exc:
            raise ValueError(f"Exception '{exception_id}' not found.")

        # 1. Primary Financial Records
        payment = None
        orders = []
        settlements = []
        disputes = []
        ledger_entries = []

        if exc.primary_payment_id:
            payment = session.scalars(
                select(GatewayTransaction).where(GatewayTransaction.payment_id == exc.primary_payment_id)
            ).first()
            if payment:
                orders = list(session.scalars(
                    select(MerchantOrder).where(MerchantOrder.payment_id_reference == payment.payment_id)
                ).all())
                settlements = list(session.scalars(
                    select(BankSettlementBatch).where(BankSettlementBatch.payment_id == payment.payment_id)
                ).all())
                disputes = list(session.scalars(
                    select(DisputeRefundEvent).where(DisputeRefundEvent.payment_id == payment.payment_id)
                ).all())
                ledger_entries = list(session.scalars(
                    select(NodalLedgerEntry).where(NodalLedgerEntry.transaction_id == payment.payment_id)
                ).all())

        # If unallocated settlement without payment mapping
        if not settlements and "SET-" in (exc.primary_payment_id or exc.exception_id):
            batch_id = exc.primary_payment_id if (exc.primary_payment_id and exc.primary_payment_id.startswith("SET-")) else None
            if batch_id:
                orphan = session.scalars(select(BankSettlementBatch).where(BankSettlementBatch.settlement_id == batch_id)).first()
                if orphan:
                    settlements = [orphan]

        # 2. AI Investigations
        investigations = list(session.scalars(
            select(InvestigationRun).where(InvestigationRun.exception_id == exception_id).order_by(InvestigationRun.created_at.asc())
        ).all())

        # 3. Risk Assessments
        risk_assessments = list(session.scalars(
            select(RiskAssessment).where(RiskAssessment.exception_id == exception_id).order_by(RiskAssessment.calculated_at.asc())
        ).all())

        # 4. Policy Decisions
        policy_decisions = list(session.scalars(
            select(PolicyDecisionRecord).where(PolicyDecisionRecord.exception_id == exception_id).order_by(PolicyDecisionRecord.id.asc())
        ).all())

        # 5. Remediation Actions
        remediations = list(session.scalars(
            select(RemediationAction).where(RemediationAction.exception_id == exception_id).order_by(RemediationAction.created_at.asc())
        ).all())

        # 6. Verification Records
        verifications = []
        for rem in remediations:
            vers = list(session.scalars(
                select(VerificationRecord).where(VerificationRecord.remediation_id == rem.action_id).order_by(VerificationRecord.created_at.asc())
            ).all())
            verifications.extend(vers)

        # 7. Audit Trail Events
        audit_events = list(session.scalars(
            select(AuditEvent).where(AuditEvent.exception_id == exception_id).order_by(AuditEvent.timestamp.asc())
        ).all())

        return {
            "exception": {
                "exception_id": exc.exception_id,
                "exception_type": exc.exception_type,
                "state": exc.state,
                "exposure": exc.exposure,
                "severity": exc.severity,
                "confidence": float(exc.confidence) if exc.confidence else 1.0,
                "description": exc.description,
                "primary_payment_id": exc.primary_payment_id,
                "detected_at": exc.detected_at.isoformat() if exc.detected_at else None,
                "resolved_at": exc.resolved_at.isoformat() if exc.resolved_at else None,
            },
            "financial_context": {
                "payment": {
                    "payment_id": payment.payment_id,
                    "amount": payment.amount,
                    "status": payment.status,
                    "currency": payment.currency,
                    "payment_method": payment.method,
                    "created_at": payment.created_at.isoformat() if payment.created_at else None,
                } if payment else None,
                "orders": [
                    {
                        "order_id": o.order_id,
                        "amount": o.order_amount,
                        "status": o.fulfillment_status,
                    }
                    for o in orders
                ],
                "settlements": [
                    {
                        "settlement_id": s.settlement_id,
                        "utr_number": s.utr_number,
                        "net_amount": s.net_amount,
                        "clearing_timestamp": s.clearing_timestamp.isoformat() if s.clearing_timestamp else None,
                    }
                    for s in settlements
                ],
                "disputes": [
                    {
                        "event_id": d.event_id,
                        "event_type": d.event_type,
                        "amount": d.amount,
                    }
                    for d in disputes
                ],
                "ledger_entries_count": len(ledger_entries),
            },
            "investigations": [
                {
                    "investigation_id": inv.investigation_id,
                    "status": inv.status,
                    "root_cause": inv.root_cause,
                    "final_classification": inv.final_classification,
                    "recommended_action": inv.recommended_action,
                    "confidence": float(inv.confidence) if inv.confidence else None,
                    "completed_at": inv.completed_at.isoformat() if inv.completed_at else None,
                }
                for inv in investigations
            ],
            "risk_assessments": [
                {
                    "assessment_id": r.assessment_id,
                    "risk_score": r.risk_score,
                    "priority": r.priority,
                    "materiality": r.materiality,
                    "net_exposure": r.net_exposure,
                    "explanation": r.explanation,
                }
                for r in risk_assessments
            ],
            "policy_decisions": [
                {
                    "decision_id": p.decision_id,
                    "requested_action": p.requested_action,
                    "decision": p.decision,
                    "approval_required": p.approval_required,
                    "rationale": p.rationale,
                }
                for p in policy_decisions
            ],
            "remediations": [
                {
                    "action_id": rem.action_id,
                    "action_type": rem.action_type,
                    "status": rem.status,
                    "approval_required": rem.approval_required,
                    "approved_by": rem.approved_by,
                    "executed_at": rem.executed_at.isoformat() if rem.executed_at else None,
                }
                for rem in remediations
            ],
            "verifications": [
                {
                    "verification_id": v.verification_id,
                    "verification_status": v.verification_status,
                    "remaining_exposure": v.remaining_exposure,
                    "exposure_reduction": v.exposure_reduction,
                    "completed_at": v.completed_at.isoformat() if v.completed_at else None,
                }
                for v in verifications
            ],
            "audit_events": [
                {
                    "audit_event_id": a.audit_event_id,
                    "event_type": a.event_type,
                    "actor_type": a.actor_type,
                    "actor_id": a.actor_id,
                    "event_summary": a.event_summary,
                    "timestamp": a.timestamp.isoformat() if a.timestamp else None,
                }
                for a in audit_events
            ],
        }
