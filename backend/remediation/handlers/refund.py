"""Handler for controlled REFUND execution with ledger debit and dispute record creation."""
from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import PaymentStatus, DisputeEventType, LedgerEntryType
from backend.models.financial_sources import GatewayTransaction, DisputeRefundEvent, NodalLedgerEntry
from backend.models.remediation import RemediationAction
from backend.remediation.handlers.base import BaseActionHandler


class RefundHandler(BaseActionHandler):
    """Executes validated customer refund, creates refund event, and posts ledger debit."""

    def execute(
        self,
        session: Session,
        plan: RemediationAction,
        parameters: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        payment_id = parameters["payment_id"]
        amount = parameters["amount_minor_units"]
        reason = parameters.get("reason", "Operational refund remediation")

        gt = session.scalars(select(GatewayTransaction).where(GatewayTransaction.payment_id == payment_id)).first()
        last_ledger = session.scalars(select(NodalLedgerEntry).order_by(NodalLedgerEntry.id.desc())).first()
        prev_balance = last_ledger.balance_after if last_ledger else 0

        before_snapshot = {
            "payment_id": payment_id,
            "payment_status": gt.status if gt else "UNKNOWN",
            "payment_amount": gt.amount if gt else 0,
            "ledger_balance_before": prev_balance,
        }

        # 1. Update gateway transaction status
        if gt:
            gt.status = PaymentStatus.REFUNDED.value

        now = datetime.now(timezone.utc)

        # 2. Record Dispute/Refund Event
        refund_event_id = f"REF-{uuid.uuid4().hex[:12]}"
        refund_evt = DisputeRefundEvent(
            event_id=refund_event_id,
            payment_id=payment_id,
            event_type=DisputeEventType.REFUND.value,
            amount=amount,
            timestamp=now,
            reason_code=reason,
        )
        session.add(refund_evt)

        # 3. Post double-entry ledger debit adjustment
        new_balance = prev_balance - amount
        ledger_entry_id = f"NLE-REF-{uuid.uuid4().hex[:8]}"
        entry = NodalLedgerEntry(
            ledger_id=ledger_entry_id,
            transaction_id=payment_id,
            account_id="nodal_escrow_main",
            entry_type=LedgerEntryType.REFUND_DEBIT.value,
            debit=amount,
            credit=0,
            balance_after=new_balance,
            reference=f"Remediation refund for {plan.exception_id}: {reason}",
            timestamp=now,
        )
        session.add(entry)
        session.flush()

        after_snapshot = {
            "payment_id": payment_id,
            "payment_status": gt.status if gt else PaymentStatus.REFUNDED.value,
            "refund_event_id": refund_event_id,
            "ledger_entry_id": ledger_entry_id,
            "ledger_balance_after": new_balance,
            "refund_amount": amount,
        }

        summary = f"Processed ₹{amount/100:,.2f} refund on {payment_id} and recorded ledger debit entry {ledger_entry_id}."
        return before_snapshot, after_snapshot, summary

    def dry_run(
        self,
        session: Session,
        plan: RemediationAction,
        parameters: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        payment_id = parameters.get("payment_id")
        amount = parameters.get("amount_minor_units", 0)

        gt = session.scalars(select(GatewayTransaction).where(GatewayTransaction.payment_id == payment_id)).first()
        last_ledger = session.scalars(select(NodalLedgerEntry).order_by(NodalLedgerEntry.id.desc())).first()
        prev_balance = last_ledger.balance_after if last_ledger else 0

        before_snapshot = {
            "payment_id": payment_id,
            "payment_status": gt.status if gt else "UNKNOWN",
            "ledger_balance": prev_balance,
        }
        after_snapshot = {
            "payment_id": payment_id,
            "projected_status": PaymentStatus.REFUNDED.value,
            "projected_ledger_balance": prev_balance - amount,
            "projected_debit": amount,
        }
        return before_snapshot, after_snapshot
