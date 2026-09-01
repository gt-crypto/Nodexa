"""Unit tests verifying that normal transactions and legitimate edge cases produce ZERO false financial exceptions."""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session

from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.enums import PaymentStatus, OrderFulfillmentStatus, DisputeEventType, LedgerEntryType
from backend.exceptions.service import ExceptionDetectionService


def test_normal_successful_payment_zero_exceptions(db_session: Session):
    """Verifies that a standard captured and settled payment creates zero exceptions."""
    now = datetime(2026, 8, 4, 10, 0, 0, tzinfo=timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-NORM-1",
        merchant_id="M1",
        amount=1000000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
        method="UPI",
    )
    order = MerchantOrder(
        order_id="ORD-NORM-1",
        payment_id_reference="PAY-NORM-1",
        customer_id="C1",
        fulfillment_status=OrderFulfillmentStatus.FULFILLED.value,
        order_amount=1000000,
        created_at=now,
    )
    settlement = BankSettlementBatch(
        settlement_id="SET-NORM-1",
        payment_id="PAY-NORM-1",
        acquirer_id="A1",
        net_amount=985000,
        interchange_fee_deducted=12711,
        tax_deducted=2289,
        clearing_timestamp=now + timedelta(hours=6),
    )
    ledger = NodalLedgerEntry(
        ledger_id="LED-NORM-1",
        transaction_id="PAY-NORM-1",
        account_id="nodal_escrow_main",
        debit=0,
        credit=985000,
        balance_after=985000,
        timestamp=now + timedelta(hours=6, minutes=5),
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
    )

    db_session.add_all([payment, order, settlement, ledger])
    db_session.commit()

    service = ExceptionDetectionService()
    report = service.detect_exceptions(session=db_session)
    assert report.total_detected_count == 0
    assert report.total_exposure == 0


def test_clean_failed_payment_zero_exceptions(db_session: Session):
    """Verifies that a failed payment with cancelled order and NO downstream settlement creates zero exceptions."""
    now = datetime(2026, 8, 4, 10, 0, 0, tzinfo=timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-FAIL-CLEAN",
        merchant_id="M1",
        amount=500000,
        currency="INR",
        status=PaymentStatus.FAILED.value,
        created_at=now,
        method="CARD",
    )
    order = MerchantOrder(
        order_id="ORD-FAIL-CLEAN",
        payment_id_reference="PAY-FAIL-CLEAN",
        customer_id="C1",
        fulfillment_status=OrderFulfillmentStatus.CANCELLED.value,
        order_amount=500000,
        created_at=now,
    )

    db_session.add_all([payment, order])
    db_session.commit()

    service = ExceptionDetectionService()
    report = service.detect_exceptions(session=db_session)
    assert report.total_detected_count == 0
    assert report.total_exposure == 0


def test_normal_single_refund_zero_financial_exceptions(db_session: Session):
    """Verifies that a normal single refund creates zero anomalous exceptions."""
    now = datetime(2026, 8, 4, 10, 0, 0, tzinfo=timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-REF-NORM",
        merchant_id="M1",
        amount=1000000,
        currency="INR",
        status=PaymentStatus.REFUNDED.value,
        created_at=now,
        method="CARD",
    )
    order = MerchantOrder(
        order_id="ORD-REF-NORM",
        payment_id_reference="PAY-REF-NORM",
        customer_id="C1",
        fulfillment_status=OrderFulfillmentStatus.FULFILLED.value,
        order_amount=1000000,
        created_at=now,
    )
    settlement = BankSettlementBatch(
        settlement_id="SET-REF-NORM",
        payment_id="PAY-REF-NORM",
        acquirer_id="A1",
        net_amount=985000,
        interchange_fee_deducted=12711,
        tax_deducted=2289,
        clearing_timestamp=now + timedelta(hours=6),
    )
    dispute = DisputeRefundEvent(
        event_id="EVT-REF-NORM",
        payment_id="PAY-REF-NORM",
        event_type="REFUND",
        amount=1000000,
        timestamp=now + timedelta(days=1),
    )
    ledger_credit = NodalLedgerEntry(
        ledger_id="LED-REF-1",
        transaction_id="PAY-REF-NORM",
        account_id="nodal_escrow_main",
        debit=0,
        credit=985000,
        balance_after=985000,
        timestamp=now + timedelta(hours=6, minutes=5),
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
    )
    ledger_debit = NodalLedgerEntry(
        ledger_id="LED-REF-2",
        transaction_id="PAY-REF-NORM",
        account_id="nodal_escrow_main",
        debit=1000000,
        credit=0,
        balance_after=-15000,
        timestamp=now + timedelta(days=1, minutes=5),
        entry_type=LedgerEntryType.REFUND_DEBIT.value,
    )

    db_session.add_all([payment, order, settlement, dispute, ledger_credit, ledger_debit])
    db_session.commit()

    service = ExceptionDetectionService()
    report = service.detect_exceptions(session=db_session)
    # Single refund without chargeback is NOT a double-dip
    assert report.total_detected_count == 0
    assert report.total_exposure == 0
