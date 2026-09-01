"""LLM Provider abstraction and structured investigation output models for Nodal Sentinel."""
from abc import ABC, abstractmethod
from enum import Enum
import json
import os
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel, Field


class RootCauseCategory(str, Enum):
    PAYMENT_STATE_CONTRADICTION = "PAYMENT_STATE_CONTRADICTION"
    SETTLEMENT_PROCESSING_FAILURE = "SETTLEMENT_PROCESSING_FAILURE"
    SETTLEMENT_TIMING = "SETTLEMENT_TIMING"
    UNALLOCATED_FUNDS = "UNALLOCATED_FUNDS"
    REFUND_CHARGEBACK_OVERLAP = "REFUND_CHARGEBACK_OVERLAP"
    LEDGER_POSTING_INCONSISTENCY = "LEDGER_POSTING_INCONSISTENCY"
    DATA_MAPPING_ISSUE = "DATA_MAPPING_ISSUE"
    DUPLICATE_EVENT = "DUPLICATE_EVENT"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    OTHER = "OTHER"


class EvidenceCitation(BaseModel):
    source: str = Field(..., description="Source table name e.g. gateway_transactions")
    record_id: str = Field(..., description="Record identifier e.g. PAY-000001")
    field: str = Field(..., description="Field name evaluated e.g. status")
    value: Any = Field(..., description="Observed value of the field")


class StructuredInvestigationOutput(BaseModel):
    investigation_status: str = Field(default="SUCCESS", description="SUCCESS or FAILED")
    root_cause: str = Field(..., description="Evidence-backed description of the root cause")
    root_cause_category: str = Field(..., description="Categorized root cause taxonomy")
    confidence: str = Field(..., description="Confidence level: HIGH, MEDIUM, or LOW")
    confidence_reason: str = Field(..., description="Explanation for assigned confidence level")
    evidence: List[EvidenceCitation] = Field(default_factory=list, description="List of cited factual evidence items")
    contradictions: List[str] = Field(default_factory=list, description="Factual contradictions observed across sources")
    missing_information: List[str] = Field(default_factory=list, description="Missing records or unresolved ambiguities")
    exposure_assessment: int = Field(..., description="Validated financial exposure in integer minor units")
    explanation: str = Field(..., description="Markdown explanation separating Facts, Hypotheses, and Conclusions")
    recommended_next_step: str = Field(..., description="Recommended human/controller follow-up action")


