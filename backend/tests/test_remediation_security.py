"""Security and safety invariant tests for Remediation Engine."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from backend.models.enums import ExceptionState, ExceptionType, PolicyActionType, RemediationStatus
from backend.models.exceptions import ExceptionRecord
from backend.models.investigation import InvestigationRun
from backend.remediation.planner import RemediationPlanner
from backend.remediation.approval import ApprovalService
from backend.remediation.executor import RemediationExecutor


def test_remediation_security_rejections(db_session: Session):
    """Verifies safety protections: unallowlisted actions, unapproved execution, and excessive amounts."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-SEC-PAY-SEC-001",
        primary_payment_id="PAY-SEC-001",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="CRITICAL",
        state=ExceptionState.DIAGNOSED.value,
        exposure=2000000,
        detected_at=now,
        created_at=now,
    )
    inv = InvestigationRun(
        investigation_id="INV-SEC-001",
        exception_id="EXC-SEC-PAY-SEC-001",
        status="COMPLETED",
        final_classification="PAYMENT_STATE_CONTRADICTION",
        confidence="0.95",
        root_cause="Diagnosed ghost settlement",
        created_at=now,
    )
    db_session.add_all([exc, inv])
    db_session.commit()

    # 1. Reject arbitrary action
    with pytest.raises(ValueError, match="not in the allowlisted remediation action taxonomy|BLOCKED"):
        RemediationPlanner.create_plan(
            session=db_session,
            exception_id="EXC-SEC-PAY-SEC-001",
            action="ARBITRARY_TRANSFER",
            parameters={"amount": 100},
            requested_by="attacker",
        )

    # 2. Reject execution without required approval
    plan = RemediationPlanner.create_plan(
        session=db_session,
        exception_id="EXC-SEC-PAY-SEC-001",
        action=PolicyActionType.REFUND.value,
        parameters={"payment_id": "PAY-SEC-001", "amount_minor_units": 2000000, "reason": "Security test plan"},
        requested_by="operator-01",
    )
    db_session.commit()

    with pytest.raises(ValueError, match="requires approval|cannot be executed|PENDING_APPROVAL"):
        RemediationExecutor.execute(session=db_session, action_id=plan.action_id)
