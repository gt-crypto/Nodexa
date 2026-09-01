"""Scenario 6: Legitimate Timing Exception Generator.

Generates transactions where settlement occurs near a weekend/cutoff boundary
and clears inside the next valid processing window.
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


def generate_timing_exception_scenario(ctx: GenerationContext, index: int) -> None:
    """Generates a legitimate timing exception case with ground truth."""
    payment_id = ctx.ids.next_payment_id()
    order_id = ctx.ids.next_order_id()
    case_id = ctx.ids.next_case_id("TIMING")
    
    amount = ctx.random_amount(min_inr=5000, max_inr=30000)
    merchant_id = ctx.random_merchant()
    acquirer = ctx.random_acquirer()
    
    # Friday 19:30 UTC (after daily 18:00 cutoff -> non-processing window until Monday 09:00 UTC)
    t_order = ctx.config.base_timestamp + timedelta(days=6 + (index * 7), hours=10, minutes=30)
    t_payment = t_order + timedelta(minutes=5)
    # Monday 09:30 UTC (next valid processing window)
    t_settle = t_payment + timedelta(hours=62)
    
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
        method=PaymentMethod.CARD.value,
        card_type=CardType.CREDIT.value,
        auth_code=f"AUTH_{ctx.rng.randint(100000, 999999)}",
    )
    ctx.gateway_transactions.append(tx)
    
    # 3. Bank Settlement Batch
    fee = int(amount * 0.015)
    tax = int(fee * 0.18)
    net = amount - fee - tax
    
    settlement = BankSettlementBatch(
        settlement_id=ctx.ids.next_settlement_id(),
        utr_number=ctx.ids.next_utr_number(acquirer["code"]),
        acquirer_id=acquirer["id"],
        raw_payment_reference=f"RAW-TIMING-{payment_id}",
        payment_id=payment_id,
        net_amount=net,
        interchange_fee_deducted=fee,
        tax_deducted=tax,
        clearing_timestamp=t_settle,
        created_at=t_settle,
    )
    ctx.settlement_batches.append(settlement)
    
    # 4. Nodal Ledger Posting
    ctx.add_ledger_entry(
        transaction_id=payment_id,
        debit=0,
        credit=net,
        timestamp=t_settle + timedelta(minutes=5),
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        reference=f"Next-window settlement credit for {payment_id}",
    )
    
    # 5. Ground Truth Record: Legitimate timing, exposure = 0
    gt = EvaluationGroundTruth(
        case_id=case_id,
        anomaly_type=ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value,
        expected_root_cause="Settlement occurs within the configured next-valid-processing window despite appearing late.",
        expected_exposure=0,
        expected_resolution_class="NO_ACTION",
        expected_verification_state="NO_ACTION_REQUIRED",
        created_at=t_settle,
    )
    ctx.ground_truth_cases.append(gt)
