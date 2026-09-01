"""Scenario 4: Legitimate Partial/Asynchronous Settlement Generator.

Generates transactions where settlement is legitimately split across multiple
batches, aggregating exactly to the expected total.
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


def generate_partial_settlement_scenario(ctx: GenerationContext, index: int) -> None:
    """Generates a legitimate partial settlement case with ground truth."""
    payment_id = ctx.ids.next_payment_id()
    order_id = ctx.ids.next_order_id()
    case_id = ctx.ids.next_case_id("PARTIAL")
    
    total_amount = 1_000_000  # ₹10,000.00
    merchant_id = ctx.random_merchant()
    acquirer = ctx.random_acquirer()
    
    t_order = ctx.config.base_timestamp + timedelta(days=index * 2, hours=3)
    t_payment = t_order + timedelta(minutes=5)
    
    # 1. Order: Fulfilled
    order = MerchantOrder(
        order_id=order_id,
        payment_id_reference=payment_id,
        customer_id=f"cust_{ctx.rng.randint(1000, 9999)}",
        fulfillment_status=OrderFulfillmentStatus.FULFILLED.value,
        order_amount=total_amount,
        created_at=t_order,
    )
    ctx.merchant_orders.append(order)
    
    # 2. Gateway Transaction: Captured
    tx = GatewayTransaction(
        payment_id=payment_id,
        merchant_id=merchant_id,
        amount=total_amount,
        currency=ctx.config.currency,
        status=PaymentStatus.CAPTURED.value,
        created_at=t_payment,
        method=PaymentMethod.CARD.value,
        card_type=CardType.DEBIT.value,
        auth_code=f"AUTH_{ctx.rng.randint(100000, 999999)}",
    )
    ctx.gateway_transactions.append(tx)
    
    # 3. Three Partial Settlement Batches: 4,000 + 3,000 + 3,000 = 10,000
    split_amounts = [400_000, 300_000, 300_000]
    total_net = 0
    
    for part_idx, part_gross in enumerate(split_amounts, start=1):
        fee = int(part_gross * 0.015)
        tax = int(fee * 0.18)
        net = part_gross - fee - tax
        total_net += net
        t_part_settle = t_payment + timedelta(hours=6 * part_idx)
        
        batch = BankSettlementBatch(
            settlement_id=ctx.ids.next_settlement_id(),
            utr_number=ctx.ids.next_utr_number(acquirer["code"]),
            acquirer_id=acquirer["id"],
            raw_payment_reference=f"RAW-PART-{payment_id}-P{part_idx}",
            payment_id=payment_id,
            net_amount=net,
            interchange_fee_deducted=fee,
            tax_deducted=tax,
            clearing_timestamp=t_part_settle,
            created_at=t_part_settle,
        )
        ctx.settlement_batches.append(batch)
        
        ctx.add_ledger_entry(
            transaction_id=payment_id,
            debit=0,
            credit=net,
            timestamp=t_part_settle + timedelta(minutes=5),
            entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
            reference=f"Partial settlement tranche {part_idx}/3 for {payment_id}",
        )
    
    # 4. Ground Truth: Legitimate financial pattern, expected exposure = 0
    gt = EvaluationGroundTruth(
        case_id=case_id,
        anomaly_type=ExceptionType.PARTIAL_SETTLEMENT.value,
        expected_root_cause="Settlement is legitimately distributed across multiple records whose aggregate matches the payment.",
        expected_exposure=0,  # Legitimate split, zero exposure
        expected_resolution_class="NO_ACTION",
        expected_verification_state="NO_ACTION_REQUIRED",
        created_at=t_payment + timedelta(hours=18),
    )
    ctx.ground_truth_cases.append(gt)
