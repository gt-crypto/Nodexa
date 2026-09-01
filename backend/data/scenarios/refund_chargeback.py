"""Scenario 2: Refund + Chargeback Double-Dip Generator.

Generates transactions where merchant issued a refund, but an overlapping
chargeback was subsequently deducted, creating dual financial liability.
"""
from datetime import timedelta

from backend.data.generator.context import GenerationContext
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
)
from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.enums import (
    PaymentStatus,
    PaymentMethod,
    CardType,
    OrderFulfillmentStatus,
    DisputeEventType,
    LedgerEntryType,
    ExceptionType,
)


def generate_refund_chargeback_scenario(ctx: GenerationContext, index: int) -> None:
    """Generates a refund + chargeback double-dip anomaly case with ground truth."""
    payment_id = ctx.ids.next_payment_id()
    order_id = ctx.ids.next_order_id()
    case_id = ctx.ids.next_case_id("REFUND-CB")
    
    amount = ctx.random_amount(min_inr=15000, max_inr=50000)  # e.g. ₹50,000.00
    merchant_id = ctx.random_merchant()
    acquirer = ctx.random_acquirer()
    
    t_order = ctx.config.base_timestamp + timedelta(days=index * 2)
    t_payment = t_order + timedelta(minutes=5)
    t_settle = t_payment + timedelta(hours=18)
    t_refund = t_settle + timedelta(days=2)
    t_chargeback = t_refund + timedelta(days=3)  # Chargeback arrives 3 days after refund
    
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
    
    # 2. Gateway Transaction: Captured (then disputed)
    tx = GatewayTransaction(
        payment_id=payment_id,
        merchant_id=merchant_id,
        amount=amount,
        currency=ctx.config.currency,
        status=PaymentStatus.DISPUTED.value,
        created_at=t_payment,
        method=PaymentMethod.CARD.value,
        card_type=CardType.CREDIT.value,
        auth_code=f"AUTH_{ctx.rng.randint(100000, 999999)}",
    )
    ctx.gateway_transactions.append(tx)
    
    # 3. Normal Settlement
    fee = int(amount * 0.015)
    tax = int(fee * 0.18)
    net = amount - fee - tax
    
    settlement = BankSettlementBatch(
        settlement_id=ctx.ids.next_settlement_id(),
        utr_number=ctx.ids.next_utr_number(acquirer["code"]),
        acquirer_id=acquirer["id"],
        raw_payment_reference=f"RAW-SETTLE-{payment_id}",
        payment_id=payment_id,
        net_amount=net,
        interchange_fee_deducted=fee,
        tax_deducted=tax,
        clearing_timestamp=t_settle,
        created_at=t_settle,
    )
    ctx.settlement_batches.append(settlement)
    
    # 4. Nodal Ledger: Initial settlement credit
    ctx.add_ledger_entry(
        transaction_id=payment_id,
        debit=0,
        credit=net,
        timestamp=t_settle + timedelta(minutes=5),
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        reference=f"Initial settlement credit for {payment_id}",
    )
    
    # 5. Refund Event & Ledger Debit
    ref_event = DisputeRefundEvent(
        event_id=ctx.ids.next_dispute_event_id(),
        payment_id=payment_id,
        event_type=DisputeEventType.REFUND.value,
        amount=amount,
        timestamp=t_refund,
        reason_code="MERCHANT_CUSTOMER_RETURN",
    )
    ctx.dispute_events.append(ref_event)
    
    ctx.add_ledger_entry(
        transaction_id=payment_id,
        debit=amount,
        credit=0,
        timestamp=t_refund + timedelta(minutes=5),
        entry_type=LedgerEntryType.REFUND_DEBIT.value,
        reference=f"Customer refund payout for {payment_id}",
    )
    
    # 6. Chargeback Event & Ledger Debit (Double Dip)
    cb_event = DisputeRefundEvent(
        event_id=ctx.ids.next_dispute_event_id(),
        payment_id=payment_id,
        event_type=DisputeEventType.CHARGEBACK.value,
        amount=amount,
        timestamp=t_chargeback,
        reason_code="CARDHOLDER_DISPUTE_UNRECOGNIZED",
    )
    ctx.dispute_events.append(cb_event)
    
    ctx.add_ledger_entry(
        transaction_id=payment_id,
        debit=amount,
        credit=0,
        timestamp=t_chargeback + timedelta(minutes=5),
        entry_type=LedgerEntryType.DISPUTE_HOLD.value,
        reference=f"Overlapping chargeback hold for {payment_id}",
    )
    
    # 7. Ground Truth Record
    gt = EvaluationGroundTruth(
        case_id=case_id,
        anomaly_type=ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value,
        expected_root_cause="Refund and chargeback financial liabilities overlap for the same payment.",
        expected_exposure=amount,
        expected_resolution_class="RECOMMEND_ONLY",
        expected_verification_state="VERIFIED_CLOSED",
        created_at=t_chargeback,
    )
    ctx.ground_truth_cases.append(gt)
