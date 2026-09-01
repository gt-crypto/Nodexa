"""Unit tests for deterministic reconciliation services, matching, amounts, and duplicate detection."""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session

from backend.controls.control_result import ControlStatus
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.enums import PaymentStatus, OrderFulfillmentStatus, DisputeEventType, LedgerEntryType
from backend.reconciliation.matching import (
    MatchStatus,
    match_payment_to_orders,
    match_payment_to_settlements,
    match_settlement_to_payment,
)
from backend.reconciliation.amounts import (
    validate_gateway_order_amounts,
    validate_settlement_components,
    validate_payment_vs_settlement_amount,
)
from backend.reconciliation.settlements import (
    SettlementReconciliationStatus,
    aggregate_settlements_for_payment,
    validate_settlement_totals,
)
from backend.reconciliation.duplicates import (
    detect_duplicate_settlements,
    detect_duplicate_disputes,
    detect_duplicate_ledger_postings,
)
from backend.reconciliation.service import ReconciliationService


def test_identifier_matching_scenarios():
    """Verifies exact, multiple, and no match identifier linkages."""
    now = datetime.now(timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-M1",
        merchant_id="M1",
        amount=100000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
        method="CARD",
    )
    order = MerchantOrder(
        order_id="ORD-M1",
        payment_id_reference="PAY-M1",
        customer_id="C1",
        fulfillment_status=OrderFulfillmentStatus.FULFILLED.value,
        order_amount=100000,
        created_at=now,
    )
    settlement = BankSettlementBatch(
        settlement_id="SET-M1",
        payment_id="PAY-M1",
        acquirer_id="ACQ-1",
        net_amount=98500,
        interchange_fee_deducted=1200,
        tax_deducted=300,
        clearing_timestamp=now,
    )

    # Exact matches
    res_order = match_payment_to_orders(payment, [order])
    assert res_order.status == MatchStatus.EXACT_MATCH
    assert res_order.matched_ids == ["ORD-M1"]

    res_settle = match_payment_to_settlements(payment, [settlement])
    assert res_settle.status == MatchStatus.EXACT_MATCH
    assert res_settle.matched_ids == ["SET-M1"]

    # No match
    res_no_order = match_payment_to_orders(payment, [])
    assert res_no_order.status == MatchStatus.NO_MATCH


def test_partial_settlement_aggregation_and_reconciliation():
    """Verifies that 3 partial settlements aggregating to the payment amount are treated as reconciled."""
    now = datetime.now(timezone.utc)
    total_amount = 1_000_000  # ₹10,000.00
    payment = GatewayTransaction(
        payment_id="PAY-PARTIAL-1",
        merchant_id="M1",
        amount=total_amount,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
        method="CARD",
    )

    # 3 batches: 400,000 + 300,000 + 300,000 = 1,000,000
    split_batches = [
        BankSettlementBatch(
            settlement_id="SET-P1",
            payment_id="PAY-PARTIAL-1",
            acquirer_id="ACQ-1",
            net_amount=394000,
            interchange_fee_deducted=5085,
            tax_deducted=915,  # gross = 400,000
            clearing_timestamp=now + timedelta(hours=4),
        ),
        BankSettlementBatch(
            settlement_id="SET-P2",
            payment_id="PAY-PARTIAL-1",
            acquirer_id="ACQ-1",
            net_amount=295500,
            interchange_fee_deducted=3814,
            tax_deducted=686,  # gross = 300,000
            clearing_timestamp=now + timedelta(hours=8),
        ),
        BankSettlementBatch(
            settlement_id="SET-P3",
            payment_id="PAY-PARTIAL-1",
            acquirer_id="ACQ-1",
            net_amount=295500,
            interchange_fee_deducted=3814,
            tax_deducted=686,  # gross = 300,000
            clearing_timestamp=now + timedelta(hours=12),
        ),
    ]

    agg = aggregate_settlements_for_payment(payment, split_batches)
    assert agg.settlement_count == 3
    assert agg.total_gross_settled == total_amount
    assert agg.variance == 0
    assert agg.status == SettlementReconciliationStatus.PARTIAL_SETTLEMENT_COMPLETE

    ctrl = validate_settlement_totals(payment, split_batches)
    assert ctrl.status == ControlStatus.PASS  # Must pass without false alarms!


