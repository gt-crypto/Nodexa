"""Scenario 5: Missing and Unallocated Settlement Generator.

Generates:
1. Missing settlements: Captured gateway payments with no settlement record.
2. Unallocated settlements: Bank settlement credits with no matching gateway payment.
"""
from datetime import timedelta

from backend.data.generator.context import GenerationContext
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
)
from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.enums import (
    PaymentStatus,
    PaymentMethod,
    CardType,
    OrderFulfillmentStatus,
    LedgerEntryType,
    ExceptionType,
)


def generate_missing_settlement_scenario(ctx: GenerationContext, index: int) -> None:
    """Generates a missing settlement case (captured payment, zero settlement records)."""
    payment_id = ctx.ids.next_payment_id()
    order_id = ctx.ids.next_order_id()
    case_id = ctx.ids.next_case_id("MISSING")
    
    amount = ctx.random_amount(min_inr=8000, max_inr=40000)
    merchant_id = ctx.random_merchant()
    
    t_order = ctx.config.base_timestamp + timedelta(days=index * 2, hours=5)
    t_payment = t_order + timedelta(minutes=3)
    
    # 1. Order: Fulfilled
    order = MerchantOrder(
        order_id=order_id,
        payment_id_reference=payment_id,
        customer_id=f"cust_{ctx.rng.randint(1000, 9999)}",
        fulfillment_status=OrderFulfillmentStatus.FULFILLED.value,
        order_amount=amount,
        created_at=t_order,
    )
    ctx.merchant_orders.append(order)
    
    # 2. Gateway Transaction: Captured
    tx = GatewayTransaction(
        payment_id=payment_id,
        merchant_id=merchant_id,
        amount=amount,
        currency=ctx.config.currency,
        status=PaymentStatus.CAPTURED.value,
        created_at=t_payment,
        method=PaymentMethod.UPI.value,
        card_type=None,
        auth_code=f"AUTH_{ctx.rng.randint(100000, 999999)}",
    )
    ctx.gateway_transactions.append(tx)
    
    # Intentionally NO settlement batch and NO ledger credit
    
    # 3. Ground Truth Record
    gt = EvaluationGroundTruth(
        case_id=case_id,
        anomaly_type=ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value,
        expected_root_cause="Captured payment has no valid downstream settlement.",
        expected_exposure=amount,
        expected_resolution_class="ESCALATE",
        expected_verification_state="FAILED_ESCALATED",
        created_at=t_payment + timedelta(hours=ctx.config.sla_hours),
    )
    ctx.ground_truth_cases.append(gt)


def generate_unallocated_settlement_scenario(ctx: GenerationContext, index: int) -> None:
    """Generates an unallocated settlement case (bank inflow exists with no payment mapping)."""
    settlement_id = ctx.ids.next_settlement_id()
    case_id = ctx.ids.next_case_id("UNALLOCATED")
    
    net_amount = ctx.random_amount(min_inr=12000, max_inr=50000)
    acquirer = ctx.random_acquirer()
    t_settle = ctx.config.base_timestamp + timedelta(days=index * 2, hours=8)
    
    # 1. Bank Settlement with NULL payment_id and unmapped reference
    settlement = BankSettlementBatch(
        settlement_id=settlement_id,
        utr_number=ctx.ids.next_utr_number(acquirer["code"]),
        acquirer_id=acquirer["id"],
        raw_payment_reference=f"RAW-UNMAPPED-ORPHAN-{settlement_id}",
        payment_id=None,  # Unallocated / orphan
        net_amount=net_amount,
        interchange_fee_deducted=int(net_amount * 0.012),
        tax_deducted=int(net_amount * 0.012 * 0.18),
        clearing_timestamp=t_settle,
        created_at=t_settle,
    )
    ctx.settlement_batches.append(settlement)
    
    # 2. Nodal Ledger Inflow
    ctx.add_ledger_entry(
        transaction_id=None,
        debit=0,
        credit=net_amount,
        timestamp=t_settle + timedelta(minutes=5),
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        reference=f"Unallocated settlement credit from {acquirer['id']} ref {settlement_id}",
    )
    
    # 3. Ground Truth Record
    gt = EvaluationGroundTruth(
        case_id=case_id,
        anomaly_type=ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value,
        expected_root_cause="Bank inflow exists but cannot be cleanly associated with a payment.",
        expected_exposure=net_amount,
        expected_resolution_class="HUMAN_APPROVAL_REQUIRED",
        expected_verification_state="VERIFIED_CLOSED",
        created_at=t_settle,
    )
    ctx.ground_truth_cases.append(gt)
