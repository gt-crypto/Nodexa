"""Pydantic schemas and typed structures for Post-Remediation Verification."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class VerificationEvidenceItem(BaseModel):
    """Structured, reproducible evidence item for an individual verification check."""
    check_id: str
    check_type: str
    source_table: str
    source_record_id: Optional[str] = None
    expected_value: Any = None
    actual_value: Any = None
    result: str = Field(..., description="PASS or FAIL")
    explanation: str


class VerificationRecordResponse(BaseModel):
    """Authoritative API response schema for a completed or ongoing verification."""
    verification_id: str
    remediation_id: str
    exception_id: str
    verification_status: str
    verification_result: Optional[str] = None
    original_exposure: int
    remaining_exposure: int
    exposure_reduction: int
    exposure_reduction_bps: int
    expected_state: Optional[Dict[str, Any]] = None
    actual_state: Optional[Dict[str, Any]] = None
    invariant_status: str
    reconciliation_status: str
    checks_passed: List[str] = Field(default_factory=list)
    checks_failed: List[str] = Field(default_factory=list)
    failure_reasons: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    verified_by: str
    verification_mode: str
    verification_version: str
    attempt_number: int
    escalation_required: bool
    final_exception_state: Optional[str] = None
    created_at: str
    completed_at: Optional[str] = None


class VerificationDryRunResponse(BaseModel):
    """Read-only dry run simulation response for verification without mutating DB."""
    remediation_id: str
    exception_id: str
    projected_status: str
    original_exposure: int
    projected_remaining_exposure: int
    projected_reduction_bps: int
    checks_passed: List[str] = Field(default_factory=list)
    checks_failed: List[str] = Field(default_factory=list)
    failure_reasons: List[str] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    eligible_for_closure: bool
    escalation_required: bool


class VerificationRetryRequest(BaseModel):
    """Request payload for retrying a failed verification."""
    reason: str = Field(default="Operator initiated retry", description="Reason for requesting verification retry")
    requested_by: str = Field(default="system-operator", description="Actor requesting the retry")
