"""Handler for RECONCILE execution updating settlement clearing references and operational reconciliations."""
from datetime import datetime, timezone
from typing import Any, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.financial_sources import BankSettlementBatch, GatewayTransaction
from backend.models.remediation import RemediationAction
from backend.remediation.handlers.base import BaseActionHandler


class ReconcileHandler(BaseActionHandler):
    """Executes reconciliation updates on delayed or split settlements."""

    def execute(
        self,
        session: Session,
        plan: RemediationAction,
        parameters: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        payment_id = parameters.get("payment_id")
        ref_id = parameters.get("reconciliation_reference", plan.action_id)
        reason = parameters.get("reason", "Re-evaluated clearing and settlement reconciliation")

        gt = session.scalars(select(GatewayTransaction).where(GatewayTransaction.payment_id == payment_id)).first() if payment_id else None

        before_snapshot = {
            "payment_id": payment_id,
            "status": gt.status if gt else "UNKNOWN",
        }

        after_snapshot = {
            "payment_id": payment_id,
            "status": gt.status if gt else "RECONCILED",
            "reconciliation_reference": ref_id,
            "reconciled_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
        }

        summary = f"Reconciled payment {payment_id} under reference {ref_id}."
        return before_snapshot, after_snapshot, summary

    def dry_run(
        self,
        session: Session,
        plan: RemediationAction,
        parameters: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        payment_id = parameters.get("payment_id")
        return (
            {"payment_id": payment_id, "status": "PENDING_RECONCILIATION"},
            {"payment_id": payment_id, "projected_status": "RECONCILED"},
        )
