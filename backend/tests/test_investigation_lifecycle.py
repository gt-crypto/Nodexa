"""Unit tests for AI investigation lifecycle state transitions, runs persistence, and audit logs."""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import ExceptionState, TransitionActorType, InvestigationStatus, LedgerEntryType
from backend.models.exceptions import ExceptionRecord, ExceptionStateTransition
from backend.models.investigation import InvestigationRun
from backend.models.audit import AuditEvent
from backend.models.financial_sources import GatewayTransaction, BankSettlementBatch, NodalLedgerEntry
from backend.agent.service import InvestigationService
from backend.agent.provider import LLMProvider, StructuredInvestigationOutput


class FailingMockLLMProvider(LLMProvider):
    """Mock LLM provider that simulates provider/network failures."""
    def generate_investigation(self, system_prompt, user_content, context=None):
        raise RuntimeError("Simulated LLM Provider Timeout.")


def test_investigation_successful_lifecycle(db_session: Session):
    """Verifies DETECTED -> INVESTIGATING -> DIAGNOSED lifecycle transition and InvestigationRun persistence."""
    now = datetime.now(timezone.utc)
    pmt = GatewayTransaction(
        payment_id="PAY-LC-AI-1",
        merchant_id="M1",
        amount=2000000,
        currency="INR",
        status="FAILED",
        created_at=now,
        method="CARD",
    )
    settle = BankSettlementBatch(
        settlement_id="SET-LC-AI-1",
        payment_id="PAY-LC-AI-1",
        acquirer_id="A1",
        net_amount=1970000,
        clearing_timestamp=now,
    )
    exc = ExceptionRecord(
        exception_id="EXC-GHOST-LC-1",
        exception_type="GHOST_SETTLEMENT",
        severity="CRITICAL",
        state=ExceptionState.DETECTED.value,
        exposure=1970000,
        primary_payment_id="PAY-LC-AI-1",
        detected_at=now,
        created_at=now,
    )
    db_session.add_all([pmt, settle, exc])
    db_session.commit()

    service = InvestigationService()
    result = service.investigate_exception(session=db_session, exception_id="EXC-GHOST-LC-1")

    assert result["status"] == "COMPLETED"
    assert result["structured_output"] is not None

    # Check updated exception record state in DB
    updated_exc = db_session.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == "EXC-GHOST-LC-1")).first()
    assert updated_exc.state == ExceptionState.DIAGNOSED.value

    # Check InvestigationRun persisted in DB
    run = db_session.scalars(select(InvestigationRun).where(InvestigationRun.exception_id == "EXC-GHOST-LC-1")).first()
    assert run is not None
    assert run.status == InvestigationStatus.COMPLETED.value
    assert run.final_classification == "PAYMENT_STATE_CONTRADICTION"
    assert run.confidence is not None

    # Check State Transitions recorded with actor_type = AI_AGENT
    transitions = list(db_session.scalars(select(ExceptionStateTransition).where(ExceptionStateTransition.exception_id == "EXC-GHOST-LC-1")).all())
    to_states = [t.to_state for t in transitions]
    assert ExceptionState.INVESTIGATING.value in to_states
    assert ExceptionState.DIAGNOSED.value in to_states
    assert any(t.actor_type == TransitionActorType.AI_AGENT.value for t in transitions)

    # Check AuditEvent recorded
    audit_events = list(db_session.scalars(select(AuditEvent).where(AuditEvent.exception_id == "EXC-GHOST-LC-1")).all())
    assert len(audit_events) >= 1
    assert audit_events[0].event_type == "INVESTIGATION_COMPLETED"
    assert audit_events[0].actor_type == TransitionActorType.AI_AGENT.value


def test_investigation_failure_escalation_lifecycle(db_session: Session):
    """Verifies DETECTED -> INVESTIGATING -> FAILED_ESCALATED lifecycle transition upon provider failure."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-FAIL-LC-1",
        exception_type="GHOST_SETTLEMENT",
        severity="HIGH",
        state=ExceptionState.DETECTED.value,
        exposure=500000,
        primary_payment_id="PAY-NONE",
        detected_at=now,
        created_at=now,
    )
    db_session.add(exc)
    db_session.commit()

    failing_service = InvestigationService(llm_provider=FailingMockLLMProvider())
    result = failing_service.investigate_exception(session=db_session, exception_id="EXC-FAIL-LC-1")

    assert result["status"] == "FAILED"

    # Check exception escalated to FAILED_ESCALATED
    updated_exc = db_session.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == "EXC-FAIL-LC-1")).first()
    assert updated_exc.state == ExceptionState.FAILED_ESCALATED.value

    # Check InvestigationRun persisted with status = FAILED
    run = db_session.scalars(select(InvestigationRun).where(InvestigationRun.exception_id == "EXC-FAIL-LC-1")).first()
    assert run is not None
    assert run.status == InvestigationStatus.FAILED.value
    assert "Timeout" in run.error_info
