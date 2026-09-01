"""Tests for the deterministic Exception State Machine and transition validation service."""
import pytest
from datetime import datetime, timezone

from backend.models.exceptions import ExceptionRecord, ExceptionAffectedRecord
from backend.models.enums import ExceptionState, ExceptionSeverity, ExceptionType, TransitionActorType
from backend.controls.state_machine import (
    transition_exception_state,
    is_valid_transition,
    InvalidStateTransitionError,
)
from backend.services.repositories import ExceptionRepository


def utc_now():
    return datetime.now(timezone.utc)


def test_exception_creation_and_initial_state(db_session):
    """Verify newly created exception defaults to DETECTED state."""
    repo = ExceptionRepository(db_session)

    exc = ExceptionRecord(
        exception_id="exc_ghost_101",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DETECTED.value,
        exposure=450000,  # ₹4500.00
        confidence=0.9850,
        description="Settlement arrived with no matching gateway capture.",
        primary_payment_id="pay_nonexistent_99",
        detected_at=utc_now(),
    )
    repo.create_exception(exc)

    fetched = repo.get_exception("exc_ghost_101")
    assert fetched is not None
    assert fetched.state == ExceptionState.DETECTED.value
    assert fetched.exposure == 450000
    assert fetched.severity == ExceptionSeverity.HIGH.value


def test_valid_full_lifecycle_state_transitions(db_session):
    """Verify happy-path transition sequence:
    DETECTED -> INVESTIGATING -> DIAGNOSED -> AWAITING_ACTION -> RESOLVING -> VERIFYING -> VERIFIED_CLOSED.
    """
    repo = ExceptionRepository(db_session)

    exc = ExceptionRecord(
        exception_id="exc_lifecycle_01",
        exception_type=ExceptionType.SETTLEMENT_SLA_BREACH.value,
        severity=ExceptionSeverity.MEDIUM.value,
        state=ExceptionState.DETECTED.value,
        exposure=200000,
        detected_at=utc_now(),
    )
    repo.create_exception(exc)

    # 1. DETECTED -> INVESTIGATING
    transition_exception_state(
        db_session,
        "exc_lifecycle_01",
        ExceptionState.INVESTIGATING,
        reason="Agent picked up exception for analysis",
        actor_type=TransitionActorType.AI_AGENT,
        actor_id="agent_v0.1",
    )
    assert repo.get_exception("exc_lifecycle_01").state == ExceptionState.INVESTIGATING.value

    # 2. INVESTIGATING -> DIAGNOSED
    transition_exception_state(
        db_session,
        "exc_lifecycle_01",
        ExceptionState.DIAGNOSED,
        reason="Root cause identified as gateway batch processing latency",
        actor_type=TransitionActorType.AI_AGENT,
        actor_id="agent_v0.1",
    )
    assert repo.get_exception("exc_lifecycle_01").state == ExceptionState.DIAGNOSED.value

    # 3. DIAGNOSED -> AWAITING_ACTION
    transition_exception_state(
        db_session,
        "exc_lifecycle_01",
        ExceptionState.AWAITING_ACTION,
        reason="Remediation plan generated, queued for finance controller approval",
        actor_type=TransitionActorType.SYSTEM,
    )
    assert repo.get_exception("exc_lifecycle_01").state == ExceptionState.AWAITING_ACTION.value

    # 4. AWAITING_ACTION -> RESOLVING
    transition_exception_state(
        db_session,
        "exc_lifecycle_01",
        ExceptionState.RESOLVING,
        reason="Finance controller approved ledger adjustment proposal",
        actor_type=TransitionActorType.FINANCE_CONTROLLER,
        actor_id="controller_anjali",
    )
    assert repo.get_exception("exc_lifecycle_01").state == ExceptionState.RESOLVING.value

    # 5. RESOLVING -> VERIFYING
    transition_exception_state(
        db_session,
        "exc_lifecycle_01",
        ExceptionState.VERIFYING,
        reason="Adjustment applied, initiating double-entry verification",
        actor_type=TransitionActorType.SYSTEM,
    )
    assert repo.get_exception("exc_lifecycle_01").state == ExceptionState.VERIFYING.value

    # 6. VERIFYING -> VERIFIED_CLOSED
    transition_exception_state(
        db_session,
        "exc_lifecycle_01",
        ExceptionState.VERIFIED_CLOSED,
        reason="Zero balance variance confirmed, exception resolved",
        actor_type=TransitionActorType.SYSTEM,
    )
    final_exc = repo.get_exception("exc_lifecycle_01")
    assert final_exc.state == ExceptionState.VERIFIED_CLOSED.value
    assert final_exc.resolved_at is not None

    # Check that all 6 transitions were recorded in the audit trail
    transitions = repo.get_state_transitions("exc_lifecycle_01")
    assert len(transitions) == 6
    assert transitions[0].from_state == ExceptionState.DETECTED.value
    assert transitions[0].to_state == ExceptionState.INVESTIGATING.value
    assert transitions[0].actor_type == TransitionActorType.AI_AGENT.value
    assert transitions[5].to_state == ExceptionState.VERIFIED_CLOSED.value