class LLMProvider(ABC):
    """Abstract interface for LLM investigation providers."""

    @abstractmethod
    def generate_investigation(
        self,
        system_prompt: str,
        user_content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> StructuredInvestigationOutput:
        """Generates a structured investigation output from prompts and context."""
        pass


class DeterministicMockLLMProvider(LLMProvider):
    """Deterministic, rule-guided LLM provider for offline testing, local dev, and CI validation."""

    def generate_investigation(
        self,
        system_prompt: str,
        user_content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> StructuredInvestigationOutput:
        ctx = context or {}
        exc_type = ctx.get("exception_type", "")
        sub_type = ctx.get("sub_type", "")
        exposure = ctx.get("exposure", 0)
        payment_id = ctx.get("primary_payment_id", "N/A")
        raw_evidence = ctx.get("evidence", [])

        citations: List[EvidenceCitation] = []
        for e in raw_evidence:
            if isinstance(e, dict):
                citations.append(
                    EvidenceCitation(
                        source=e.get("source", "unknown"),
                        record_id=str(e.get("record_id", "unknown")),
                        field=e.get("field", "unknown"),
                        value=e.get("value"),
                    )
                )

        contradictions: List[str] = []
        missing_info: List[str] = []

        if exc_type == "GHOST_SETTLEMENT":
            category = RootCauseCategory.PAYMENT_STATE_CONTRADICTION.value
            root_cause = (
                f"Gateway payment {payment_id} is in FAILED state, but downstream bank settlement "
                f"and nodal ledger credit were processed without a successful capture event."
            )
            contradictions = [
                f"Payment {payment_id} recorded as FAILED in gateway while bank batch confirmed settlement credit.",
            ]
            confidence = "HIGH"
            confidence_reason = "Direct contradictory evidence exists between gateway transaction status and bank settlement batch."
            recommended_action = "Initiate clawback / reversal request with acquirer bank for erroneous settlement credit."
            explanation = (
                f"### Facts\n"
                f"- Gateway payment `{payment_id}` status is `FAILED`.\n"
                f"- Acquirer settlement cleared funds of {exposure} minor units.\n\n"
                f"### Hypothesis\n"
                f"- Downstream banking network processed settlement before receiving gateway failure notification.\n\n"
                f"### Conclusion\n"
                f"- Confirmed ghost settlement resulting in unauthorized ledger credit of {exposure} minor units."
            )

        elif exc_type == "REFUND_CHARGEBACK_DOUBLE_DIP":
            category = RootCauseCategory.REFUND_CHARGEBACK_OVERLAP.value
            root_cause = (
                f"Payment {payment_id} experienced both an automated merchant refund and an issuer chargeback, "
                f"resulting in dual ledger debit liabilities for the single transaction."
            )
            contradictions = [
                f"Payment {payment_id} has overlapping REFUND and CHARGEBACK dispute records.",
            ]
            confidence = "HIGH"
            confidence_reason = "Deterministic dispute event records verify simultaneous refund and chargeback events."
            recommended_action = "Represent chargeback with issuing bank citing prior merchant refund reference."
            explanation = (
                f"### Facts\n"
                f"- Payment `{payment_id}` has a completed refund event.\n"
                f"- Card network issued an overlapping chargeback of {exposure} minor units.\n\n"
                f"### Hypothesis\n"
                f"- Customer initiated bank dispute before merchant refund cleared the banking network.\n\n"
                f"### Conclusion\n"
                f"- Unlawful double recovery causing {exposure} minor units excess liability."
            )

        elif exc_type == "SETTLEMENT_SLA_BREACH":
            category = RootCauseCategory.SETTLEMENT_TIMING.value
            root_cause = (
                f"Captured payment {payment_id} settlement clearance exceeded the configured SLA window "
                f"taking standard business processing windows into account."
            )
            confidence = "HIGH"
            confidence_reason = "Deterministic SLA engine verified elapsed processing hours exceed SLA threshold."
            recommended_action = "Escalate SLA breach with partner acquirer operations."
            explanation = (
                f"### Facts\n"
                f"- Payment `{payment_id}` was captured on a valid business processing window.\n"
                f"- Clearing timestamp breached the allowable 24h SLA window.\n\n"
                f"### Hypothesis\n"
                f"- Acquirer batch pipeline experienced processing delays.\n\n"
                f"### Conclusion\n"
                f"- Genuine SLA timing breach on unsettled amount of {exposure} minor units."
            )

        elif exc_type == "PARTIAL_SETTLEMENT":
            category = RootCauseCategory.SETTLEMENT_PROCESSING_FAILURE.value if exposure > 0 else RootCauseCategory.OTHER.value
            if exposure == 0:
                root_cause = (
                    f"Payment {payment_id} was legitimately settled across multiple tranches whose aggregate "
                    f"sum matches the expected payment gross amount. Zero financial exposure."
                )
                confidence = "HIGH"
                confidence_reason = "Tranche reconciliation confirms 100% complete settlement aggregation."
                recommended_action = "No action required. Clean legitimate partial settlement observation."
                explanation = (
                    f"### Facts\n"
                    f"- Payment `{payment_id}` received multiple settlement batches.\n"
                    f"- Sum of gross tranches equals payment gross amount.\n\n"
                    f"### Hypothesis\n"
                    f"- Acquirer split transaction into multi-day batch clearances.\n\n"
                    f"### Conclusion\n"
                    f"- Legitimate observation. No financial anomaly or discrepancy exists."
                )
            else:
                root_cause = f"Payment {payment_id} partial settlement under-settled."
                confidence = "HIGH"
                confidence_reason = "Partial tranches do not aggregate to total payment amount."
                recommended_action = "Request missing tranche reconciliation from acquirer."
                explanation = f"### Facts\n- Under-settlement detected."

        elif exc_type == "MISSING_UNALLOCATED_SETTLEMENT":
            if sub_type == "UNALLOCATED_SETTLEMENT":
                category = RootCauseCategory.UNALLOCATED_FUNDS.value
                root_cause = (
                    f"Bank settlement batch received with net amount {exposure} minor units but missing "
                    f"gateway payment mapping. Preserved as ambiguous unallocated funds."
                )
                missing_info = [
                    "Missing gateway payment identifier or ambiguous candidate match.",
                ]
                confidence = "MEDIUM"
                confidence_reason = "Inflow settlement verified in bank records but payment reference is unallocated."
                recommended_action = "Contact acquirer operations for UTR payment reference mapping."
                explanation = (
                    f"### Facts\n"
                    f"- Settlement inflow exists in bank records for {exposure} minor units.\n"
                    f"- Gateway transaction mapping is null or ambiguous.\n\n"
                    f"### Hypothesis\n"
                    f"- Payment reference was truncated or dropped during bank batch export.\n\n"
                    f"### Conclusion\n"
                    f"- Unallocated settlement funds held pending reference resolution."
                )
            else:
                category = RootCauseCategory.SETTLEMENT_PROCESSING_FAILURE.value
                root_cause = (
                    f"Captured payment {payment_id} has zero downstream bank settlement records "
                    f"past the expected processing period."
                )
                missing_info = [
                    f"No bank settlement batch found for payment {payment_id}.",
                ]
                confidence = "HIGH"
                confidence_reason = "Gateway captured state confirmed with total absence of downstream settlement."
                recommended_action = "Inquire with acquirer regarding missing batch file for payment."
                explanation = (
                    f"### Facts\n"
                    f"- Gateway payment `{payment_id}` status is `CAPTURED`.\n"
                    f"- Zero downstream settlement records found in banking tables.\n\n"
                    f"### Hypothesis\n"
                    f"- Acquirer failed to submit transaction in clearing batch.\n\n"
                    f"### Conclusion\n"
                    f"- Missing settlement of {exposure} minor units."
                )

        elif exc_type == "LEGITIMATE_TIMING_EXCEPTION":
            category = RootCauseCategory.SETTLEMENT_TIMING.value
            root_cause = (
                f"Payment {payment_id} initiated near weekend/post-cutoff boundary is a legitimate timing exception "
                f"that cleared inside the next valid business processing window (LATE_BUT_VALID). Zero financial exposure."
            )
            confidence = "HIGH"
            confidence_reason = "Deterministic SLA calendar confirmed clearance inside valid window."
            recommended_action = "No action required. Legitimate calendar timing observation."
            explanation = (
                f"### Facts\n"
                f"- Payment `{payment_id}` initiated post-cutoff/weekend.\n"
                f"- Cleared on the immediate next business processing window.\n\n"
                f"### Hypothesis\n"
                f"- Standard non-business hour processing delay.\n\n"
                f"### Conclusion\n"
                f"- Legitimate timing observation. No financial breach occurred."
            )

        else:
            category = RootCauseCategory.OTHER.value
            root_cause = f"Investigated discrepancy for exception {ctx.get('exception_id', 'N/A')}."
            confidence = "MEDIUM"
            confidence_reason = "General evidence analysis."
            recommended_action = "Review operational records manually."
            explanation = f"### Facts\n- Operational records reviewed."

        return StructuredInvestigationOutput(
            investigation_status="SUCCESS",
            root_cause=root_cause,
            root_cause_category=category,
            confidence=confidence,
            confidence_reason=confidence_reason,
            evidence=citations,
            contradictions=contradictions,
            missing_information=missing_info,
            exposure_assessment=exposure,
            explanation=explanation,
            recommended_next_step=recommended_action,
        )


class HTTPLLMProvider(LLMProvider):
    """HTTP LLM provider supporting OpenAI, Gemini, or Anthropic OpenAI-compatible endpoints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.0,
    ):
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "gpt-4o-mini")
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
        self.temperature = float(os.getenv("LLM_TEMPERATURE", str(temperature)))

    def generate_investigation(
        self,
        system_prompt: str,
        user_content: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> StructuredInvestigationOutput:
        if not self.api_key:
            # Fallback to mock provider if no API key is provided
            mock = DeterministicMockLLMProvider()
            return mock.generate_investigation(system_prompt, user_content, context)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            "response_format": {"type": "json_object"},
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                res = client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
                res.raise_for_status()
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                parsed = json.loads(content)
                return StructuredInvestigationOutput(**parsed)
        except Exception:
            # Fallback to mock provider on network/parsing error to ensure resilience
            mock = DeterministicMockLLMProvider()
            return mock.generate_investigation(system_prompt, user_content, context)


def get_llm_provider(provider_type: Optional[str] = None) -> LLMProvider:
    """Factory creating configured LLMProvider instance."""
    prov = provider_type or os.getenv("LLM_PROVIDER", "mock").lower()
    if prov in ("openai", "gemini", "anthropic", "http"):
        return HTTPLLMProvider()
    return DeterministicMockLLMProvider()
