"""Scenario 3: Genuine Settlement SLA Breach Generator.

Generates captured transactions where settlement fails to clear within the
configured synthetic SLA processing window.
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


def generate_sla_breach_scenario(ctx: GenerationContext, index: int) -> None:
    """Generates an SLA breach anomaly case with ground truth."""
    payment_id = ctx.ids.next_payment_id()
    order_id = ctx.ids.next_order_id()
    case_id = ctx.ids.next_case_id("SLA")
    
    amount = ctx.random_amount(min_inr=5000, max_inr=35000)
    merchant_id = ctx.random_merchant()
    acquirer = ctx.random_acquirer()
    
    # Start on Monday (base Saturday + 2 days)
    t_order = ctx.config.base_timestamp + timedelta(days=2 + (index * 3))
    t_payment = t_order + timedelta(minutes=10)
    # SLA is 24 hours. Settlement arrives after 54 hours (severe SLA breach)
    t_late_settle = t_payment + timedelta(hours=54)
    
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
    
    # 3. Late Settlement Batch (exceeding 24h SLA)
    fee = int(amount * 0.01)
    tax = int(fee * 0.18)
    net = amount - fee - tax
    
    settlement = BankSettlementBatch(
        settlement_id=ctx.ids.next_settlement_id(),
        utr_number=ctx.ids.next_utr_number(acquirer["code"]),
        acquirer_id=acquirer["id"],
        raw_payment_reference=f"RAW-LATE-SLA-{payment_id}",
        payment_id=payment_id,
        net_amount=net,
        interchange_fee_deducted=fee,
        tax_deducted=tax,
        clearing_timestamp=t_late_settle,
        created_at=t_late_settle,
    )
    ctx.settlement_batches.append(settlement)
    
    # 4. Nodal Ledger Posting
    ctx.add_ledger_entry(
        transaction_id=payment_id,
        debit=0,
        credit=net,
        timestamp=t_late_settle + timedelta(minutes=5),
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        reference=f"Delayed settlement credit for {payment_id}",
    )
    
    # 5. Ground Truth Record
    gt = EvaluationGroundTruth(
        case_id=case_id,
        anomaly_type=ExceptionType.SETTLEMENT_SLA_BREACH.value,
        expected_root_cause="Captured payment has no valid settlement within the configured synthetic processing window.",
        expected_exposure=amount,
        expected_resolution_class="ESCALATE",
        expected_verification_state="FAILED_ESCALATED",
        created_at=t_payment + timedelta(hours=ctx.config.sla_hours),
    )
    ctx.ground_truth_cases.append(gt)
