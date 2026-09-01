"""Pydantic schemas and structured representations for Risk Policy Gating."""
from typing import List, Optional
from pydantic import BaseModel, Field


class PolicyCheckRequest(BaseModel):
    requested_action: str = Field(..., description="Allowlisted policy action: e.g. REFUND, RECONCILE, INVESTIGATE, NO_ACTION")
    simulation: bool = Field(default=False, description="Whether to simulate policy evaluation without persisting a new decision record")


class PolicyDecisionResponse(BaseModel):
    decision_id: str
    exception_id: str
    requested_action: str
    decision: str  # ALLOW, ALLOW_WITH_CONDITIONS, REQUIRE_APPROVAL, REQUIRE_ESCALATION, BLOCK, INSUFFICIENT_EVIDENCE
    policy_version: str
    allowed_actions: List[str]
    prohibited_actions: List[str]
    approval_required: bool
    approval_role: Optional[str] = None
    approval_reason: Optional[str] = None
    escalation_required: bool
    escalation_level: Optional[str] = None
    escalation_reason: Optional[str] = None
    evidence_requirements: List[str]
    rules_evaluated: List[str]
    violated_rules: List[str]
    rationale: str
    risk_score: int
    priority: str
    materiality: str
    exposure: int
    evaluated_at: str


class PolicyConfigResponse(BaseModel):
    policy_version: str
    allowlisted_actions: List[str]
    financial_mutation_actions: List[str]
    p1_requires_approval: bool
    p1_requires_escalation: bool
    min_investigation_confidence: float
    remediation_capability_active: bool