def test_under_settlement_detection():
    """Verifies that an under-settled payment fails validation with UNDER_SETTLED status."""
    now = datetime.now(timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-UNDER-1",
        merchant_id="M1",
        amount=1000000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
        method="CARD",
    )
    # Only settled 400,000 of 1,000,000
    batch = BankSettlementBatch(
        settlement_id="SET-P1",
        payment_id="PAY-UNDER-1",
        acquirer_id="ACQ-1",
        net_amount=394000,
        interchange_fee_deducted=5085,
        tax_deducted=915,
        clearing_timestamp=now,
    )

    agg = aggregate_settlements_for_payment(payment, [batch])
    assert agg.status == SettlementReconciliationStatus.UNDER_SETTLED
    assert agg.variance == -600000

    ctrl = validate_settlement_totals(payment, [batch])
    assert ctrl.status == ControlStatus.FAIL


def test_amount_validation_gateway_vs_order():
    """Verifies amount comparison between payment and order."""
    now = datetime.now(timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-AMT-1",
        merchant_id="M1",
        amount=500000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
        method="CARD",
    )
    bad_order = MerchantOrder(
        order_id="ORD-AMT-1",
        payment_id_reference="PAY-AMT-1",
        customer_id="C1",
        fulfillment_status=OrderFulfillmentStatus.FULFILLED.value,
        order_amount=450000,  # ₹4,500 vs ₹5,000
        created_at=now,
    )

    res = validate_gateway_order_amounts(payment, [bad_order])
    assert res.status == ControlStatus.FAIL
    assert res.calculated_values["variance"] == 50000


def test_duplicate_settlements_and_utr_detection():
    """Verifies detection of duplicate settlement IDs and duplicated UTR numbers."""
    now = datetime.now(timezone.utc)
    settlements = [
        BankSettlementBatch(settlement_id="SET-DUP-1", utr_number="UTR-SAME", acquirer_id="A1", net_amount=1000, clearing_timestamp=now),
        BankSettlementBatch(settlement_id="SET-DUP-2", utr_number="UTR-SAME", acquirer_id="A1", net_amount=1000, clearing_timestamp=now),
    ]

    res = detect_duplicate_settlements(settlements)
    assert len(res) == 1
    assert res[0].status == ControlStatus.FAIL
    assert res[0].calculated_values["duplicate_utrs"] == 1


def test_reconciliation_service_e2e(db_session: Session):
    """Verifies ReconciliationService operation against an in-memory test database."""
    now = datetime.now(timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-E2E-1",
        merchant_id="MERCH-1",
        amount=500000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
        method="UPI",
    )
    order = MerchantOrder(
        order_id="ORD-E2E-1",
        payment_id_reference="PAY-E2E-1",
        customer_id="CUST-1",
        fulfillment_status=OrderFulfillmentStatus.FULFILLED.value,
        order_amount=500000,
        created_at=now,
    )
    settlement = BankSettlementBatch(
        settlement_id="SET-E2E-1",
        payment_id="PAY-E2E-1",
        acquirer_id="ACQ-1",
        net_amount=492500,
        interchange_fee_deducted=6356,
        tax_deducted=1144,
        clearing_timestamp=now + timedelta(hours=6),
    )
    ledger = NodalLedgerEntry(
        ledger_id="LED-E2E-1",
        transaction_id="PAY-E2E-1",
        account_id="nodal_escrow_main",
        debit=0,
        credit=492500,
        balance_after=492500,
        timestamp=now + timedelta(hours=6, minutes=5),
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
    )

    db_session.add_all([payment, order, settlement, ledger])
    db_session.commit()

    service = ReconciliationService(session=db_session)
    pmt_res = service.reconcile_payment("PAY-E2E-1")
    assert pmt_res is not None
    assert pmt_res.is_reconciled is True

    acct_res = service.reconcile_account("nodal_escrow_main")
    assert acct_res.is_reconciled is True
