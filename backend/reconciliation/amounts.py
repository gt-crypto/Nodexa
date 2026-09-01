"""Deterministic monetary amount validation across operational sources and ledger."""
from typing import Dict, List, Optional

from backend.controls.control_result import ControlResult, ControlStatus, EvidenceItem
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.enums import LedgerEntryType


def validate_gateway_order_amounts(
    payment: GatewayTransaction,
    orders: List[MerchantOrder],
) -> ControlResult:
    """Validates that gateway payment amount matches associated merchant order amount."""
    matching_orders = [o for o in orders if o.payment_id_reference == payment.payment_id]
    
    if not matching_orders:
        return ControlResult(
            control_id=f"CTRL-AMT-GW-ORDER-{payment.payment_id}",
            control_name="Gateway vs Order Amount Validation",
            status=ControlStatus.NOT_APPLICABLE,
            affected_record_ids=[payment.payment_id],
            rule="Gateway transaction must match referenced merchant order amount.",
            calculated_values={"matching_orders_count": 0},
        )

    order = matching_orders[0]
    is_match = payment.amount == order.order_amount
    variance = payment.amount - order.order_amount

    evidence = [
        EvidenceItem(
            source="gateway_transactions",
            record_id=payment.payment_id,
            field="amount",
            value=payment.amount,
        ),
        EvidenceItem(
            source="merchant_orders",
            record_id=order.order_id,
            field="order_amount",
            value=order.order_amount,
            comparison=f"Payment {payment.amount} == Order {order.order_amount} (variance: {variance})",
        ),
    ]

    return ControlResult(
        control_id=f"CTRL-AMT-GW-ORDER-{payment.payment_id}",
        control_name="Gateway vs Order Amount Validation",
        status=ControlStatus.PASS if is_match else ControlStatus.FAIL,
        severity="HIGH" if not is_match else None,
        affected_record_ids=[payment.payment_id, order.order_id],
        rule="Gateway payment amount must exactly equal merchant order amount.",
        calculated_values={
            "payment_amount": payment.amount,
            "order_amount": order.order_amount,
            "variance": variance,
        },
        expected_values={"amount": order.order_amount},
        actual_values={"amount": payment.amount},
        evidence=evidence,
    )


def validate_settlement_components(batch: BankSettlementBatch) -> ControlResult:
    """Validates internal financial consistency of a settlement batch line.
    
    Checks that:
    - net_amount, interchange_fee_deducted, and tax_deducted are non-negative.
    - Gross calculated = net_amount + interchange_fee_deducted + tax_deducted.
    """
    gross = batch.net_amount + batch.interchange_fee_deducted + batch.tax_deducted
    is_valid = (
        batch.net_amount >= 0 and
        batch.interchange_fee_deducted >= 0 and
        batch.tax_deducted >= 0 and
        gross > 0
    )

    evidence = [
        EvidenceItem(
            source="bank_settlement_batches",
            record_id=batch.settlement_id,
            field="net_amount",
            value=batch.net_amount,
        ),
        EvidenceItem(
            source="bank_settlement_batches",
            record_id=batch.settlement_id,
            field="interchange_fee_deducted",
            value=batch.interchange_fee_deducted,
        ),
        EvidenceItem(
            source="bank_settlement_batches",
            record_id=batch.settlement_id,
            field="tax_deducted",
            value=batch.tax_deducted,
            comparison=f"Calculated Gross = {gross} (Net {batch.net_amount} + Fee {batch.interchange_fee_deducted} + Tax {batch.tax_deducted})",
        ),
    ]

    return ControlResult(
        control_id=f"CTRL-AMT-SETTLE-COMPONENTS-{batch.settlement_id}",
        control_name="Settlement Component Validation",
        status=ControlStatus.PASS if is_valid else ControlStatus.FAIL,
        severity="MEDIUM" if not is_valid else None,
        affected_record_ids=[batch.settlement_id],
        rule="Settlement line components (net + fee + tax) must be non-negative and sum to gross.",
        calculated_values={
            "net_amount": batch.net_amount,
            "fee": batch.interchange_fee_deducted,
            "tax": batch.tax_deducted,
            "gross_amount": gross,
        },
        expected_values={"is_valid": True},
        actual_values={"is_valid": is_valid},
        evidence=evidence,
    )


def validate_payment_vs_settlement_amount(
    payment: GatewayTransaction,
    settlements: List[BankSettlementBatch],
) -> ControlResult:
    """Validates that the sum of gross settlement tranches equals the payment amount."""
    payment_settlements = [s for s in settlements if s.payment_id == payment.payment_id]
    
    if not payment_settlements:
        return ControlResult(
            control_id=f"CTRL-AMT-PMT-SETTLE-{payment.payment_id}",
            control_name="Payment vs Aggregated Settlement Amount",
            status=ControlStatus.WARNING,
            severity="MEDIUM",
            affected_record_ids=[payment.payment_id],
            rule="Sum of gross settlement tranches must match payment amount.",
            calculated_values={"settlement_count": 0, "total_gross_settled": 0},
            expected_values={"expected_amount": payment.amount},
            actual_values={"total_gross_settled": 0},
            evidence=[
                EvidenceItem(
                    source="gateway_transactions",
                    record_id=payment.payment_id,
                    field="amount",
                    value=payment.amount,
                    comparison="Zero settlement batches found for payment",
                )
            ],
        )

    total_net = sum(s.net_amount for s in payment_settlements)
    total_fee = sum(s.interchange_fee_deducted for s in payment_settlements)
    total_tax = sum(s.tax_deducted for s in payment_settlements)
    total_gross = total_net + total_fee + total_tax
    variance = total_gross - payment.amount

    is_match = variance == 0

    evidence = [
        EvidenceItem(
            source="gateway_transactions",
            record_id=payment.payment_id,
            field="amount",
            value=payment.amount,
        )
    ]
    for s in payment_settlements:
        evidence.append(
            EvidenceItem(
                source="bank_settlement_batches",
                record_id=s.settlement_id,
                field="net_amount/fee/tax",
                value={"net": s.net_amount, "fee": s.interchange_fee_deducted, "tax": s.tax_deducted},
                comparison=f"Tranche gross = {s.net_amount + s.interchange_fee_deducted + s.tax_deducted}",
            )
        )

    return ControlResult(
        control_id=f"CTRL-AMT-PMT-SETTLE-{payment.payment_id}",
        control_name="Payment vs Aggregated Settlement Amount",
        status=ControlStatus.PASS if is_match else ControlStatus.FAIL,
        severity="HIGH" if not is_match else None,
        affected_record_ids=[payment.payment_id] + [s.settlement_id for s in payment_settlements],
        rule="Sum of gross settlement tranches must match payment amount.",
        calculated_values={
            "payment_amount": payment.amount,
            "settlement_count": len(payment_settlements),
            "total_net": total_net,
            "total_fee": total_fee,
            "total_tax": total_tax,
            "total_gross_settled": total_gross,
            "variance": variance,
        },
        expected_values={"expected_amount": payment.amount},
        actual_values={"total_gross_settled": total_gross},
        evidence=evidence,
    )
