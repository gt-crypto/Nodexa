"""Tests for financial source models, relationships, business identifiers, and monetary precision."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.exc import IntegrityError

from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.enums import (
    PaymentStatus,
    PaymentMethod,
    CardType,
    DisputeEventType,
    LedgerEntryType,
    OrderFulfillmentStatus,
)
from backend.services.repositories import FinancialSourceRepository


def utc_now():
    return datetime.now(timezone.utc)


def test_gateway_transaction_crud_and_retrieval(db_session):
    """Verify inserting and retrieving gateway transaction records."""
    repo = FinancialSourceRepository(db_session)

    tx = GatewayTransaction(
        payment_id="pay_gw_1001",
        merchant_id="mer_acme_corp",
        amount=150000,  # ₹1500.00 in paisa
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=utc_now(),
        method=PaymentMethod.CARD.value,
        card_type=CardType.CREDIT.value,
        auth_code="AUTH_998811",
    )
    repo.add_gateway_transaction(tx)

    fetched = repo.get_gateway_transaction("pay_gw_1001")
    assert fetched is not None
    assert fetched.payment_id == "pay_gw_1001"
    assert fetched.amount == 150000
    assert fetched.currency == "INR"
    assert fetched.merchant_id == "mer_acme_corp"
    assert fetched.status == PaymentStatus.CAPTURED.value


def test_payment_id_uniqueness_constraint(db_session):
    """Verify that duplicate business payment_id raises IntegrityError."""
    repo = FinancialSourceRepository(db_session)

    tx1 = GatewayTransaction(
        payment_id="pay_unique_test",
        merchant_id="mer_001",
        amount=50000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=utc_now(),
        method=PaymentMethod.UPI.value,
    )
    repo.add_gateway_transaction(tx1)

    tx2 = GatewayTransaction(
        payment_id="pay_unique_test",
        merchant_id="mer_002",
        amount=75000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=utc_now(),
        method=PaymentMethod.CARD.value,
    )
    with pytest.raises(IntegrityError):
        repo.add_gateway_transaction(tx2)


def test_multiple_settlements_for_single_payment(db_session):
    """Verify one payment can be settled across multiple settlement batches (partial settlement)."""
    repo = FinancialSourceRepository(db_session)

    tx = GatewayTransaction(
        payment_id="pay_split_settle_01",
        merchant_id="mer_retail_inc",
        amount=100000,  # ₹1000.00
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=utc_now(),
        method=PaymentMethod.CARD.value,
    )
    repo.add_gateway_transaction(tx)

    # Batch 1: Partial settlement of ₹600.00
    batch1 = BankSettlementBatch(
        settlement_id="stl_batch_part_01",
        utr_number="UTR_HDFC_001",
        acquirer_id="acq_hdfc",
        payment_id="pay_split_settle_01",
        net_amount=58800,  # ₹588.00 after fee
        interchange_fee_deducted=1000,  # ₹10.00
        tax_deducted=200,  # ₹2.00
        clearing_timestamp=utc_now(),
    )
    # Batch 2: Partial settlement of ₹400.00
    batch2 = BankSettlementBatch(
        settlement_id="stl_batch_part_02",
        utr_number="UTR_HDFC_002",
        acquirer_id="acq_hdfc",
        payment_id="pay_split_settle_01",
        net_amount=39200,  # ₹392.00 after fee
        interchange_fee_deducted=700,
        tax_deducted=100,
        clearing_timestamp=utc_now(),
    )
    repo.add_settlement_batch(batch1)
    repo.add_settlement_batch(batch2)

    settlements = repo.list_settlements_for_payment("pay_split_settle_01")
    assert len(settlements) == 2
    total_net = sum(s.net_amount for s in settlements)
    assert total_net == 58800 + 39200


def test_merchant_order_relationship(db_session):
    """Verify merchant orders linked to payment_id."""
    repo = FinancialSourceRepository(db_session)

    tx = GatewayTransaction(
        payment_id="pay_ord_link_01",
        merchant_id="mer_ecommerce",
        amount=250000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=utc_now(),
        method=PaymentMethod.NETBANKING.value,
    )
    repo.add_gateway_transaction(tx)

    order = MerchantOrder(
        order_id="ord_shopify_9921",
        payment_id_reference="pay_ord_link_01",
        customer_id="cust_rahul_sharma",
        fulfillment_status=OrderFulfillmentStatus.FULFILLED.value,
        order_amount=250000,
    )
    repo.add_merchant_order(order)

    fetched_orders = repo.list_orders_for_payment("pay_ord_link_01")
    assert len(fetched_orders) == 1
    assert fetched_orders[0].order_id == "ord_shopify_9921"
    assert fetched_orders[0].order_amount == 250000


def test_multiple_dispute_and_refund_events_for_payment(db_session):
    """Verify multiple dispute/refund events (e.g., partial refund followed by chargeback) on a single payment."""
    repo = FinancialSourceRepository(db_session)

    tx = GatewayTransaction(
        payment_id="pay_dispute_multi_01",
        merchant_id="mer_travel_portal",
        amount=500000,  # ₹5000.00
        currency="INR",
        status=PaymentStatus.DISPUTED.value,
        created_at=utc_now(),
        method=PaymentMethod.CARD.value,
    )
    repo.add_gateway_transaction(tx)

    # Event 1: Partial refund
    evt1 = DisputeRefundEvent(
        event_id="evt_ref_001",
        payment_id="pay_dispute_multi_01",
        event_type=DisputeEventType.REFUND.value,
        amount=200000,  # ₹2000.00
        reason_code="CUSTOMER_CANCELLED",
    )
    # Event 2: Chargeback on remainder
    evt2 = DisputeRefundEvent(
        event_id="evt_cb_002",
        payment_id="pay_dispute_multi_01",
        event_type=DisputeEventType.CHARGEBACK.value,
        amount=300000,  # ₹3000.00
        reason_code="FRAUD_REPORTED",
    )
    repo.add_dispute_event(evt1)
    repo.add_dispute_event(evt2)

    events = repo.list_dispute_events_for_payment("pay_dispute_multi_01")
    assert len(events) == 2
    assert {e.event_type for e in events} == {DisputeEventType.REFUND.value, DisputeEventType.CHARGEBACK.value}


def test_multiple_nodal_ledger_entries_for_payment(db_session):
    """Verify multiple double-entry ledger postings for a single payment (credit & fee debit)."""
    repo = FinancialSourceRepository(db_session)

    tx = GatewayTransaction(
        payment_id="pay_ledger_flow_01",
        merchant_id="mer_fintech",
        amount=1000000,  # ₹10,000.00
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=utc_now(),
        method=PaymentMethod.UPI.value,
    )
    repo.add_gateway_transaction(tx)

    # Entry 1: Nodal escrow settlement credit
    entry1 = NodalLedgerEntry(
        ledger_id="led_ent_001",
        transaction_id="pay_ledger_flow_01",
        account_id="nodal_escrow_main",
        debit=0,
        credit=1000000,
        balance_after=1000000,
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        reference="Inward UPI settlement credit",
    )
    # Entry 2: Platform fee debit
    entry2 = NodalLedgerEntry(
        ledger_id="led_ent_002",
        transaction_id="pay_ledger_flow_01",
        account_id="nodal_escrow_main",
        debit=20000,  # ₹200.00 fee
        credit=0,
        balance_after=980000,
        entry_type=LedgerEntryType.FEE_DEBIT.value,
        reference="Payment gateway processing fee debit",
    )
    repo.add_ledger_entry(entry1)
    repo.add_ledger_entry(entry2)

    entries = repo.list_ledger_entries_for_transaction("pay_ledger_flow_01")
    assert len(entries) == 2
    assert entries[0].credit == 1000000
    assert entries[1].debit == 20000
    assert entries[1].balance_after == 980000


def test_monetary_exact_precision_without_float_drift(db_session):
    """Verify integer minor unit storage eliminates floating-point representation errors."""
    repo = FinancialSourceRepository(db_session)

    # In IEEE-754 floats: 0.1 + 0.2 != 0.3 (0.30000000000000004)
    # In integer minor units: 10 + 20 == 30 exactly
    tx = GatewayTransaction(
        payment_id="pay_precision_test",
        merchant_id="mer_precision",
        amount=10 + 20,  # 30 minor units
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=utc_now(),
        method=PaymentMethod.UPI.value,
    )
    repo.add_gateway_transaction(tx)

    fetched = repo.get_gateway_transaction("pay_precision_test")
    assert fetched.amount == 30
    assert isinstance(fetched.amount, int)
    assert fetched.amount != 30.000000000000004
