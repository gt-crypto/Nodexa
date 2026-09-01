"""Deterministic exposure recalculation for post-remediation verification."""
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.exceptions import ExceptionRecord, ExceptionAffectedRecord
from backend.models.remediation import RemediationAction
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.enums import (
    ExceptionType,
    PaymentStatus,
    DisputeEventType,
    LedgerEntryType,
)


def recalculate_deterministic_exposure(
    session: Session,
    exception: ExceptionRecord,
    remediation_plan: Optional[RemediationAction] = None,
) -> Tuple[int, int, int, Dict[str, Any]]:
    """Deterministically recalculates remaining financial exposure from live operational records.
    
    Returns:
        (remaining_exposure, exposure_reduction, exposure_reduction_bps, explanation_breakdown)
    
    Guarantees:
    - Pure integer arithmetic (minor units: paise/cents, basis points).
    - Never uses floating point math.
    - Never blindly trusts prior exposure assessments.
    """
    orig_exp = int(exception.exposure or 0)
    exc_type = exception.exception_type
    pmt_id = exception.primary_payment_id

    remaining_exposure = 0
    breakdown: Dict[str, Any] = {
        "original_exposure": orig_exp,
        "exception_type": exc_type,
        "primary_payment_id": pmt_id,
        "evaluations": [],
    }

    # 1. Legitimate observations have 0 anomaly exposure by definition
    if exc_type in (
        ExceptionType.PARTIAL_SETTLEMENT.value,
        ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value,
    ):
        remaining_exposure = 0
        breakdown["evaluations"].append({
            "rule": "Legitimate observation maintains zero financial anomaly exposure.",
            "remaining": 0,
        })

    # 2. Ghost Settlement
    elif exc_type == ExceptionType.GHOST_SETTLEMENT.value:
        payment = session.scalars(
            select(GatewayTransaction).where(GatewayTransaction.payment_id == pmt_id)
        ).first() if pmt_id else None

        # Check if refund or corrective ledger entry exists
        refund_events = list(session.scalars(
            select(DisputeRefundEvent).where(DisputeRefundEvent.payment_id == pmt_id)
        ).all()) if pmt_id else []

        refund_total = sum(r.amount for r in refund_events if r.event_type == DisputeEventType.REFUND.value)

        # Check ledger debit for this ghost payment
        ledger_entries = list(session.scalars(
            select(NodalLedgerEntry).where(NodalLedgerEntry.transaction_id == pmt_id)
        ).all()) if pmt_id else []
        ledger_debits = sum(l.debit for l in ledger_entries)

        if payment and payment.status == PaymentStatus.REFUNDED.value and refund_total >= orig_exp:
            remaining_exposure = 0
            breakdown["evaluations"].append({
                "rule": "Ghost settlement fully refunded in gateway & dispute records.",
                "refunded_amount": refund_total,
                "remaining": 0,
            })
        elif ledger_debits >= orig_exp:
            remaining_exposure = 0
            breakdown["evaluations"].append({
                "rule": "Ghost settlement offset by ledger debit entry.",
                "ledger_debit": ledger_debits,
                "remaining": 0,
            })
        else:
            remaining_exposure = max(0, orig_exp - max(refund_total, ledger_debits))
            breakdown["evaluations"].append({
                "rule": "Ghost settlement remains unoffset or partially offset.",
                "offset_amount": max(refund_total, ledger_debits),
                "remaining": remaining_exposure,
            })

    # 3. Refund + Chargeback Double-Dip
    elif exc_type == ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value:
        # Check if reversal event was posted
        disputes = list(session.scalars(
            select(DisputeRefundEvent).where(DisputeRefundEvent.payment_id == pmt_id)
        ).all()) if pmt_id else []

        reversals = [
            d for d in disputes
            if d.event_type in (
                DisputeEventType.REVERSAL.value,
                DisputeEventType.CHARGEBACK_REVERSAL.value,
            )
        ]
        reversal_amount = sum(r.amount for r in reversals)

        ledger_credits = 0
        if pmt_id:
            ledger_entries = list(session.scalars(
                select(NodalLedgerEntry).where(NodalLedgerEntry.transaction_id == pmt_id)
            ).all())
            ledger_credits = sum(
                l.credit for l in ledger_entries
                if l.entry_type in (LedgerEntryType.REVERSAL.value, LedgerEntryType.ADJUSTMENT.value)
            )

        resolved_amount = max(reversal_amount, ledger_credits)
        if resolved_amount >= orig_exp:
            remaining_exposure = 0
            breakdown["evaluations"].append({
                "rule": "Duplicate refund/chargeback successfully reversed in dispute & ledger.",
                "reversed_amount": resolved_amount,
                "remaining": 0,
            })
        else:
            remaining_exposure = max(0, orig_exp - resolved_amount)
            breakdown["evaluations"].append({
                "rule": "Duplicate liability only partially reversed or unreversed.",
                "reversed_amount": resolved_amount,
                "remaining": remaining_exposure,
            })

    # 4. Settlement SLA Breach
    elif exc_type == ExceptionType.SETTLEMENT_SLA_BREACH.value:
        # Check if settlement batch is now reconciled / processed
        settlements = list(session.scalars(
            select(BankSettlementBatch).where(BankSettlementBatch.payment_id == pmt_id)
        ).all()) if pmt_id else []

        if not settlements and pmt_id:
            settlements = list(session.scalars(
                select(BankSettlementBatch).where(BankSettlementBatch.raw_payment_reference.like(f"%{pmt_id}%"))
            ).all())

        if settlements:
            remaining_exposure = 0
            breakdown["evaluations"].append({
                "rule": "Delayed settlement batch matched and verified.",
                "settlement_ids": [s.settlement_id for s in settlements],
                "remaining": 0,
            })
        else:
            remaining_exposure = orig_exp
            breakdown["evaluations"].append({
                "rule": "Settlement SLA breach remains unresolved.",
                "remaining": remaining_exposure,
            })

    # 5. Missing / Unallocated Settlement
    elif exc_type == ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value:
        # Find affected settlement records
        aff_records = list(session.scalars(
            select(ExceptionAffectedRecord).where(
                ExceptionAffectedRecord.exception_id == exception.exception_id,
                ExceptionAffectedRecord.record_type == "settlement",
            )
        ).all())

        all_allocated = True
        unallocated_total = 0

        for aff in aff_records:
            stl = session.scalars(
                select(BankSettlementBatch).where(BankSettlementBatch.settlement_id == aff.record_identifier)
            ).first()
            if stl and not stl.payment_id:
                all_allocated = False
                unallocated_total += (stl.net_amount or 0)

        if aff_records and all_allocated:
            remaining_exposure = 0
            breakdown["evaluations"].append({
                "rule": "All previously unallocated settlement batches are now linked to payments.",
                "remaining": 0,
            })
        elif not aff_records and pmt_id:
            # Check if payment now has settlement linked
            stl = session.scalars(
                select(BankSettlementBatch).where(BankSettlementBatch.payment_id == pmt_id)
            ).first()
            if stl:
                remaining_exposure = 0
            else:
                remaining_exposure = orig_exp
        else:
            remaining_exposure = unallocated_total if unallocated_total > 0 else orig_exp

    # 6. Default / Generic Fallback
    else:
        remaining_exposure = orig_exp

    # Exposure reduction calculation using pure integer arithmetic
    exposure_reduction = orig_exp - remaining_exposure
    if orig_exp > 0:
        exposure_reduction_bps = (exposure_reduction * 10000) // orig_exp
    else:
        # If original exposure was 0, reduction is 10000 bps (100.00%)
        exposure_reduction_bps = 10000

    breakdown["final_remaining_exposure"] = remaining_exposure
    breakdown["exposure_reduction"] = exposure_reduction
    breakdown["exposure_reduction_bps"] = exposure_reduction_bps

    return remaining_exposure, exposure_reduction, exposure_reduction_bps, breakdown
