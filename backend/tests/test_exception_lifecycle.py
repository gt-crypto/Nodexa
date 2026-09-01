"""Unit tests for exception lifecycle state machine, transitions, affected records, and audit logging."""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import ExceptionState, ExceptionType, TransitionActorType, LedgerEntryType
from backend.models.exceptions import ExceptionRecord, ExceptionStateTransition, ExceptionAffectedRecord
from backend.models.audit import AuditEvent
from backend.controls.state_machine import transition_exception_state, InvalidStateTransitionError
from backend.models.financial_sources import GatewayTransaction, BankSettlementBatch, NodalLedgerEntry
from backend.exceptions.service import ExceptionDetectionService


def test_exception_lifecycle_initial_state_and_audit(db_session: Session):
    """Verifies that new exceptions start at DETECTED with state transitions and audit events recorded."""
    now = datetime.now(timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-LC-1",
        merchant_id="M1",
        amount=1000000,
        currency="INR",
        status="FAILED",
        created_at=now,
        method="CARD",
    )
    settlement = BankSettlementBatch(
        settlement_id="SET-LC-1",
        payment_id="PAY-LC-1",
        acquirer_id="A1",
        net_amount=985000,
        clearing_timestamp=now,
    )
    ledger = NodalLedgerEntry(
        ledger_id="LED-LC-1",
        transaction_id="PAY-LC-1",
        account_id="nodal_escrow_main",
        debit=0,
        credit=985000,
        balance_after=985000,
        timestamp=now,
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
    )

    db_session.add_all([payment, settlement, ledger])
    db_session.commit()

    service = ExceptionDetectionService()
    report = service.detect_exceptions(session=db_session)
    assert report.new_exception_count == 1

    exc_id = "EXC-GHOST_SETTLEMENT-PAY-LC-1"
    exc_rec = db_session.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == exc_id)).first()
    assert exc_rec is not None
    assert exc_rec.state == ExceptionState.DETECTED.value

    # Check state transitions
    transitions = list(db_session.scalars(select(ExceptionStateTransition).where(ExceptionStateTransition.exception_id == exc_id)).all())
    assert len(transitions) == 1
    assert transitions[0].from_state == "NONE"
    assert transitions[0].to_state == ExceptionState.DETECTED.value
    assert transitions[0].actor_type == TransitionActorType.SYSTEM.value

    # Check affected records
    aff_records = list(db_session.scalars(select(ExceptionAffectedRecord).where(ExceptionAffectedRecord.exception_id == exc_id)).all())
    assert len(aff_records) >= 2

    # Check audit events
    audit_events = list(db_session.scalars(select(AuditEvent).where(AuditEvent.exception_id == exc_id)).all())
    assert len(audit_events) == 1
    assert audit_events[0].event_type == "EXCEPTION_DETECTED"
    assert audit_events[0].actor_type == TransitionActorType.SYSTEM.value


def test_state_machine_transition_from_detected_to_investigating(db_session: Session):
    """Verifies that transitioning from DETECTED to INVESTIGATING succeeds while illegal jumps are rejected."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-TEST-SM-1",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="HIGH",
        state=ExceptionState.DETECTED.value,
        exposure=100000,
        detected_at=now,
        created_at=now,
    )
    db_session.add(exc)
    db_session.commit()

    # Illegal transition: DETECTED -> DIAGNOSED
    with pytest.raises(InvalidStateTransitionError):
        transition_exception_state(db_session, "EXC-TEST-SM-1", to_state=ExceptionState.DIAGNOSED)

    # Illegal transition: DETECTED -> VERIFIED_CLOSED
    with pytest.raises(InvalidStateTransitionError):
        transition_exception_state(db_session, "EXC-TEST-SM-1", to_state=ExceptionState.VERIFIED_CLOSED)

    # Valid transition: DETECTED -> INVESTIGATING
    updated_exc = transition_exception_state(
        db_session,
        "EXC-TEST-SM-1",
        to_state=ExceptionState.INVESTIGATING,
        reason="AI Investigator assigned case.",
        actor_type=TransitionActorType.SYSTEM,
    )
    db_session.commit()
    assert updated_exc.state == ExceptionState.INVESTIGATING.value
