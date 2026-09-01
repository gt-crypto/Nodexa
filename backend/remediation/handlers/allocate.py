"""Handler for ALLOCATE_SETTLEMENT linking unallocated bank credit tranches to merchant payments."""
from datetime import datetime, timezone
from typing import Any, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.financial_sources import BankSettlementBatch, NodalLedgerEntry
from backend.models.remediation import RemediationAction
from backend.remediation.handlers.base import BaseActionHandler


class AllocateSettlementHandler(BaseActionHandler):
    """Associates an unallocated bank settlement tranche to merchant payment records."""

    def execute(
        self,
        session: Session,
        plan: RemediationAction,
        parameters: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        settlement_id = parameters["settlement_id"]
        payment_id = parameters.get("payment_id")
        amount = parameters["amount_minor_units"]
        reason = parameters.get("reason", "Manual settlement tranche allocation")

        batch = session.scalars(select(BankSettlementBatch).where(BankSettlementBatch.batch_id == settlement_id)).first()

        before_snapshot = {
            "settlement_id": settlement_id,
            "net_amount": batch.net_amount if batch else amount,
            "allocated_payment_id": None,
        }

        # Update ledger reference if existing entry has this settlement ID
        entries = list(session.scalars(select(NodalLedgerEntry).where(NodalLedgerEntry.reference.like(f"%{settlement_id}%"))).all())
        for entry in entries:
            entry.reference = f"{entry.reference or ''} [Allocated to {payment_id} via {plan.action_id}]"

        session.flush()

        after_snapshot = {
            "settlement_id": settlement_id,
            "net_amount": batch.net_amount if batch else amount,
            "allocated_payment_id": payment_id,
            "allocation_reason": reason,
        }

        summary = f"Successfully allocated bank settlement {settlement_id} (₹{amount/100:,.2f}) to payment {payment_id}."
        return before_snapshot, after_snapshot, summary

    def dry_run(
        self,
        session: Session,
        plan: RemediationAction,
        parameters: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        settlement_id = parameters.get("settlement_id")
        payment_id = parameters.get("payment_id")
        amount = parameters.get("amount_minor_units", 0)

        before_snapshot = {"settlement_id": settlement_id, "allocated_payment_id": None}
        after_snapshot = {"settlement_id": settlement_id, "projected_allocated_payment_id": payment_id, "amount": amount}
        return before_snapshot, after_snapshot
