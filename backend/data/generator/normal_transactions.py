"""Normal financial transaction generator.

Generates standard, clean financial lifecycles across diverse scenarios:
- Successful captured and settled payments
- Failed/cancelled payments with no contradictory downstream records
- Normal single refunds
- Normal single chargebacks
- Normal chargeback reversals
"""
from datetime import timedelta

from backend.data.generator.context import GenerationContext
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
)
from backend.models.enums import (
    PaymentStatus,
    PaymentMethod,
    CardType,
    OrderFulfillmentStatus,
    DisputeEventType,
    LedgerEntryType,
)


def generate_normal_transactions(ctx: GenerationContext, count: int) -> None:
    """Generates a mix of normal, structurally consistent financial lifecycles."""
    for idx in range(count):
        lifecycle_type = ctx.rng.choices(
            ["CAPTURED_SETTLED", "FAILED_CLEAN", "NORMAL_REFUND", "NORMAL_CHARGEBACK"],
            weights=[70, 15, 10, 5],
            k=1,
        )[0]

        payment_id = ctx.ids.next_payment_id()
        order_id = ctx.ids.next_order_id()
        merchant_id = ctx.random_merchant()
        acquirer = ctx.random_acquirer()
        amount = ctx.random_amount(min_inr=500, max_inr=45000)

        t_order = ctx.config.base_timestamp + timedelta(hours=idx * 2, minutes=ctx.rng.randint(0, 50))
        t_payment = t_order + timedelta(minutes=ctx.rng.randint(1, 10))

        if lifecycle_type == "FAILED_CLEAN":
            # Failed transaction with no downstream settlements
            order = MerchantOrder(
                order_id=order_id,
                payment_id_reference=payment_id,
                customer_id=f"cust_{ctx.rng.randint(1000, 9999)}",
                fulfillment_status=OrderFulfillmentStatus.CANCELLED.value,
                order_amount=amount,
                created_at=t_order,
            )
            ctx.merchant_orders.append(order)

            tx = GatewayTransaction(
                payment_id=payment_id,
                merchant_id=merchant_id,
                amount=amount,
                currency=ctx.config.currency,
                status=PaymentStatus.FAILED.value,
                created_at=t_payment,
                method=ctx.rng.choice([PaymentMethod.CARD.value, PaymentMethod.UPI.value]),
                card_type=CardType.DEBIT.value,
                error_code="INSUFFICIENT_FUNDS",
            )
            ctx.gateway_transactions.append(tx)
            continue

        # For all captured flows:
        order = MerchantOrder(
            order_id=order_id,
            payment_id_reference=payment_id,
            customer_id=f"cust_{ctx.rng.randint(1000, 9999)}",
            fulfillment_status=OrderFulfillmentStatus.FULFILLED.value,
            order_amount=amount,
            created_at=t_order,
        )
        ctx.merchant_orders.append(order)

        method = ctx.rng.choice([PaymentMethod.CARD.value, PaymentMethod.UPI.value, PaymentMethod.NETBANKING.value])
        card_type = CardType.CREDIT.value if method == PaymentMethod.CARD.value else None

        status = PaymentStatus.CAPTURED.value
        if lifecycle_type == "NORMAL_REFUND":
            status = PaymentStatus.REFUNDED.value
        elif lifecycle_type == "NORMAL_CHARGEBACK":
            status = PaymentStatus.DISPUTED.value

        tx = GatewayTransaction(
            payment_id=payment_id,
            merchant_id=merchant_id,
            amount=amount,
            currency=ctx.config.currency,
            status=status,
            created_at=t_payment,
            method=method,
            card_type=card_type,
            auth_code=f"AUTH_{ctx.rng.randint(100000, 999999)}",
        )
        ctx.gateway_transactions.append(tx)

        # Settlement clears within normal window (4-18 hours)
        t_settle = t_payment + timedelta(hours=ctx.rng.randint(4, 18))
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

        ctx.add_ledger_entry(
            transaction_id=payment_id,
            debit=0,
            credit=net,
            timestamp=t_settle + timedelta(minutes=5),
            entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
            reference=f"Standard settlement credit for {payment_id}",
        )

        if lifecycle_type == "NORMAL_REFUND":
            t_ref = t_settle + timedelta(days=ctx.rng.randint(1, 3))
            ref_event = DisputeRefundEvent(
                event_id=ctx.ids.next_dispute_event_id(),
                payment_id=payment_id,
                event_type=DisputeEventType.REFUND.value,
                amount=amount,
                timestamp=t_ref,
                reason_code="CUSTOMER_REQUESTED_REFUND",
            )
            ctx.dispute_events.append(ref_event)

            ctx.add_ledger_entry(
                transaction_id=payment_id,
                debit=amount,
                credit=0,
                timestamp=t_ref + timedelta(minutes=5),
                entry_type=LedgerEntryType.REFUND_DEBIT.value,
                reference=f"Standard refund payout for {payment_id}",
            )

        elif lifecycle_type == "NORMAL_CHARGEBACK":
            t_cb = t_settle + timedelta(days=ctx.rng.randint(2, 5))
            cb_event = DisputeRefundEvent(
                event_id=ctx.ids.next_dispute_event_id(),
                payment_id=payment_id,
                event_type=DisputeEventType.CHARGEBACK.value,
                amount=amount,
                timestamp=t_cb,
                reason_code="DISPUTE_FRAUD_INVESTIGATION",
            )
            ctx.dispute_events.append(cb_event)

            ctx.add_ledger_entry(
                transaction_id=payment_id,
                debit=amount,
                credit=0,
                timestamp=t_cb + timedelta(minutes=5),
                entry_type=LedgerEntryType.DISPUTE_HOLD.value,
                reference=f"Standard chargeback dispute hold for {payment_id}",
            )
