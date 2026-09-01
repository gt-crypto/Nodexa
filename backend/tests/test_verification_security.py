"""Tests for security boundaries, input hygiene, and verification safety gates."""
import json
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
)
from backend.models.exceptions import ExceptionRecord
from backend.models.remediation import RemediationAction
from backend.models.financial_sources import GatewayTransaction
from backend.services.repositories import ExceptionRepository, RemediationRepository
from backend.verification.service import VerificationService


def utc_now():
    return datetime.now(timezone.utc)


def test_verification_rejects_unexecuted_remediation(db_session: Session):
    """Verify that attempting to verify a PLANNED or PENDING_APPROVAL remediation raises an error."""
    exc_repo = ExceptionRepository(db_session)
    rem_repo = RemediationRepository(db_session)

    exc = ExceptionRecord(
        exception_id="exc_sec_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DIAGNOSED.value,
        exposure=500000,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    plan = RemediationAction(
        action_id="act_sec_planned",
        exception_id="exc_sec_01",
        action_type=PolicyActionType.REFUND.value,
        status=RemediationStatus.PLANNED.value,  # Unexecuted
        action_payload=json.dumps({"amount_minor_units": 500000}),
        created_at=utc_now(),
        requested_at=utc_now(),
    )
    rem_repo.create_action(plan)

    service = VerificationService()
    with pytest.raises(ValueError, match="Cannot verify remediation in unexecuted state 'PLANNED'"):
        service.verify_remediation(db_session, remediation_id="act_sec_planned")


def test_dry_run_never_mutates_database_or_lifecycle(db_session: Session):
    """Verify dry_run=True performs pure read inspection without state transition or record creation."""
    exc_repo = ExceptionRepository(db_session)
    rem_repo = RemediationRepository(db_session)

    exc = ExceptionRecord(
        exception_id="exc_sec_dry_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DIAGNOSED.value,
        primary_payment_id="pay_sec_dry_01",
        exposure=100000,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    plan = RemediationAction(
        action_id="act_sec_dry_01",
        exception_id="exc_sec_dry_01",
        action_type=PolicyActionType.REFUND.value,
        status=RemediationStatus.AWAITING_VERIFICATION.value,
        action_payload=json.dumps({"payment_id": "pay_sec_dry_01", "amount_minor_units": 100000}),
        created_at=utc_now(),
        requested_at=utc_now(),
    )
    rem_repo.create_action(plan)

    service = VerificationService()
    dry_res = service.verify_remediation(db_session, remediation_id="act_sec_dry_01", dry_run=True)

    # State must remain unchanged in DIAGNOSED
    exc_after = exc_repo.get_exception("exc_sec_dry_01")
    assert exc_after.state == ExceptionState.DIAGNOSED.value

    # No verification record persisted
    latest_ver = service.get_latest_verification_for_remediation(db_session, "act_sec_dry_01")
    assert latest_ver is None
