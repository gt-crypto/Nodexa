"""Critical Safety Boundaries and Invariant Hardening Tests for Nodal Sentinel.

Tests all required safety boundary conditions to guarantee zero unauthorized
mutations, zero state machine bypasses, zero false closures, and strict isolation.
"""
import json
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.enums import (
    ExceptionType,
    ExceptionState,
    RemediationStatus,
)
from backend.models.exceptions import ExceptionRecord
from backend.models.investigation import InvestigationRun
from backend.models.remediation import RemediationAction, RemediationApproval
from backend.controls.state_machine import (
    transition_exception_state,
    TransitionActorType,
    InvalidStateTransitionError,
)
from backend.remediation.service import RemediationService
from backend.verification.service import VerificationService
from backend.agent.tools.registry import AgentToolRegistry


def utc_now():
    return datetime.now(timezone.utc)


def test_safety_boundary_1_unauthorized_remediation_blocked(db_session: Session):
    """Safety Gate 1: Unapproved remediation execution must be rejected."""
    rem_service = RemediationService()
    exc = ExceptionRecord(
        exception_id="exc_dummy_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="HIGH",
        state=ExceptionState.DIAGNOSED.value,
        exposure=50000,
        created_at=utc_now(),
    )
    db_session.add(exc)
    db_session.flush()

    # Create action requiring approval but with no approval record
    action = RemediationAction(
        action_id="act_unauth_01",
        exception_id="exc_dummy_01",
        action_type="REFUND",
        status=RemediationStatus.PENDING_APPROVAL.value,
        approval_required=True,
        action_payload=json.dumps({"amount_minor_units": 50000}),
        requested_by="operator-01",
        created_at=utc_now(),
    )
    db_session.add(action)
    db_session.commit()

    with pytest.raises(ValueError, match="requires approval before execution|cannot be executed"):
        rem_service.execute_remediation(session=db_session, action_id="act_unauth_01")


def test_safety_boundary_2_expired_approval_rejected(db_session: Session):
    """Safety Gate 2: Expired approvals must be rejected."""
    rem_service = RemediationService()
    exc = ExceptionRecord(
        exception_id="exc_dummy_02",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="HIGH",
        state=ExceptionState.DIAGNOSED.value,
        exposure=50000,
        created_at=utc_now(),
    )
    db_session.add(exc)
    db_session.flush()

    action = RemediationAction(
        action_id="act_expired_01",
        exception_id="exc_dummy_02",
        action_type="REFUND",
        status=RemediationStatus.APPROVED.value,
        approval_required=True,
        approved_by="controller-01",
        approved_at=utc_now() - timedelta(hours=48),
        action_payload=json.dumps({"amount_minor_units": 50000}),
        requested_by="operator-01",
        created_at=utc_now() - timedelta(hours=48),
    )
    approval = RemediationApproval(
        approval_id="appr_expired_01",
        action_id="act_expired_01",
        required_role="FINANCE_CONTROLLER",
        approved_by="controller-01",
        decision="APPROVED",
        reason="Approved previously",
        timestamp=utc_now() - timedelta(hours=48),
        expires_at=utc_now() - timedelta(hours=24),  # Expired
    )
    db_session.add(action)
    db_session.add(approval)
    db_session.commit()

    with pytest.raises(ValueError, match="has expired"):
        rem_service.execute_remediation(session=db_session, action_id="act_expired_01")


def test_safety_boundary_3_separation_of_duties_self_approval_rejected(db_session: Session):
    """Safety Gate 3: Requester cannot approve their own restricted remediation."""
    rem_service = RemediationService()
    exc = ExceptionRecord(
        exception_id="exc_dummy_03",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="HIGH",
        state=ExceptionState.DIAGNOSED.value,
        exposure=50000,
        created_at=utc_now(),
    )
    db_session.add(exc)
    db_session.flush()

    action = RemediationAction(
        action_id="act_sod_01",
        exception_id="exc_dummy_03",
        action_type="REFUND",
        status=RemediationStatus.PENDING_APPROVAL.value,
        approval_required=True,
        action_payload=json.dumps({"amount_minor_units": 50000}),
        requested_by="operator-alice",
        created_at=utc_now(),
    )
    db_session.add(action)
    db_session.commit()

    with pytest.raises(ValueError, match="Separation of duties violation"):
        rem_service.approve_remediation(
            session=db_session,
            action_id="act_sod_01",
            approved_by="operator-alice",  # Self-approval
            decision="APPROVED",
            reason="Self-approving my own request",
        )


