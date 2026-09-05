"""Comprehensive test suite for Nodexa Copilot LLM Tool-Calling Agent.

Verifies:
1. LLM Provider configuration and resilience (Gemini, OpenAI, mock fallback).
2. Read-only tool schema completeness (18 tools, strict parameter validation).
3. Natural-language query understanding across all financial domains (sales, refunds,
   settlements, merchants, exceptions, entities, cross-data comparisons).
4. Strict answer relevance guard (zero exception/exposure leakage on sales queries).
5. Deterministic multi-tool planning and synthesis.
6. Mutation rejection and boundary safety.
7. Missing data honesty and abstention.
8. Live LLM mock tool calling and graceful fallback.
"""
import os
import json
from unittest.mock import patch, MagicMock
import pytest
from sqlalchemy.orm import Session

from backend.models.database import SessionLocal
from backend.copilot.provider import CopilotLLMProvider
from backend.copilot.agent import (
    ASK_SENTINEL_TOOL_DEFINITIONS,
    DeterministicSemanticToolPlanner,
    CopilotToolCallingAgent,
)
from backend.copilot.tools import AskSentinelToolRegistry
from backend.copilot.service import AskSentinelService


@pytest.fixture(scope="module")
def setup_db():
    session = SessionLocal()
    yield session
    session.close()


# ---------------------------------------------------------------------------
# 1. Provider Configuration & Fallback
# ---------------------------------------------------------------------------

def test_provider_configuration_defaults():
    """Verifies default provider status when unconfigured."""
    with patch.dict(os.environ, {}, clear=True):
        status = CopilotLLMProvider.get_provider_status()
        assert status["provider_name"] == "mock"
        assert status["has_credentials"] is False
        assert status["is_real_llm_configured"] is False


def test_provider_configuration_gemini_without_key():
    """Gemini without API key must not claim real LLM is configured."""
    with patch.dict(os.environ, {"LLM_PROVIDER": "gemini"}, clear=True):
        status = CopilotLLMProvider.get_provider_status()
        assert status["provider_name"] == "gemini"
        assert status["is_real_llm_configured"] is False


def test_provider_configuration_gemini_with_key():
    """Gemini with API key is recognized as real LLM."""
    with patch.dict(os.environ, {"LLM_PROVIDER": "gemini", "LLM_API_KEY": "AIzaSyFakeKey123"}, clear=True):
        status = CopilotLLMProvider.get_provider_status()
        assert status["provider_name"] == "gemini"
        assert status["has_credentials"] is True
        assert status["is_real_llm_configured"] is True
        assert "gemini" in status["model"]


def test_provider_configuration_custom_model_and_url():
    """Custom model and base URL are respected."""
    with patch.dict(
        os.environ,
        {
            "LLM_PROVIDER": "openai",
            "LLM_API_KEY": "sk-fake-key",
            "LLM_MODEL": "gpt-4o",
            "LLM_BASE_URL": "https://custom.ai.proxy/v1",
        },
        clear=True,
    ):
        status = CopilotLLMProvider.get_provider_status()
        assert status["provider_name"] == "openai"
        assert status["model"] == "gpt-4o"
        assert status["is_real_llm_configured"] is True


# ---------------------------------------------------------------------------
# 2. Tool Schema Completeness
# ---------------------------------------------------------------------------

def test_tool_schema_completeness():
    """All 18 read-only tools must have valid JSON function definitions."""
    assert len(ASK_SENTINEL_TOOL_DEFINITIONS) == 18
    registry = AskSentinelToolRegistry()

    for tool in ASK_SENTINEL_TOOL_DEFINITIONS:
        assert tool["type"] == "function"
        fn = tool["function"]
        name = fn["name"]
        assert name in registry.ASK_SENTINEL_ALLOWED_TOOLS, f"Tool {name} not in registry allowlist"
        assert fn["description"] and len(fn["description"]) > 10
        assert "parameters" in fn
        assert fn["parameters"]["type"] == "object"


# ---------------------------------------------------------------------------
# 3. Sales Query Matrix (Relevance Guard & No Exception Leakage)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "how much money did we process?",
        "what did we process?",
        "what was our payment volume?",
        "how much did customers pay?",
        "total sales?",
        "how much money was processed?",
        "total payment volume",
        "what is the total transaction value?",
        "what is our total GMV?",
    ],
)
def test_sales_queries_route_correctly_and_protect_relevance(query, setup_db: Session):
    """Verifies all sales query variations route to get_sales_summary and NEVER leak exceptions."""
    service = AskSentinelService()
    res = service.ask(session=setup_db, question=query)

    assert res["abstained"] is False
    assert res["confidence"] == "HIGH"
    assert "get_sales_summary" in res["tools_used"]
    assert "₹" in res["answer"]
    assert any(w in res["answer"].lower() for w in ("sales", "volume", "processed", "payment"))

    # CRITICAL: Relevance guard verification
    forbidden_terms = ["exception", "incident", "exposure", "ghost_settlement", "anomal"]
    for term in forbidden_terms:
        assert term not in res["answer"].lower(), f"Forbidden term '{term}' found in sales answer for query: '{query}'"


