"""Unit tests for Remediation Planning Engine."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from backend.models.enums import ExceptionState, ExceptionType, PolicyActionType, RemediationStatus
from backend.models.exceptions import ExceptionRecord
from backend.models.investigation import InvestigationRun
from backend.remediation.planner import RemediationPlanner


def test_remediation_planner_valid_plan(db_session: Session):
    """Verifies that a valid remediation plan is created for a diagnosed exception with an approved policy decision."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-PLAN-TEST-PAY-000001",
        primary_payment_id="PAY-000001",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="CRITICAL",
        state=ExceptionState.DIAGNOSED.value,
        exposure=5000000,
        detected_at=now,
        created_at=now,
    )
    db_session.add(exc)
    db_session.commit()

    inv = InvestigationRun(
        investigation_id="INV-PLAN-001",
        exception_id="EXC-PLAN-TEST-PAY-000001",
        status="COMPLETED",
        final_classification="PAYMENT_STATE_CONTRADICTION",
        confidence="0.95",
        root_cause="Diagnosed ghost settlement",
        created_at=now,
    )
    db_session.add(inv)
    db_session.commit()

    plan = RemediationPlanner.create_plan(
        session=db_session,
        exception_id="EXC-PLAN-TEST-PAY-000001",
        action=PolicyActionType.REFUND.value,
        parameters={"payment_id": "PAY-000001", "amount_minor_units": 5000000, "reason": "Refund ghost settlement"},
        requested_by="operator-01",
    )
    db_session.commit()

    assert plan.action_id.startswith("REM-")
    assert plan.action_type == PolicyActionType.REFUND.value
    assert plan.status == RemediationStatus.PENDING_APPROVAL.value
    assert plan.approval_required is True
    assert plan.approval_role == "FINANCE"


def test_remediation_planner_rejects_amount_exceeding_exposure(db_session: Session):
    """Verifies that the planner strictly rejects requested amounts exceeding authoritative deterministic exposure."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-PLAN-OVER-PAY-000002",
        primary_payment_id="PAY-000002",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="CRITICAL",
        state=ExceptionState.DIAGNOSED.value,
        exposure=5000000,
        detected_at=now,
        created_at=now,
    )
    db_session.add(exc)
    db_session.commit()

    inv = InvestigationRun(
        investigation_id="INV-PLAN-002",
        exception_id="EXC-PLAN-OVER-PAY-000002",
        status="COMPLETED",
        final_classification="PAYMENT_STATE_CONTRADICTION",
        confidence="0.95",
        root_cause="Diagnosed ghost settlement",
        created_at=now,
    )
    db_session.add(inv)
    db_session.commit()

    with pytest.raises(ValueError, match="exceeds authoritative deterministic exposure"):
        RemediationPlanner.create_plan(
            session=db_session,
            exception_id="EXC-PLAN-OVER-PAY-000002",
            action=PolicyActionType.REFUND.value,
            parameters={"payment_id": "PAY-000002", "amount_minor_units": 6000000, "reason": "Excessive refund"},
            requested_by="operator-01",
        )


def test_remediation_planner_legitimate_case_protection(db_session: Session):
    """Verifies that legitimate zero-exposure observations strictly reject financial remediation plans."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-LEGIT-PLAN-PAY-000003",
        primary_payment_id="PAY-000003",
        exception_type=ExceptionType.PARTIAL_SETTLEMENT.value,
        severity="LOW",
        state=ExceptionState.DIAGNOSED.value,
        exposure=0,
        detected_at=now,
        created_at=now,
    )
    db_session.add(exc)
    db_session.commit()

    inv = InvestigationRun(
        investigation_id="INV-LEGIT-PLAN-003",
        exception_id="EXC-LEGIT-PLAN-PAY-000003",
        status="COMPLETED",
        final_classification="PARTIAL_SETTLEMENT_OBSERVED",
        confidence="0.95",
        root_cause="Legitimate partial settlement with zero exposure",
        created_at=now,
    )
    db_session.add(inv)
    db_session.commit()

    with pytest.raises(ValueError, match="prohibits financial remediation|BLOCKED"):
        RemediationPlanner.create_plan(
            session=db_session,
            exception_id="EXC-LEGIT-PLAN-PAY-000003",
            action=PolicyActionType.REFUND.value,
            parameters={"payment_id": "PAY-000003", "amount_minor_units": 100000, "reason": "Invalid refund on legit case"},
            requested_by="operator-01",
        )
