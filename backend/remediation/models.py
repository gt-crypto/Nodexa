"""Pydantic schemas and typed parameter structures for Remediation Workflow."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class RefundParameters(BaseModel):
    payment_id: str
    amount_minor_units: int = Field(gt=0, description="Amount in minor units (paise/cents)")
    currency: str = "INR"
    reason: str


class ReverseRefundParameters(BaseModel):
    payment_id: str
    refund_event_id: Optional[str] = None
    amount_minor_units: int = Field(gt=0, description="Amount in minor units (paise/cents)")
    currency: str = "INR"
    reason: str


class AllocateSettlementParameters(BaseModel):
    settlement_id: str
    payment_id: Optional[str] = None
    amount_minor_units: int = Field(gt=0, description="Amount in minor units (paise/cents)")
    reason: str


class ReconcileParameters(BaseModel):
    payment_id: Optional[str] = None
    reconciliation_reference: Optional[str] = None
    reason: str


class EscalateParameters(BaseModel):
    escalation_level: str
    reason: str


class ResolveExceptionParameters(BaseModel):
    resolution_reason: str


class RemediationPlanCreateRequest(BaseModel):
    action: str = Field(..., description="Allowlisted remediation action: REFUND, REVERSE_REFUND, ALLOCATE_SETTLEMENT, RECONCILE, ESCALATE, RESOLVE_EXCEPTION")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Typed parameters matching the action schema")
    requested_by: str = Field(default="system-operator", description="Identifier of the requesting user or service")


class RemediationApprovalRequest(BaseModel):
    approved_by: str = Field(..., description="Identifier of the reviewing human authority")
    decision: str = Field(..., description="APPROVED or REJECTED")
    reason: str = Field(..., description="Reasoning for approval or rejection decision")


class RemediationApprovalResponse(BaseModel):
    approval_id: str
    action_id: str
    required_role: str
    approved_by: str
    decision: str
    reason: str
    timestamp: str
    policy_version: str
    expires_at: Optional[str] = None


class RemediationPlanResponse(BaseModel):
    remediation_id: str
    exception_id: str
    action: str
    parameters: Dict[str, Any]
    policy_decision_id: Optional[str] = None
    risk_assessment_id: Optional[str] = None
    investigation_id: Optional[str] = None
    deterministic_exposure: int
    requested_by: Optional[str] = None
    approved_by: Optional[str] = None
    status: str
    approval_required: bool
    approval_role: Optional[str] = None
    verification_required: bool
    before_snapshot: Optional[Dict[str, Any]] = None
    after_snapshot: Optional[Dict[str, Any]] = None
    result_summary: Optional[str] = None
    error_reason: Optional[str] = None
    policy_version: str
    remediation_version: str
    requested_at: str
    approved_at: Optional[str] = None
    executed_at: Optional[str] = None
    created_at: str
    updated_at: str


class RemediationExecutionResponse(BaseModel):
    remediation_id: str
    exception_id: str
    action: str
    status: str
    result_summary: Optional[str] = None
    before_snapshot: Optional[Dict[str, Any]] = None
    after_snapshot: Optional[Dict[str, Any]] = None
    verification_required: bool
    executed_at: str


class RemediationDryRunResponse(BaseModel):
    remediation_id: str
    exception_id: str
    action: str
    eligible: bool
    validation_errors: List[str]
    projected_before_state: Dict[str, Any]
    projected_after_state: Dict[str, Any]
    approval_status: str