# ---------------------------------------------------------------------------
# 4. Refund Query Matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "how much did we refund?",
        "what was refunded?",
        "how many refunds?",
        "total refunds",
        "what is our refund volume?",
    ],
)
def test_refund_queries_route_correctly(query, setup_db: Session):
    """Verifies refund query variations route to get_refunds_summary."""
    service = AskSentinelService()
    res = service.ask(session=setup_db, question=query)

    assert res["abstained"] is False
    assert "get_refunds_summary" in res["tools_used"]
    assert "refund" in res["answer"].lower()
    assert "₹" in res["answer"]


# ---------------------------------------------------------------------------
# 5. Settlement Queries Matrix
# ---------------------------------------------------------------------------

def test_settlement_volume_query(setup_db: Session):
    """Settlement volume query routes to get_settlements_summary."""
    service = AskSentinelService()
    res = service.ask(session=setup_db, question="what is our settlement volume?")

    assert res["abstained"] is False
    assert "get_settlements_summary" in res["tools_used"]
    assert "settlement" in res["answer"].lower()
    assert "₹" in res["answer"]


def test_unsettled_payments_query(setup_db: Session):
    """Queries about unsettled payments route to cross-source reconciliation."""
    service = AskSentinelService()
    res = service.ask(session=setup_db, question="which payments haven't settled?")

    assert res["abstained"] is False
    assert "get_cross_source_reconciliation" in res["tools_used"]
    assert "settled" in res["answer"].lower() or "unsettled" in res["answer"].lower()


def test_late_settlements_query(setup_db: Session):
    """Queries about late settlements route to cross-source reconciliation."""
    service = AskSentinelService()
    res = service.ask(session=setup_db, question="which settlements are late?")

    assert res["abstained"] is False
    assert "get_cross_source_reconciliation" in res["tools_used"]
    assert "sla" in res["answer"].lower() or "delay" in res["answer"].lower() or "settlement" in res["answer"].lower()


def test_average_settlement_time_honesty(setup_db: Session):
    """Queries about average settlement time return factual data or clear unavailability."""
    service = AskSentinelService()
    res = service.ask(session=setup_db, question="what is our average settlement time?")

    assert res["abstained"] is False
    assert "get_settlements_summary" in res["tools_used"]
    assert "clearing delay" in res["answer"].lower() or "delay" in res["answer"].lower()


# ---------------------------------------------------------------------------
# 6. Merchant Queries Matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "who processed the most?",
        "which merchant generated the most volume?",
        "which merchant has the highest refund rate?",
    ],
)
def test_merchant_rankings_queries(query, setup_db: Session):
    """Queries about merchant performance route to get_merchants_overview."""
    service = AskSentinelService()
    res = service.ask(session=setup_db, question=query)

    assert res["abstained"] is False
    assert "get_merchants_overview" in res["tools_used"]
    assert "merchant" in res["answer"].lower()


# ---------------------------------------------------------------------------
# 7. Exception Queries Matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "query",
    [
        "how many issues are open?",
        "what is our unresolved exposure?",
        "what is the biggest problem?",
    ],
)
def test_exception_queries_matrix(query, setup_db: Session):
    """Explicit exception questions route to get_aggregate_summary."""
    service = AskSentinelService()
    res = service.ask(session=setup_db, question=query)

    assert res["abstained"] is False
    assert "get_aggregate_summary" in res["tools_used"]
    assert "exception" in res["answer"].lower() or "exposure" in res["answer"].lower()


# ---------------------------------------------------------------------------
# 8. Specific Entity Queries
# ---------------------------------------------------------------------------

def test_specific_payment_lookup(setup_db: Session):
    """Queries targeting a payment ID route to get_payment."""
    service = AskSentinelService()
    res = service.ask(session=setup_db, question="tell me about PAY-000001")

    assert res["abstained"] is False
    assert "get_payment" in res["tools_used"]
    assert "PAY-000001" in res["evidence_refs"]
    assert "PAY-000001" in res["answer"]


def test_why_payment_flagged_multi_tool(setup_db: Session):
    """Investigating why a payment was flagged invokes payment, ledger, and settlements."""
    service = AskSentinelService()
    res = service.ask(session=setup_db, question="why was this payment flagged? PAY-000001")

    assert res["abstained"] is False
    assert "get_payment" in res["tools_used"]
    assert "get_ledger_entries" in res["tools_used"]
    assert "get_settlement" in res["tools_used"]
    assert "PAY-000001" in res["evidence_refs"]


def test_specific_exception_lookup(setup_db: Session):
    """Queries targeting an exception ID route to get_exception."""
    service = AskSentinelService()
    exc_id = "EXC-GHOST_SETTLEMENT-PAY-000001"
    res = service.ask(session=setup_db, question=f"what is exception {exc_id}?")

    assert res["abstained"] is False
    assert "get_exception" in res["tools_used"]
    assert exc_id in res["evidence_refs"]
    assert exc_id in res["answer"]


