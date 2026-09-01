"""Tests for verification idempotency, concurrency locking, and controlled retry."""
import json
import threading
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from backend.models.enums import (
    ExceptionType,
    ExceptionSeverity,
    ExceptionState,
    RemediationStatus,
    PolicyActionType,
    PaymentStatus,
    DisputeEventType,
    LedgerEntryType,
    VerificationStatus,
)
from backend.models.exceptions import ExceptionRecord
from backend.models.remediation import RemediationAction
from backend.models.financial_sources import (
    GatewayTransaction,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.services.repositories import ExceptionRepository, RemediationRepository, VerificationRepository
from backend.verification.service import VerificationService


def utc_now():
    return datetime.now(timezone.utc)


def test_verification_idempotency(db_session: Session):
    """Verify that executing verification twice on a verified remediation returns the identical record."""
    exc_repo = ExceptionRepository(db_session)
    rem_repo = RemediationRepository(db_session)

    pmt = GatewayTransaction(
        payment_id="pay_idemp_01",
        merchant_id="mer_01",
        amount=300000,
        currency="INR",
        status=PaymentStatus.REFUNDED.value,
        method="UPI",
    )
    db_session.add(pmt)

    disp = DisputeRefundEvent(
        event_id="dsp_idemp_01",
        payment_id="pay_idemp_01",
        event_type=DisputeEventType.REFUND.value,
        amount=300000,
        timestamp=utc_now(),
    )
    db_session.add(disp)

    ledger = NodalLedgerEntry(
        ledger_id="led_idemp_01",
        account_id="nodal_escrow_main",
        entry_type=LedgerEntryType.REFUND_DEBIT.value,
        debit=300000,
        credit=0,
        balance_after=700000,
        transaction_id="pay_idemp_01",
        timestamp=utc_now(),
    )
    db_session.add(ledger)

    exc = ExceptionRecord(
        exception_id="exc_idemp_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DIAGNOSED.value,
        primary_payment_id="pay_idemp_01",
        exposure=300000,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    plan = RemediationAction(
        action_id="act_idemp_01",
        exception_id="exc_idemp_01",
        action_type=PolicyActionType.REFUND.value,
        status=RemediationStatus.AWAITING_VERIFICATION.value,
        action_payload=json.dumps({"payment_id": "pay_idemp_01", "amount_minor_units": 300000}),
        before_snapshot=json.dumps({"current_balance": 1000000}),
        after_snapshot=json.dumps({"current_balance": 700000, "debit": 300000, "credit": 0}),
        created_at=utc_now(),
        requested_at=utc_now(),
    )
    rem_repo.create_action(plan)

    service = VerificationService()

    # First verification run
    ver1 = service.verify_remediation(db_session, remediation_id="act_idemp_01")
    print(f"\nIDEMP FAILURE REASONS: {ver1.failure_reasons}, FAILED CHECKS: {ver1.checks_failed}")
    assert ver1.verification_status == VerificationStatus.VERIFIED.value

    # Second verification run (idempotent)
    ver2 = service.verify_remediation(db_session, remediation_id="act_idemp_01")
    assert ver2.verification_id == ver1.verification_id

    # Verify count of records in DB is exactly 1
    ver_repo = VerificationRepository(db_session)
    records = ver_repo.list_records_for_remediation("act_idemp_01")
    assert len(records) == 1


def test_retry_on_failed_verification(db_session: Session):
    """Verify that a failed verification can be retried and recorded with an incremented attempt number."""
    exc_repo = ExceptionRepository(db_session)
    rem_repo = RemediationRepository(db_session)

    pmt = GatewayTransaction(
        payment_id="pay_retry_01",
        merchant_id="mer_01",
        amount=400000,
        currency="INR",
        status=PaymentStatus.AUTHORIZED.value,  # Not refunded yet (will fail verification)
        method="CARD",
    )
    db_session.add(pmt)

    exc = ExceptionRecord(
        exception_id="exc_retry_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DIAGNOSED.value,
        primary_payment_id="pay_retry_01",
        exposure=400000,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    plan = RemediationAction(
        action_id="act_retry_01",
        exception_id="exc_retry_01",
        action_type=PolicyActionType.REFUND.value,
        status=RemediationStatus.AWAITING_VERIFICATION.value,
        action_payload=json.dumps({"payment_id": "pay_retry_01", "amount_minor_units": 400000}),
        created_at=utc_now(),
        requested_at=utc_now(),
    )
    rem_repo.create_action(plan)

    service = VerificationService()

    # Attempt 1: Fails because payment status is AUTHORIZED and dispute event missing
    ver1 = service.verify_remediation(db_session, remediation_id="act_retry_01")
    assert ver1.verification_status == VerificationStatus.FAILED.value
    assert ver1.attempt_number == 1

    # Now fix the database state (simulate operator correction)
    pmt.status = PaymentStatus.REFUNDED.value
    disp = DisputeRefundEvent(
        event_id="dsp_retry_01",
        payment_id="pay_retry_01",
        event_type=DisputeEventType.REFUND.value,
        amount=400000,
        timestamp=utc_now(),
    )
    db_session.add(disp)
    ledger = NodalLedgerEntry(
        ledger_id="led_retry_01",
        account_id="nodal_escrow_main",
        entry_type=LedgerEntryType.REFUND_DEBIT.value,
        debit=400000,
        credit=0,
        balance_after=600000,
        transaction_id="pay_retry_01",
        timestamp=utc_now(),
    )
    db_session.add(ledger)
    db_session.flush()

    # Attempt 2: Retry succeeds
    ver2 = service.retry_verification(db_session, verification_id=ver1.verification_id)
    assert ver2.verification_status == VerificationStatus.VERIFIED.value
    assert ver2.attempt_number == 2

    # Cannot retry a VERIFIED record
    with pytest.raises(ValueError, match="Cannot retry verification with status 'VERIFIED'"):
        service.retry_verification(db_session, verification_id=ver2.verification_id)
