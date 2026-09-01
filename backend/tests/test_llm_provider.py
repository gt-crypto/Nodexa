"""Unit tests for LLM provider abstraction and structured output validation."""
import pytest
from backend.agent.provider import (
    DeterministicMockLLMProvider,
    StructuredInvestigationOutput,
    RootCauseCategory,
    EvidenceCitation,
    get_llm_provider,
)
from backend.agent.prompts.system_prompt import INVESTIGATOR_SYSTEM_PROMPT


def test_deterministic_mock_provider_structured_output():
    """Verifies that the mock LLM provider generates valid structured output adhering to schema."""
    provider = DeterministicMockLLMProvider()
    context = {
        "exception_type": "GHOST_SETTLEMENT",
        "primary_payment_id": "PAY-MOCK-1",
        "exposure": 4500000,
        "evidence": [
            {"source": "gateway_transactions", "record_id": "PAY-MOCK-1", "field": "status", "value": "FAILED"},
            {"source": "bank_settlement_batches", "record_id": "SET-MOCK-1", "field": "net_amount", "value": 4500000},
        ],
    }

    output = provider.generate_investigation(
        system_prompt=INVESTIGATOR_SYSTEM_PROMPT,
        user_content="Investigate PAY-MOCK-1",
        context=context,
    )

    assert isinstance(output, StructuredInvestigationOutput)
    assert output.investigation_status == "SUCCESS"
    assert output.root_cause_category == RootCauseCategory.PAYMENT_STATE_CONTRADICTION.value
    assert output.confidence == "HIGH"
    assert output.exposure_assessment == 4500000
    assert len(output.evidence) == 2
    assert "Facts" in output.explanation
    assert "Hypothesis" in output.explanation
    assert "Conclusion" in output.explanation


def test_get_llm_provider_factory():
    """Verifies provider factory defaults to DeterministicMockLLMProvider for offline safety."""
    prov = get_llm_provider("mock")
    assert isinstance(prov, DeterministicMockLLMProvider)


def test_structured_output_schema_validation():
    """Verifies Pydantic validation rejects invalid fields."""
    with pytest.raises(Exception):
        # Missing required fields
        StructuredInvestigationOutput(
            investigation_status="SUCCESS",
            root_cause="Test",
            # missing root_cause_category, confidence, etc.
        )
