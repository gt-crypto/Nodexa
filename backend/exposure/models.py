"""Pydantic schemas and domain structures for Risk & Exposure engine."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.models.enums import (
    ExposureType,
    MaterialityLevel,
    PriorityLevel,
    EscalationRecommendation,
)


class RiskScoreBreakdown(BaseModel):
    financial_exposure_score: int
    severity_score: int
    control_failure_score: int
    confidence_score: int
    complexity_score: int
    sla_score: int
    ledger_risk_score: int
    allocation_risk_score: int
    total: int


class RiskFactors(BaseModel):
    exposure_amount: int
    severity_level: str
    control_failure_count: int
    investigation_confidence: Optional[str] = None
    affected_record_count: int
    sla_breached: bool
    ledger_contradiction: bool
    is_unallocated: bool
    is_double_dip: bool
    age_minutes: int


class RiskAssessmentResponse(BaseModel):
    assessment_id: str
    exception_id: str
    deterministic_exposure: int
    currency: str = "INR"
    exposure_type: str
    gross_exposure: int
    recoverable_amount: int
    net_exposure: int
    materiality: str
    risk_score: int
    score_breakdown: Dict[str, int]
    risk_factors: Dict[str, Any]
    priority: str
    escalation: str
    explanation: str
    policy_version: str
    scoring_version: str
    threshold_version: str
    calculated_at: str
    created_at: str


class RiskQueueItemResponse(BaseModel):
    exception_id: str
    exception_type: str
    severity: str
    exposure: int
    materiality: str
    risk_score: int
    priority: str
    escalation: str
    root_cause_category: Optional[str] = None
    investigation_confidence: Optional[float] = None
    detected_at: str


class TopExposureItem(BaseModel):
    exception_id: str
    exception_type: str
    exposure: int
    priority: str
    risk_score: int


class TopRiskItem(BaseModel):
    exception_id: str
    exception_type: str
    risk_score: int
    priority: str
    exposure: int


class AccountRiskSummaryResponse(BaseModel):
    account_id: str
    total_open_exposure: int
    total_material_exposure: int
    total_exceptions_count: int
    p1_count: int
    p2_count: int
    p3_count: int
    p4_count: int
    highest_risk_exception_id: Optional[str] = None
    highest_risk_score: int = 0
    top_exposure_exceptions: List[TopExposureItem]
    top_risk_exceptions: List[TopRiskItem]
    exposure_concentration_top3_bps: int  # Basis points (0-10000)
