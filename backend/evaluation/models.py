"""Pydantic schemas and serialization models for the Evaluation layer."""
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from datetime import datetime


class EvaluationRunRequest(BaseModel):
    dataset_id: str = Field(..., description="ID of the dataset to evaluate against ground truth")
    force_rerun: bool = Field(False, description="If True, bypasses cache and creates a fresh evaluation run")
    actor_type: str = Field("SYSTEM", description="Actor type triggering evaluation")
    actor_id: str = Field("evaluator-v1", description="Identifier of the evaluator")


class EvaluationMetricDetail(BaseModel):
    name: str
    expected_count: int
    predicted_count: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    precision_bps: int
    recall: float
    recall_bps: int
    f1_score: float
    f1_score_bps: int


class ExposureAccuracySummary(BaseModel):
    exact_matches: int
    total_evaluated: int
    exact_match_rate: float
    exact_match_rate_bps: int
    total_expected_exposure: int
    total_predicted_exposure: int
    total_absolute_error: int
    max_absolute_error: int
    mean_absolute_error: float
    zero_exposure_cases_verified: int


class ConfusionMatrixItem(BaseModel):
    expected_class: str
    predicted_class: str
    count: int


class CaseScoreBreakdown(BaseModel):
    detection_score: int
    root_cause_score: int
    exposure_score: int
    severity_score: int
    priority_score: int
    policy_score: int
    remediation_score: int
    verification_score: int
    total_score: int


class EvaluationCaseResponse(BaseModel):
    evaluation_case_id: str
    evaluation_run_id: str
    ground_truth_case_id: Optional[str] = None
    predicted_exception_id: Optional[str] = None
    match_status: str
    matched_by: Optional[str] = None
    matched_identifier: Optional[str] = None
    expected_exception_type: Optional[str] = None
    predicted_exception_type: Optional[str] = None
    expected_root_cause: Optional[str] = None
    predicted_root_cause: Optional[str] = None
    expected_exposure: int
    predicted_exposure: int
    exposure_error: int
    expected_severity: Optional[str] = None
    predicted_severity: Optional[str] = None
    expected_priority: Optional[str] = None
    predicted_priority: Optional[str] = None
    expected_resolution_class: Optional[str] = None
    predicted_resolution_class: Optional[str] = None
    expected_policy_decision: Optional[str] = None
    predicted_policy_decision: Optional[str] = None
    remediation_result: Optional[str] = None
    verification_result: Optional[str] = None
    is_false_closure: bool
    is_legitimate_case: bool
    error_categories: List[str] = []
    details: Dict[str, Any] = {}
    created_at: datetime


class ComponentScores(BaseModel):
    detection: int
    investigation: int
    financial: int
    risk: int
    policy: int
    remediation: int
    verification: int
    safety: int
    overall: int


class EvaluationRunResponse(BaseModel):
    evaluation_run_id: str
    dataset_id: str
    benchmark_version: str
    system_version: str
    status: str
    total_ground_truth_cases: int
    total_predictions: int
    true_positives: int
    false_positives: int
    false_negatives: int
    precision: float
    precision_bps: int
    recall: float
    recall_bps: int
    f1_score: float
    f1_score_bps: int
    overall_score: int
    scores: ComponentScores
    safety_status: str
    critical_safety_failure: bool
    safety_failure_reasons: List[str] = []
    started_at: datetime
    completed_at: Optional[datetime] = None
    created_at: datetime


class EvaluationReportSummary(BaseModel):
    run: EvaluationRunResponse
    detection_by_type: Dict[str, EvaluationMetricDetail]
    exposure_accuracy: ExposureAccuracySummary
    confusion_matrices: Dict[str, List[ConfusionMatrixItem]]
    legitimate_cases_summary: Dict[str, Any]
    normal_cases_summary: Dict[str, Any]
    false_positives: List[EvaluationCaseResponse]
    false_negatives: List[EvaluationCaseResponse]
    misclassifications: List[EvaluationCaseResponse]
    critical_safety_violations: List[str]