# ---------------------------------------------------------------------------
# 9. Multi-Tool Reasoning & Cross-Source Reconciliation
# ---------------------------------------------------------------------------

def test_multi_tool_net_sales(setup_db: Session):
    """Net sales requires calling both sales and refunds summaries."""
    service = AskSentinelService()
    res = service.ask(session=setup_db, question="what is our net sales?")

    assert res["abstained"] is False
    assert "get_sales_summary" in res["tools_used"]
    assert "get_refunds_summary" in res["tools_used"]
    assert "net sales" in res["answer"].lower()


def test_compare_payments_with_settlements(setup_db: Session):
    """Comparing payments with settlements invokes cross-source reconciliation and settlement summaries."""
    service = AskSentinelService()
    res = service.ask(session=setup_db, question="compare payments with settlements")

    assert res["abstained"] is False
    assert "get_cross_source_reconciliation" in res["tools_used"]
    assert "settlement" in res["answer"].lower()


def test_ledger_mismatches_query(setup_db: Session):
    """Queries about ledger mismatches route to cross-source reconciliation."""
    service = AskSentinelService()
    res = service.ask(session=setup_db, question="which transactions have ledger mismatches?")

    assert res["abstained"] is False
    assert "get_cross_source_reconciliation" in res["tools_used"]
    assert "reconciliation" in res["answer"].lower() or "ledger" in res["answer"].lower()


# ---------------------------------------------------------------------------
# 10. Boundary Safety & Mutation Rejection
# ---------------------------------------------------------------------------

def test_mutation_commands_rejected(setup_db: Session):
    """Write/mutation attempts are rejected unconditionally."""
    service = AskSentinelService()
    mutations = [
        "delete exception EXC-000001",
        "drop table gateway_transactions",
        "update payment PAY-000001 set amount=9999",
        "override policy rule to APPROVE",
    ]
    for cmd in mutations:
        res = service.ask(session=setup_db, question=cmd)
        assert res["abstained"] is True
        assert res["confidence"] == "LOW"
        assert "read-only" in res["answer"].lower() or "cannot" in res["answer"].lower() or "mutation" in res["answer"].lower()


# ---------------------------------------------------------------------------
# 11. Missing Data Honesty
# ---------------------------------------------------------------------------

def test_missing_entity_honesty(setup_db: Session):
    """Querying a non-existent payment abstains without hallucinations."""
    service = AskSentinelService()
    res = service.ask(session=setup_db, question="tell me about payment PAY-DOES-NOT-EXIST-404")

    assert res["abstained"] is True
    assert res["confidence"] == "LOW"
    assert "not found" in res["answer"].lower() or "no matching" in res["answer"].lower()


# ---------------------------------------------------------------------------
# 12. Remote LLM Tool-Calling Mock & Fallback
# ---------------------------------------------------------------------------

def test_remote_llm_tool_calling_flow(setup_db: Session):
    """Tests the full remote LLM flow with mock HTTP tool planning and synthesis."""
    mock_plan_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Selected sales summary tool based on user question.",
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "get_sales_summary",
                                "arguments": json.dumps({"merchant_id": None}),
                            },
                        }
                    ],
                }
            }
        ]
    }

    mock_synth_response = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Based on Nodexa records, gross sales total ₹54,200.00 across 60 transactions.",
                }
            }
        ]
    }

    with patch.dict(
        os.environ,
        {"LLM_PROVIDER": "openai", "LLM_API_KEY": "sk-mock-key-for-test"},
        clear=True,
    ):
        with patch("httpx.Client.post") as mock_post:
            resp_plan = MagicMock()
            resp_plan.json.return_value = mock_plan_response
            resp_plan.raise_for_status.return_value = None

            resp_synth = MagicMock()
            resp_synth.json.return_value = mock_synth_response
            resp_synth.raise_for_status.return_value = None

            mock_post.side_effect = [resp_plan, resp_synth]

            service = AskSentinelService()
            res = service.ask(session=setup_db, question="how much money did we process?")

            assert res["abstained"] is False
            assert "get_sales_summary" in res["tools_used"]
            assert "₹54,200.00" in res["answer"]
            assert res["provider_metadata"]["provider"] == "openai"
            assert res["provider_metadata"]["is_real_llm"] is True


def test_remote_llm_fallback_on_error(setup_db: Session):
    """When remote LLM throws an HTTP 500, fallback to deterministic planner seamlessly."""
    with patch.dict(
        os.environ,
        {"LLM_PROVIDER": "openai", "LLM_API_KEY": "sk-mock-key-for-test"},
        clear=True,
    ):
        with patch("httpx.Client.post", side_effect=Exception("Connection refused / 500 error")):
            service = AskSentinelService()
            res = service.ask(session=setup_db, question="how much money did we process?")

            # Must still succeed via local deterministic fallback
            assert res["abstained"] is False
            assert "get_sales_summary" in res["tools_used"]
            assert "₹" in res["answer"]
            assert res["provider_metadata"]["is_real_llm"] is False
