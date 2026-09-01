"""Unit tests for entity correlation, deduplication keys, and detection idempotency."""
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
from backend.models.enums import PaymentStatus, OrderFulfillmentStatus, LedgerEntryType
from backend.exceptions.correlator import correlate_operational_entities
from backend.exceptions.service import ExceptionDetectionService


def test_correlate_operational_entities_multi_source(db_session: Session):
    """Verifies that all operational tables are cleanly correlated into a single entity group."""
    now = datetime.now(timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-CORR-1",
        merchant_id="M1",
        amount=1000000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
        method="CARD",
    )
    order = MerchantOrder(
        order_id="ORD-CORR-1",
        payment_id_reference="PAY-CORR-1",
        customer_id="C1",
        fulfillment_status=OrderFulfillmentStatus.FULFILLED.value,
        order_amount=1000000,
        created_at=now,
    )
    settlement = BankSettlementBatch(
        settlement_id="SET-CORR-1",
        payment_id="PAY-CORR-1",
        acquirer_id="A1",
        net_amount=985000,
        interchange_fee_deducted=12711,
        tax_deducted=2289,
        clearing_timestamp=now + timedelta(hours=6),
    )
    dispute = DisputeRefundEvent(
        event_id="EVT-CORR-1",
        payment_id="PAY-CORR-1",
        event_type="REFUND",
        amount=1000000,
        timestamp=now + timedelta(days=1),
    )
    ledger = NodalLedgerEntry(
        ledger_id="LED-CORR-1",
        transaction_id="PAY-CORR-1",
        account_id="nodal_escrow_main",
        debit=0,
        credit=985000,
        balance_after=985000,
        timestamp=now + timedelta(hours=6, minutes=5),
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
    )

    db_session.add_all([payment, order, settlement, dispute, ledger])
    db_session.commit()

    correlated = correlate_operational_entities(db_session)
    assert "PAY-CORR-1" in correlated
    entity = correlated["PAY-CORR-1"]

    assert entity.payment is not None
    assert len(entity.orders) == 1
    assert len(entity.settlements) == 1
    assert len(entity.disputes) == 1
    assert len(entity.ledger_entries) == 1
    assert len(entity.all_record_references) == 5


def test_detection_service_idempotency(db_session: Session):
    """Verifies that running detection twice on the same dataset creates 0 duplicate exceptions."""
    now = datetime.now(timezone.utc)
    # Ghost settlement anomaly
    payment = GatewayTransaction(
        payment_id="PAY-IDEMP-1",
        merchant_id="M1",
        amount=2000000,
        currency="INR",
        status=PaymentStatus.FAILED.value,
        created_at=now,
        method="CARD",
    )
    settlement = BankSettlementBatch(
        settlement_id="SET-IDEMP-1",
        payment_id="PAY-IDEMP-1",
        acquirer_id="A1",
        net_amount=1970000,
        interchange_fee_deducted=25423,
        tax_deducted=4577,
        clearing_timestamp=now + timedelta(hours=6),
    )
    ledger = NodalLedgerEntry(
        ledger_id="LED-IDEMP-1",
        transaction_id="PAY-IDEMP-1",
        account_id="nodal_escrow_main",
        debit=0,
        credit=1970000,
        balance_after=1970000,
        timestamp=now + timedelta(hours=6, minutes=5),
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
    )

    db_session.add_all([payment, settlement, ledger])
    db_session.commit()

    service = ExceptionDetectionService()

    # 1. First detection run
    report1 = service.detect_exceptions(session=db_session)
    assert report1.total_detected_count == 1
    assert report1.new_exception_count == 1
    assert report1.existing_exception_count == 0

    # 2. Second detection run (Idempotent)
    report2 = service.detect_exceptions(session=db_session)
    assert report2.total_detected_count == 1
    assert report2.new_exception_count == 0
    assert report2.existing_exception_count == 1
