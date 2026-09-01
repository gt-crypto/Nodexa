"""Scenario 1: Ghost Settlement Generator.

Generates transactions where gateway payment failed and order cancelled,
yet bank settlement and nodal ledger credit were posted.
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


def generate_ghost_settlement_scenario(ctx: GenerationContext, index: int) -> None:
    """Generates a ghost settlement anomaly case with associated ground truth."""
    payment_id = ctx.ids.next_payment_id()
    order_id = ctx.ids.next_order_id()
    case_id = ctx.ids.next_case_id("GHOST")
    
    amount = ctx.random_amount(min_inr=10000, max_inr=60000)  # e.g. ₹45,000.00
    merchant_id = ctx.random_merchant()
    acquirer = ctx.random_acquirer()
    
    t_order = ctx.config.base_timestamp + timedelta(hours=index * 4)
    t_payment = t_order + timedelta(minutes=2)
    t_settle = t_payment + timedelta(hours=14)
    
    # 1. Merchant Order: Cancelled
    order = MerchantOrder(
        order_id=order_id,
        payment_id_reference=payment_id,
        customer_id=f"cust_{ctx.rng.randint(1000, 9999)}",
        fulfillment_status=OrderFulfillmentStatus.CANCELLED.value,
        order_amount=amount,
        created_at=t_order,
    )
    ctx.merchant_orders.append(order)
    
    # 2. Gateway Transaction: Failed
    tx = GatewayTransaction(
        payment_id=payment_id,
        merchant_id=merchant_id,
        amount=amount,
        currency=ctx.config.currency,
        status=PaymentStatus.FAILED.value,
        created_at=t_payment,
        method=PaymentMethod.CARD.value,
        card_type=CardType.CREDIT.value,
        auth_code=None,
        error_code="GATEWAY_TIMED_OUT",
    )
    ctx.gateway_transactions.append(tx)
    
    # 3. Bank Settlement Batch: Inconsistency (funds cleared despite failure)
    fee = int(amount * 0.015)  # 1.5% fee
    tax = int(fee * 0.18)      # 18% GST
    net = amount - fee - tax
    
    settlement = BankSettlementBatch(
        settlement_id=ctx.ids.next_settlement_id(),
        utr_number=ctx.ids.next_utr_number(acquirer["code"]),
        acquirer_id=acquirer["id"],
        raw_payment_reference=f"RAW-GHOST-{payment_id}",
        payment_id=payment_id,
        net_amount=net,
        interchange_fee_deducted=fee,
        tax_deducted=tax,
        clearing_timestamp=t_settle,
        created_at=t_settle,
    )
    ctx.settlement_batches.append(settlement)
    
    # 4. Nodal Ledger: Money received
    ctx.add_ledger_entry(
        transaction_id=payment_id,
        debit=0,
        credit=net,
        timestamp=t_settle + timedelta(minutes=5),
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        reference=f"Ghost settlement credit for {payment_id}",
    )
    
    # 5. Ground Truth Record (Isolated)
    gt = EvaluationGroundTruth(
        case_id=case_id,
        anomaly_type=ExceptionType.GHOST_SETTLEMENT.value,
        expected_root_cause="Gateway/order state indicates failure or cancellation while bank and nodal records show settlement funds.",
        expected_exposure=amount,
        expected_resolution_class="EVIDENCE_DISPUTE_PACKET",
        expected_verification_state="VERIFIED_CLOSED",
        created_at=t_settle,
    )
    ctx.ground_truth_cases.append(gt)
