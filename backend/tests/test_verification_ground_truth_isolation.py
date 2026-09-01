"""Tests proving complete isolation between the verification engine and evaluation_ground_truth table."""
import json
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import delete

from backend.models.ground_truth import EvaluationGroundTruth
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
from backend.services.repositories import ExceptionRepository, RemediationRepository
from backend.verification.service import VerificationService


def utc_now():
    return datetime.now(timezone.utc)


def test_verification_ground_truth_isolation(db_session: Session):
    """Verify that deleting the entire evaluation_ground_truth table does not impair post-remediation verification."""
    # 1. Completely delete all records in evaluation_ground_truth
    db_session.execute(delete(EvaluationGroundTruth))
    db_session.flush()

    # 2. Setup standard operational data
    exc_repo = ExceptionRepository(db_session)
    rem_repo = RemediationRepository(db_session)

    pmt = GatewayTransaction(
        payment_id="pay_gt_iso_01",
        merchant_id="mer_01",
        amount=200000,
        currency="INR",
        status=PaymentStatus.REFUNDED.value,
        method="UPI",
    )
    db_session.add(pmt)

    disp = DisputeRefundEvent(
        event_id="dsp_gt_iso_01",
        payment_id="pay_gt_iso_01",
        event_type=DisputeEventType.REFUND.value,
        amount=200000,
        timestamp=utc_now(),
    )
    db_session.add(disp)

    ledger = NodalLedgerEntry(
        ledger_id="led_gt_iso_01",
        account_id="nodal_escrow_main",
        entry_type=LedgerEntryType.REFUND_DEBIT.value,
        debit=200000,
        credit=0,
        balance_after=800000,
        transaction_id="pay_gt_iso_01",
        timestamp=utc_now(),
    )
    db_session.add(ledger)

    exc = ExceptionRecord(
        exception_id="exc_gt_iso_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DIAGNOSED.value,
        primary_payment_id="pay_gt_iso_01",
        exposure=200000,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    plan = RemediationAction(
        action_id="act_gt_iso_01",
        exception_id="exc_gt_iso_01",
        action_type=PolicyActionType.REFUND.value,
        status=RemediationStatus.AWAITING_VERIFICATION.value,
        action_payload=json.dumps({"payment_id": "pay_gt_iso_01", "amount_minor_units": 200000}),
        before_snapshot=json.dumps({"current_balance": 1000000}),
        after_snapshot=json.dumps({"current_balance": 800000, "debit": 200000, "credit": 0}),
        created_at=utc_now(),
        requested_at=utc_now(),
    )
    rem_repo.create_action(plan)

    # 3. Execute post-remediation verification without ground truth
    service = VerificationService()
    record = service.verify_remediation(db_session, remediation_id="act_gt_iso_01")

    assert record.verification_status == VerificationStatus.VERIFIED.value
    assert record.remaining_exposure == 0
    assert record.exposure_reduction == 200000
    assert record.exposure_reduction_bps == 10000

    # Ensure exception closed cleanly
    updated_exc = exc_repo.get_exception("exc_gt_iso_01")
    assert updated_exc.state == ExceptionState.VERIFIED_CLOSED.value