def test_alternative_failure_escalation_path(db_session):
    """Verify alternative escalation path from VERIFYING to FAILED_ESCALATED."""
    repo = ExceptionRepository(db_session)

    exc = ExceptionRecord(
        exception_id="exc_fail_esc_01",
        exception_type=ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value,
        severity=ExceptionSeverity.CRITICAL.value,
        state=ExceptionState.DETECTED.value,
        exposure=800000,
        detected_at=utc_now(),
    )
    repo.create_exception(exc)

    # DETECTED -> INVESTIGATING -> DIAGNOSED -> AWAITING_ACTION -> RESOLVING -> VERIFYING
    transition_exception_state(db_session, "exc_fail_esc_01", ExceptionState.INVESTIGATING)
    transition_exception_state(db_session, "exc_fail_esc_01", ExceptionState.DIAGNOSED)
    transition_exception_state(db_session, "exc_fail_esc_01", ExceptionState.AWAITING_ACTION)
    transition_exception_state(db_session, "exc_fail_esc_01", ExceptionState.RESOLVING)
    transition_exception_state(db_session, "exc_fail_esc_01", ExceptionState.VERIFYING)

    # Verification failure leads to FAILED_ESCALATED
    transition_exception_state(
        db_session,
        "exc_fail_esc_01",
        ExceptionState.FAILED_ESCALATED,
        reason="Double-entry invariant violated post-action; escalated to human tier 2",
        actor_type=TransitionActorType.SYSTEM,
    )

    final_exc = repo.get_exception("exc_fail_esc_01")
    assert final_exc.state == ExceptionState.FAILED_ESCALATED.value
    assert final_exc.resolved_at is not None


@pytest.mark.parametrize(
    "invalid_from, invalid_to",
    [
        (ExceptionState.DETECTED, ExceptionState.VERIFIED_CLOSED),
        (ExceptionState.DETECTED, ExceptionState.DIAGNOSED),
        (ExceptionState.DETECTED, ExceptionState.RESOLVING),
        (ExceptionState.INVESTIGATING, ExceptionState.VERIFIED_CLOSED),
        (ExceptionState.DIAGNOSED, ExceptionState.RESOLVING),  # Cannot skip AWAITING_ACTION
        (ExceptionState.VERIFIED_CLOSED, ExceptionState.INVESTIGATING),  # Cannot reopen closed
        (ExceptionState.FAILED_ESCALATED, ExceptionState.RESOLVING),
    ],
)
def test_invalid_state_transitions_are_rejected(db_session, invalid_from, invalid_to):
    """Verify that illegal transitions raise InvalidStateTransitionError and do not mutate state."""
    repo = ExceptionRepository(db_session)
    exc_id = f"exc_invalid_{invalid_from.value}_{invalid_to.value}"

    exc = ExceptionRecord(
        exception_id=exc_id,
        exception_type=ExceptionType.PARTIAL_SETTLEMENT.value,
        severity=ExceptionSeverity.LOW.value,
        state=invalid_from.value,
        detected_at=utc_now(),
    )
    repo.create_exception(exc)

    with pytest.raises(InvalidStateTransitionError):
        transition_exception_state(db_session, exc_id, invalid_to)

    # State must remain unchanged
    assert repo.get_exception(exc_id).state == invalid_from.value


def test_exception_affected_records_linkage(db_session):
    """Verify linking multiple affected financial records to an exception."""
    repo = ExceptionRepository(db_session)

    exc = ExceptionRecord(
        exception_id="exc_multi_aff_01",
        exception_type=ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DETECTED.value,
        detected_at=utc_now(),
    )
    repo.create_exception(exc)

    repo.add_affected_record(
        ExceptionAffectedRecord(
            exception_id="exc_multi_aff_01",
            record_type="settlement",
            record_identifier="stl_unknown_batch_99",
        )
    )
    repo.add_affected_record(
        ExceptionAffectedRecord(
            exception_id="exc_multi_aff_01",
            record_type="payment",
            record_identifier="pay_suspect_11",
        )
    )

    affected = repo.get_affected_records("exc_multi_aff_01")
    assert len(affected) == 2
    assert {r.record_type for r in affected} == {"settlement", "payment"}
