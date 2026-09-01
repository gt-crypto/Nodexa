"""Deterministic settlement aggregation and total validation."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.controls.control_result import ControlResult, ControlStatus, EvidenceItem
from backend.models.financial_sources import GatewayTransaction, BankSettlementBatch
from backend.models.enums import PaymentStatus


class SettlementReconciliationStatus(str, Enum):
    """Classification of settlement reconciliation state for a payment."""
    FULL_SETTLEMENT = "FULL_SETTLEMENT"
    PARTIAL_SETTLEMENT_COMPLETE = "PARTIAL_SETTLEMENT_COMPLETE"
    UNDER_SETTLED = "UNDER_SETTLED"
    OVER_SETTLED = "OVER_SETTLED"
    MISSING_SETTLEMENT = "MISSING_SETTLEMENT"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class SettlementAggregation:
    """Aggregated financial summary of all settlement tranches for a payment."""
    payment_id: str
    expected_gross_amount: int
    settlement_count: int
    total_net_amount: int
    total_interchange_fee: int
    total_tax_deducted: int
    total_gross_settled: int
    variance: int  # total_gross_settled - expected_gross_amount
    status: SettlementReconciliationStatus
    settlement_ids: List[str] = field(default_factory=list)


def aggregate_settlements_for_payment(
    payment: GatewayTransaction,
    settlements: List[BankSettlementBatch],
) -> SettlementAggregation:
    """Aggregates all settlement tranches for a payment and determines settlement state."""
    if payment.status != PaymentStatus.CAPTURED.value:
        return SettlementAggregation(
            payment_id=payment.payment_id,
            expected_gross_amount=payment.amount,
            settlement_count=0,
            total_net_amount=0,
            total_interchange_fee=0,
            total_tax_deducted=0,
            total_gross_settled=0,
            variance=0,
            status=SettlementReconciliationStatus.NOT_APPLICABLE,
        )

    linked_settlements = [s for s in settlements if s.payment_id == payment.payment_id]
    count = len(linked_settlements)
    
    total_net = sum(s.net_amount for s in linked_settlements)
    total_fee = sum(s.interchange_fee_deducted for s in linked_settlements)
    total_tax = sum(s.tax_deducted for s in linked_settlements)
    total_gross = total_net + total_fee + total_tax
    variance = total_gross - payment.amount

    if count == 0:
        status = SettlementReconciliationStatus.MISSING_SETTLEMENT
    elif variance == 0:
        if count == 1:
            status = SettlementReconciliationStatus.FULL_SETTLEMENT
        else:
            status = SettlementReconciliationStatus.PARTIAL_SETTLEMENT_COMPLETE
    elif variance < 0:
        status = SettlementReconciliationStatus.UNDER_SETTLED
    else:
        status = SettlementReconciliationStatus.OVER_SETTLED

    return SettlementAggregation(
        payment_id=payment.payment_id,
        expected_gross_amount=payment.amount,
        settlement_count=count,
        total_net_amount=total_net,
        total_interchange_fee=total_fee,
        total_tax_deducted=total_tax,
        total_gross_settled=total_gross,
        variance=variance,
        status=status,
        settlement_ids=[s.settlement_id for s in linked_settlements],
    )


def validate_settlement_totals(
    payment: GatewayTransaction,
    settlements: List[BankSettlementBatch],
) -> ControlResult:
    """Validates settlement totals against the payment expectation, handling partial tranches cleanly."""
    agg = aggregate_settlements_for_payment(payment, settlements)

    if agg.status == SettlementReconciliationStatus.NOT_APPLICABLE:
        return ControlResult(
            control_id=f"CTRL-SETTLE-TOTAL-{payment.payment_id}",
            control_name="Settlement Total Validation",
            status=ControlStatus.NOT_APPLICABLE,
            affected_record_ids=[payment.payment_id],
            rule="Settlement totals only evaluated for CAPTURED payments.",
            calculated_values={"reconciliation_status": agg.status.value},
        )

    is_reconciled = agg.status in (
        SettlementReconciliationStatus.FULL_SETTLEMENT,
        SettlementReconciliationStatus.PARTIAL_SETTLEMENT_COMPLETE,
    )

    ctrl_status = ControlStatus.PASS if is_reconciled else ControlStatus.FAIL
    severity = None if is_reconciled else ("HIGH" if agg.status != SettlementReconciliationStatus.UNDER_SETTLED else "MEDIUM")

    evidence = [
        EvidenceItem(
            source="gateway_transactions",
            record_id=payment.payment_id,
            field="amount",
            value=payment.amount,
        )
    ]
    for s_id in agg.settlement_ids:
        evidence.append(
            EvidenceItem(
                source="bank_settlement_batches",
                record_id=s_id,
                field="settlement_id",
                value=s_id,
                comparison=f"Included in {agg.settlement_count}-part aggregation",
            )
        )

    return ControlResult(
        control_id=f"CTRL-SETTLE-TOTAL-{payment.payment_id}",
        control_name="Settlement Total Validation",
        status=ctrl_status,
        severity=severity,
        affected_record_ids=[payment.payment_id] + agg.settlement_ids,
        rule="Total aggregated settlement gross amount must exactly equal payment amount.",
        calculated_values={
            "reconciliation_status": agg.status.value,
            "expected_gross_amount": agg.expected_gross_amount,
            "settlement_count": agg.settlement_count,
            "total_net_amount": agg.total_net_amount,
            "total_interchange_fee": agg.total_interchange_fee,
            "total_tax_deducted": agg.total_tax_deducted,
            "total_gross_settled": agg.total_gross_settled,
            "variance": agg.variance,
        },
        expected_values={"expected_gross_amount": agg.expected_gross_amount},
        actual_values={"total_gross_settled": agg.total_gross_settled, "status": agg.status.value},
        evidence=evidence,
    )
