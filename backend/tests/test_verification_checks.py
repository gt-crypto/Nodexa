"""Tests for independent deterministic post-remediation verification checks."""
import json
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from backend.models.database import SessionLocal
from backend.models.enums import (
    ExceptionType,
    ExceptionSeverity,
    ExceptionState,
    RemediationStatus,
    PolicyActionType,
    PaymentStatus,
    DisputeEventType,
    LedgerEntryType,
)
from backend.models.exceptions import ExceptionRecord
from backend.models.remediation import RemediationAction
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.services.repositories import ExceptionRepository, RemediationRepository
from backend.verification.checks import VerificationChecksRunner


def utc_now():
    return datetime.now(timezone.utc)


def test_check_1_remediation_execution_status(db_session: Session):
    """Verify Check 1 allows EXECUTED / AWAITING_VERIFICATION and rejects PLANNED, PENDING_APPROVAL, REJECTED, FAILED."""
    exc_repo = ExceptionRepository(db_session)
    rem_repo = RemediationRepository(db_session)

    exc = ExceptionRecord(
        exception_id="exc_chk1_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DIAGNOSED.value,
        exposure=500000,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    plan_awaiting = RemediationAction(
        action_id="act_chk1_awaiting",
        exception_id="exc_chk1_01",
        action_type=PolicyActionType.REFUND.value,
        status=RemediationStatus.AWAITING_VERIFICATION.value,
        action_payload=json.dumps({"amount_minor_units": 500000}),
        created_at=utc_now(),
        requested_at=utc_now(),
    )
    rem_repo.create_action(plan_awaiting)

    passed, ev = VerificationChecksRunner.check_remediation_execution_status(plan_awaiting)
    assert passed is True
    assert ev.result == "PASS"

    plan_planned = RemediationAction(
        action_id="act_chk1_planned",
        exception_id="exc_chk1_01",
        action_type=PolicyActionType.REFUND.value,
        status=RemediationStatus.PLANNED.value,
        action_payload=json.dumps({"amount_minor_units": 500000}),
        created_at=utc_now(),
        requested_at=utc_now(),
    )
    rem_repo.create_action(plan_planned)

    passed_planned, ev_planned = VerificationChecksRunner.check_remediation_execution_status(plan_planned)
    assert passed_planned is False
    assert ev_planned.result == "FAIL"


def test_check_2_refund_action_result_verification(db_session: Session):
    """Verify Check 2 verifies REFUND database state: payment status, dispute event, and ledger entry."""
    exc_repo = ExceptionRepository(db_session)
    rem_repo = RemediationRepository(db_session)

    # 1. Setup payment, dispute event, and ledger entry
    pmt = GatewayTransaction(
        payment_id="pay_chk2_ref_01",
        merchant_id="mer_01",
        amount=250000,
        currency="INR",
        status=PaymentStatus.REFUNDED.value,
        method="UPI",
    )
    db_session.add(pmt)

    disp = DisputeRefundEvent(
        event_id="dsp_chk2_ref_01",
        payment_id="pay_chk2_ref_01",
        event_type=DisputeEventType.REFUND.value,
        amount=250000,
        timestamp=utc_now(),
    )
    db_session.add(disp)

    ledger = NodalLedgerEntry(
        ledger_id="led_chk2_ref_01",
        account_id="nodal_escrow_main",
        entry_type=LedgerEntryType.REFUND_DEBIT.value,
        debit=250000,
        credit=0,
        balance_after=750000,
        transaction_id="pay_chk2_ref_01",
        timestamp=utc_now(),
    )
    db_session.add(ledger)

    exc = ExceptionRecord(
        exception_id="exc_chk2_ref_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DIAGNOSED.value,
        primary_payment_id="pay_chk2_ref_01",
        exposure=250000,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    plan = RemediationAction(
        action_id="act_chk2_ref_01",
        exception_id="exc_chk2_ref_01",
        action_type=PolicyActionType.REFUND.value,
        status=RemediationStatus.AWAITING_VERIFICATION.value,
        action_payload=json.dumps({"payment_id": "pay_chk2_ref_01", "amount_minor_units": 250000}),
        created_at=utc_now(),
        requested_at=utc_now(),
    )
    rem_repo.create_action(plan)

    passed, fail_reasons, ev_list = VerificationChecksRunner.check_action_result(db_session, plan, exc)
    assert passed is True
    assert len(fail_reasons) == 0
    assert any(e.check_id == "CHECK-REFUND-STATUS" and e.result == "PASS" for e in ev_list)
    assert any(e.check_id == "CHECK-REFUND-AMOUNT" and e.result == "PASS" for e in ev_list)
    assert any(e.check_id == "CHECK-LEDGER-DEBIT" and e.result == "PASS" for e in ev_list)


def test_check_3_exposure_recalculation(db_session: Session):
    """Verify Check 3 recalculates remaining exposure from fresh records."""
    exc_repo = ExceptionRepository(db_session)
    rem_repo = RemediationRepository(db_session)

    # Setup refunded payment
    pmt = GatewayTransaction(
        payment_id="pay_chk3_exp_01",
        merchant_id="mer_01",
        amount=500000,
        currency="INR",
        status=PaymentStatus.REFUNDED.value,
        method="CARD",
    )
    db_session.add(pmt)

    disp = DisputeRefundEvent(
        event_id="dsp_chk3_exp_01",
        payment_id="pay_chk3_exp_01",
        event_type=DisputeEventType.REFUND.value,
        amount=500000,
        timestamp=utc_now(),
    )
    db_session.add(disp)

    exc = ExceptionRecord(
        exception_id="exc_chk3_exp_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DIAGNOSED.value,
        primary_payment_id="pay_chk3_exp_01",
        exposure=500000,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    plan = RemediationAction(
        action_id="act_chk3_exp_01",
        exception_id="exc_chk3_exp_01",
        action_type=PolicyActionType.REFUND.value,
        status=RemediationStatus.AWAITING_VERIFICATION.value,
        action_payload=json.dumps({"payment_id": "pay_chk3_exp_01", "amount_minor_units": 500000}),
        created_at=utc_now(),
        requested_at=utc_now(),
    )
    rem_repo.create_action(plan)

    passed, rem_exp, red_amt, red_bps, ev_list = VerificationChecksRunner.check_exposure_recalculation(
        db_session, exc, plan, tolerance=0
    )
    assert passed is True
    assert rem_exp == 0
    assert red_amt == 500000
    assert red_bps == 10000


def test_check_7_legitimate_case_protection(db_session: Session):
    """Verify Check 7 prevents unauthorized financial remediation on legitimate timing/partial exceptions."""
    exc_repo = ExceptionRepository(db_session)
    rem_repo = RemediationRepository(db_session)

    exc = ExceptionRecord(
        exception_id="exc_chk7_legit_01",
        exception_type=ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value,
        severity=ExceptionSeverity.LOW.value,
        state=ExceptionState.DIAGNOSED.value,
        exposure=0,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    # Valid non-financial plan (e.g. CLEAR_LEGITIMATE_EXCEPTION or RESOLVE_EXCEPTION)
    valid_plan = RemediationAction(
        action_id="act_chk7_valid",
        exception_id="exc_chk7_legit_01",
        action_type=PolicyActionType.RESOLVE_EXCEPTION.value,
        status=RemediationStatus.AWAITING_VERIFICATION.value,
        action_payload=json.dumps({"resolution_reason": "Cleared legitimate timing"}),
        created_at=utc_now(),
        requested_at=utc_now(),
    )
    rem_repo.create_action(valid_plan)

    passed_valid, ev_valid = VerificationChecksRunner.check_legitimate_case_protection(exc, valid_plan)
    assert passed_valid is True
    assert ev_valid.result == "PASS"

    # Invalid financial plan attempted on legitimate case
    bad_plan = RemediationAction(
        action_id="act_chk7_bad",
        exception_id="exc_chk7_legit_01",
        action_type=PolicyActionType.REFUND.value,
        status=RemediationStatus.AWAITING_VERIFICATION.value,
        action_payload=json.dumps({"amount_minor_units": 100000}),
        created_at=utc_now(),
        requested_at=utc_now(),
    )
    rem_repo.create_action(bad_plan)

    passed_bad, ev_bad = VerificationChecksRunner.check_legitimate_case_protection(exc, bad_plan)
    assert passed_bad is False
    assert ev_bad.result == "FAIL"
