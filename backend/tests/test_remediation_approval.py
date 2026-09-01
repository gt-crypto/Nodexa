"""Unit tests for Remediation Approval workflow and Separation of Duties."""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session

from backend.models.enums import ExceptionState, ExceptionType, PolicyActionType, RemediationStatus
from backend.models.exceptions import ExceptionRecord
from backend.models.investigation import InvestigationRun
from backend.remediation.planner import RemediationPlanner
from backend.remediation.approval import ApprovalService
from backend.remediation.executor import RemediationExecutor


def test_remediation_approval_success_and_rejection(db_session: Session):
    """Verifies that approval transitions plan to APPROVED, and rejection transitions plan to REJECTED."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-APPR-TEST-PAY-000001",
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
        investigation_id="INV-APPR-001",
        exception_id="EXC-APPR-TEST-PAY-000001",
        status="COMPLETED",
        final_classification="PAYMENT_STATE_CONTRADICTION",
        confidence="0.95",
        root_cause="Diagnosed ghost settlement",
        created_at=now,
    )
    db_session.add(inv)
    db_session.commit()

    # Create plan 1
    plan1 = RemediationPlanner.create_plan(
        session=db_session,
        exception_id="EXC-APPR-TEST-PAY-000001",
        action=PolicyActionType.REFUND.value,
        parameters={"payment_id": "PAY-000001", "amount_minor_units": 5000000, "reason": "Refund ghost settlement"},
        requested_by="operator-01",
    )
    db_session.commit()

    # 1. Approve Plan 1
    appr1 = ApprovalService.record_approval(
        session=db_session,
        action_id=plan1.action_id,
        approved_by="finance-controller-01",
        decision="APPROVED",
        reason="Verified diagnosis and exposure",
    )
    db_session.commit()

    assert appr1.decision == "APPROVED"
    assert plan1.status == RemediationStatus.APPROVED.value
    assert plan1.approved_by == "finance-controller-01"

    # Create plan 2
    plan2 = RemediationPlanner.create_plan(
        session=db_session,
        exception_id="EXC-APPR-TEST-PAY-000001",
        action=PolicyActionType.REFUND.value,
        parameters={"payment_id": "PAY-000001", "amount_minor_units": 5000000, "reason": "Second refund plan"},
        requested_by="operator-01",
    )
    db_session.commit()

    # 2. Reject Plan 2
    appr2 = ApprovalService.record_approval(
        session=db_session,
        action_id=plan2.action_id,
        approved_by="finance-controller-01",
        decision="REJECTED",
        reason="Duplicate plan rejected",
    )
    db_session.commit()

    assert appr2.decision == "REJECTED"
    assert plan2.status == RemediationStatus.REJECTED.value


def test_separation_of_duties_enforcement(db_session: Session):
    """Verifies that requester cannot approve their own remediation plan."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-SOD-TEST-PAY-000002",
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
        investigation_id="INV-SOD-002",
        exception_id="EXC-SOD-TEST-PAY-000002",
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
        exception_id="EXC-SOD-TEST-PAY-000002",
        action=PolicyActionType.REFUND.value,
        parameters={"payment_id": "PAY-000002", "amount_minor_units": 5000000, "reason": "Self-approval test"},
        requested_by="operator-john",
    )
    db_session.commit()

    with pytest.raises(ValueError, match="Separation of duties violation"):
        ApprovalService.record_approval(
            session=db_session,
            action_id=plan.action_id,
            approved_by="operator-john",  # Same user!
            decision="APPROVED",
            reason="Self-approval attempt",
        )
