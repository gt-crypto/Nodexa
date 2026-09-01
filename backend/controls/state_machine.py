"""Deterministic state machine and transition validation for Nodal Sentinel exceptions."""
import uuid
from datetime import datetime, timezone
from typing import Optional, Set
from sqlalchemy.orm import Session

from backend.models.enums import ExceptionState, TransitionActorType
from backend.models.exceptions import ExceptionRecord, ExceptionStateTransition


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal exception state transition is attempted."""
    def __init__(self, from_state: str, to_state: str, message: Optional[str] = None):
        self.from_state = from_state
        self.to_state = to_state
        msg = message or f"Illegal state transition from '{from_state}' to '{to_state}'."
        super().__init__(msg)


# Allowed state transition map
ALLOWED_TRANSITIONS: dict[ExceptionState, Set[ExceptionState]] = {
    ExceptionState.DETECTED: {
        ExceptionState.INVESTIGATING,
        ExceptionState.FAILED_ESCALATED,
    },
    ExceptionState.INVESTIGATING: {
        ExceptionState.DIAGNOSED,
        ExceptionState.FAILED_ESCALATED,
    },
    ExceptionState.DIAGNOSED: {
        ExceptionState.INVESTIGATING,
        ExceptionState.AWAITING_ACTION,
        ExceptionState.VERIFYING,
        ExceptionState.VERIFIED_CLOSED,
        ExceptionState.FAILED_ESCALATED,
    },
    ExceptionState.AWAITING_ACTION: {
        ExceptionState.RESOLVING,
        ExceptionState.FAILED_ESCALATED,
    },
    ExceptionState.RESOLVING: {
        ExceptionState.VERIFYING,
        ExceptionState.FAILED_ESCALATED,
    },
    ExceptionState.VERIFYING: {
        ExceptionState.VERIFIED_CLOSED,
        ExceptionState.FAILED_ESCALATED,
    },
    # Terminal states
    ExceptionState.VERIFIED_CLOSED: set(),
    ExceptionState.FAILED_ESCALATED: set(),
}


def is_valid_transition(from_state: ExceptionState | str, to_state: ExceptionState | str) -> bool:
    """Validates whether transitioning from from_state to to_state is allowed."""
    from_enum = ExceptionState(from_state) if isinstance(from_state, str) else from_state
    to_enum = ExceptionState(to_state) if isinstance(to_state, str) else to_state

    allowed_targets = ALLOWED_TRANSITIONS.get(from_enum, set())
    return to_enum in allowed_targets


def transition_exception_state(
    session: Session,
    exception_id: str,
    to_state: ExceptionState | str,
    reason: Optional[str] = None,
    actor_type: TransitionActorType | str = TransitionActorType.SYSTEM,
    actor_id: Optional[str] = None,
) -> ExceptionRecord:
    """Deterministically validates and transitions an exception record to a new state.
    
    Persists an immutable ExceptionStateTransition audit record.
    Raises InvalidStateTransitionError if the requested transition is illegal.
    """
    exc = session.query(ExceptionRecord).filter(ExceptionRecord.exception_id == exception_id).first()
    if not exc:
        raise ValueError(f"Exception record with id '{exception_id}' not found.")

    current_state = ExceptionState(exc.state)
    target_state = ExceptionState(to_state) if isinstance(to_state, str) else to_state
    actor_type_val = actor_type.value if isinstance(actor_type, TransitionActorType) else actor_type

    if not is_valid_transition(current_state, target_state):
        raise InvalidStateTransitionError(
            from_state=current_state.value,
            to_state=target_state.value,
            message=f"Cannot transition exception '{exception_id}' from '{current_state.value}' to '{target_state.value}'.",
        )

    # Apply state change
    exc.state = target_state.value
    now = datetime.now(timezone.utc)
    exc.updated_at = now
    if target_state in (ExceptionState.VERIFIED_CLOSED, ExceptionState.FAILED_ESCALATED):
        exc.resolved_at = now

    # Append immutable transition record
    transition = ExceptionStateTransition(
        transition_id=f"trans_{uuid.uuid4().hex[:16]}",
        exception_id=exception_id,
        from_state=current_state.value,
        to_state=target_state.value,
        timestamp=now,
        reason=reason,
        actor_type=actor_type_val,
        actor_id=actor_id,
    )
    session.add(transition)
    session.flush()

    return exc