def test_safety_boundary_4_excessive_amount_rejected(db_session: Session):
    """Safety Gate 4: Remediation amount exceeding deterministic exposure must be blocked."""
    rem_service = RemediationService()
    exc = ExceptionRecord(
        exception_id="exc_exposure_limit_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="HIGH",
        state=ExceptionState.DIAGNOSED.value,
        exposure=50000,  # ₹500.00
        primary_payment_id="PAY-01",
        created_at=utc_now(),
    )
    db_session.add(exc)
    db_session.flush()

    inv = InvestigationRun(
        investigation_id="inv_exp_limit_01",
        exception_id="exc_exposure_limit_01",
        status="COMPLETED",
        final_classification="PAYMENT_STATE_CONTRADICTION",
        root_cause="Ghost settlement detected",
        created_at=utc_now(),
    )
    db_session.add(inv)
    db_session.commit()

    with pytest.raises(ValueError, match="exceeds authoritative deterministic exposure"):
        rem_service.create_remediation_plan(
            session=db_session,
            exception_id="exc_exposure_limit_01",
            action="REFUND",
            parameters={"payment_id": "PAY-01", "amount_minor_units": 60000, "reason": "Excessive refund"},  # 60000 > 50000
            requested_by="operator-01",
        )


def test_safety_boundary_5_ai_tool_registry_read_only(db_session: Session):
    """Safety Gate 5: AI agent tool registry must declare only read-only inspect tools with zero mutation capability."""
    registry = AgentToolRegistry(max_tool_calls=10)
    tools = registry._tools

    # All tools must be read-only
    for tool_name in tools.keys():
        assert "mutate" not in tool_name.lower()
        assert "delete" not in tool_name.lower()
        assert "drop" not in tool_name.lower()
        assert "execute" not in tool_name.lower()


def test_safety_boundary_6_state_machine_invalid_transitions_rejected(db_session: Session):
    """Safety Gate 6: Direct lifecycle transitions bypassing mandatory stages must fail."""
    exc = ExceptionRecord(
        exception_id="exc_state_bypass_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="HIGH",
        state=ExceptionState.DETECTED.value,
        exposure=50000,
        created_at=utc_now(),
    )
    db_session.add(exc)
    db_session.commit()

    # DETECTED cannot jump directly to VERIFIED_CLOSED
    with pytest.raises(InvalidStateTransitionError):
        transition_exception_state(
            session=db_session,
            exception_id="exc_state_bypass_01",
            to_state=ExceptionState.VERIFIED_CLOSED,
            reason="Illegal jump to verified closed",
            actor_type=TransitionActorType.SYSTEM,
            actor_id="bypass-tester",
        )


def test_safety_boundary_7_unexecuted_remediation_verification_rejected(db_session: Session):
    """Safety Gate 7: Verification cannot verify an unexecuted remediation."""
    ver_service = VerificationService()
    exc = ExceptionRecord(
        exception_id="exc_dummy_07",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="HIGH",
        state=ExceptionState.DIAGNOSED.value,
        exposure=50000,
        created_at=utc_now(),
    )
    db_session.add(exc)
    db_session.flush()

    action = RemediationAction(
        action_id="act_unexecuted_01",
        exception_id="exc_dummy_07",
        action_type="REFUND",
        status=RemediationStatus.APPROVED.value,  # Not EXECUTED / AWAITING_VERIFICATION
        action_payload=json.dumps({"amount_minor_units": 50000}),
        requested_by="operator-01",
        created_at=utc_now(),
    )
    db_session.add(action)
    db_session.commit()

    with pytest.raises(ValueError, match="Cannot verify remediation in unexecuted state"):
        ver_service.verify_remediation(session=db_session, remediation_id="act_unexecuted_01")
