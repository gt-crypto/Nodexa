"""Comprehensive failure mode and resilience tests for AI Investigation Engine."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import ExceptionState, InvestigationStatus
from backend.models.exceptions import ExceptionRecord
from backend.models.investigation import InvestigationRun
from backend.models.financial_sources import GatewayTransaction, BankSettlementBatch
from backend.agent.service import InvestigationService
from backend.agent.provider import (
    LLMProvider,
    StructuredInvestigationOutput,
    EvidenceCitation,
    RootCauseCategory,
)
from backend.agent.graph.investigator import InvestigationGraph


class TimeoutMockLLMProvider(LLMProvider):
    """Simulates persistent LLM timeout errors across all retry attempts."""
    def __init__(self):
        self.call_attempts = 0

    def generate_investigation(self, system_prompt, user_content, context=None):
        self.call_attempts += 1
        raise TimeoutError("Simulated LLM Gateway Timeout after 30000ms.")


class MalformedOutputMockLLMProvider(LLMProvider):
    """Simulates malformed / invalid schema responses from provider."""
    def generate_investigation(self, system_prompt, user_content, context=None):
        # Returns invalid output violating schema requirements
        raise ValueError("Malformed JSON payload: Missing required field 'root_cause_category'.")


class DivergentExposureMockLLMProvider(LLMProvider):
    """Simulates a rogue LLM returning an unauthorized different financial exposure."""
    def generate_investigation(self, system_prompt, user_content, context=None):
        return StructuredInvestigationOutput(
            investigation_status="SUCCESS",
            root_cause="Rogue exposure calculation test.",
            root_cause_category=RootCauseCategory.OTHER.value,
            confidence="HIGH",
            confidence_reason="Test reason.",
            evidence=[],
            contradictions=[],
            missing_information=[],
            exposure_assessment=999999999,  # Divergent value!
            explanation="### Facts\n- Fact\n\n### Hypothesis\n- Hypo\n\n### Conclusion\n- Concl",
            recommended_next_step="No action.",
        )


def test_provider_timeout_bounded_retries_and_escalation(db_session: Session):
    """Verifies that persistent provider timeouts retry up to max_retries and escalate to FAILED_ESCALATED."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-FAIL-TIMEOUT-1",
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

    timeout_provider = TimeoutMockLLMProvider()
    graph = InvestigationGraph(llm_provider=timeout_provider, max_retries=2)
    state = graph.run(session=db_session, exception_id="EXC-FAIL-TIMEOUT-1")
    db_session.commit()

    # Bounded retries: 1 initial attempt + 2 retries = 3 attempts total
    assert timeout_provider.call_attempts == 3
    assert state.status == "FAILED"

    # Verify exception transitioned to FAILED_ESCALATED
    updated_exc = db_session.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == "EXC-FAIL-TIMEOUT-1")).first()
    assert updated_exc.state == ExceptionState.FAILED_ESCALATED.value

    # Verify InvestigationRun is recorded with status = FAILED
    run = db_session.scalars(select(InvestigationRun).where(InvestigationRun.exception_id == "EXC-FAIL-TIMEOUT-1")).first()
    assert run is not None
    assert run.status == InvestigationStatus.FAILED.value
    assert "Timeout" in run.error_info


def test_malformed_output_rejection_and_escalation(db_session: Session):
    """Verifies that malformed provider outputs fail validation and escalate safely."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-FAIL-MALFORMED-1",
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

    malformed_provider = MalformedOutputMockLLMProvider()
    graph = InvestigationGraph(llm_provider=malformed_provider, max_retries=1)
    state = graph.run(session=db_session, exception_id="EXC-FAIL-MALFORMED-1")
    db_session.commit()

    assert state.status == "FAILED"
    updated_exc = db_session.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == "EXC-FAIL-MALFORMED-1")).first()
    assert updated_exc.state == ExceptionState.FAILED_ESCALATED.value


def test_exposure_authority_enforced_against_divergent_ai_output(db_session: Session):
    """Verifies that deterministic Prompt 4 exposure overrides any divergent exposure returned by the LLM."""
    now = datetime.now(timezone.utc)
    pmt = GatewayTransaction(
        payment_id="PAY-EXP-AUTH-1",
        merchant_id="M1",
        amount=3500000,
        currency="INR",
        status="FAILED",
        created_at=now,
        method="CARD",
    )
    settle = BankSettlementBatch(
        settlement_id="SET-EXP-AUTH-1",
        payment_id="PAY-EXP-AUTH-1",
        acquirer_id="A1",
        net_amount=3447500,
        clearing_timestamp=now,
    )
    exc = ExceptionRecord(
        exception_id="EXC-EXP-AUTH-1",
        exception_type="GHOST_SETTLEMENT",
        severity="HIGH",
        state=ExceptionState.DETECTED.value,
        exposure=3447500,  # Authoritative deterministic exposure
        primary_payment_id="PAY-EXP-AUTH-1",
        detected_at=now,
        created_at=now,
    )
    db_session.add_all([pmt, settle, exc])
    db_session.commit()

    divergent_provider = DivergentExposureMockLLMProvider()
    graph = InvestigationGraph(llm_provider=divergent_provider)
    state = graph.run(session=db_session, exception_id="EXC-EXP-AUTH-1")
    db_session.commit()

    assert state.status == "COMPLETED"
    assert state.structured_output is not None

    # The authoritative deterministic exposure MUST prevail over the rogue 999,999,999
    assert state.structured_output.exposure_assessment == 3447500


def test_insufficient_evidence_preserves_ambiguity(db_session: Session):
    """Verifies that an orphan settlement without payment mapping preserves ambiguity and assigns MEDIUM confidence."""
    now = datetime.now(timezone.utc)
    orphan_settle = BankSettlementBatch(
        settlement_id="SET-ORPHAN-TEST-1",
        utr_number="UTR-ORPHAN-99",
        acquirer_id="A1",
        payment_id=None,
        net_amount=2000000,
        clearing_timestamp=now,
    )
    exc = ExceptionRecord(
        exception_id="EXC-UNALLOCATED-SET-ORPHAN-TEST-1",
        exception_type="MISSING_UNALLOCATED_SETTLEMENT",
        severity="HIGH",
        state=ExceptionState.DETECTED.value,
        exposure=2000000,
        primary_payment_id=None,
        detected_at=now,
        created_at=now,
    )
    db_session.add_all([orphan_settle, exc])
    db_session.commit()

    service = InvestigationService()
    result = service.investigate_exception(session=db_session, exception_id="EXC-UNALLOCATED-SET-ORPHAN-TEST-1")

    assert result["status"] == "COMPLETED"
    output = result["structured_output"]
    assert output["root_cause_category"] == RootCauseCategory.UNALLOCATED_FUNDS.value
    assert output["confidence"] == "MEDIUM"
    assert len(output["missing_information"]) >= 1
