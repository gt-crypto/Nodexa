"""Tests for deterministic exposure recalculation and integer basis points precision."""
import json
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from backend.models.enums import ExceptionType, ExceptionSeverity, ExceptionState, PaymentStatus, DisputeEventType
from backend.models.exceptions import ExceptionRecord
from backend.models.financial_sources import GatewayTransaction, DisputeRefundEvent
from backend.services.repositories import ExceptionRepository
from backend.verification.exposure import recalculate_deterministic_exposure


def utc_now():
    return datetime.now(timezone.utc)


def test_exposure_recalculation_zero_remaining(db_session: Session):
    """Verify that full remediation results in 0 remaining exposure and 10,000 bps (100.00%) reduction."""
    exc_repo = ExceptionRepository(db_session)

    pmt = GatewayTransaction(
        payment_id="pay_exp_zero_01",
        merchant_id="mer_01",
        amount=5000000,
        currency="INR",
        status=PaymentStatus.REFUNDED.value,
        method="UPI",
    )
    db_session.add(pmt)

    disp = DisputeRefundEvent(
        event_id="dsp_exp_zero_01",
        payment_id="pay_exp_zero_01",
        event_type=DisputeEventType.REFUND.value,
        amount=5000000,
        timestamp=utc_now(),
    )
    db_session.add(disp)

    exc = ExceptionRecord(
        exception_id="exc_exp_zero_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.CRITICAL.value,
        state=ExceptionState.DIAGNOSED.value,
        primary_payment_id="pay_exp_zero_01",
        exposure=5000000,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    rem_exp, red_amt, red_bps, breakdown = recalculate_deterministic_exposure(db_session, exc)
    assert rem_exp == 0
    assert red_amt == 5000000
    assert red_bps == 10000
    assert isinstance(red_bps, int)


def test_exposure_recalculation_partial_exposure(db_session: Session):
    """Verify that partial remediation records correct integer remaining exposure and partial basis points."""
    exc_repo = ExceptionRepository(db_session)

    pmt = GatewayTransaction(
        payment_id="pay_exp_part_01",
        merchant_id="mer_01",
        amount=1000000,
        currency="INR",
        status=PaymentStatus.AUTHORIZED.value,  # Not marked refunded
        method="UPI",
    )
    db_session.add(pmt)

    # Only partial refund of ₹2,500 out of ₹10,000 exposure
    disp = DisputeRefundEvent(
        event_id="dsp_exp_part_01",
        payment_id="pay_exp_part_01",
        event_type=DisputeEventType.REFUND.value,
        amount=250000,
        timestamp=utc_now(),
    )
    db_session.add(disp)

    exc = ExceptionRecord(
        exception_id="exc_exp_part_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DIAGNOSED.value,
        primary_payment_id="pay_exp_part_01",
        exposure=1000000,  # ₹10,000.00
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    rem_exp, red_amt, red_bps, breakdown = recalculate_deterministic_exposure(db_session, exc)
    assert rem_exp == 750000
    assert red_amt == 250000
    assert red_bps == 2500  # 25.00%
    assert isinstance(rem_exp, int)
    assert isinstance(red_bps, int)


def test_exposure_recalculation_legitimate_zero_case(db_session: Session):
    """Verify that legitimate observation with 0 exposure yields 0 remaining and 10,000 bps."""
    exc_repo = ExceptionRepository(db_session)

    exc = ExceptionRecord(
        exception_id="exc_exp_legit_01",
        exception_type=ExceptionType.PARTIAL_SETTLEMENT.value,
        severity=ExceptionSeverity.LOW.value,
        state=ExceptionState.DIAGNOSED.value,
        exposure=0,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    rem_exp, red_amt, red_bps, breakdown = recalculate_deterministic_exposure(db_session, exc)
    assert rem_exp == 0
    assert red_amt == 0
    assert red_bps == 10000
