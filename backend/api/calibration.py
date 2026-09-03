"""Confidence calibration API router for Nodal Sentinel."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.calibration.service import ConfidenceCalibrationService

router = APIRouter(prefix="/calibration", tags=["Confidence Calibration"])
service = ConfidenceCalibrationService()


class ConfidenceBucketResponse(BaseModel):
    confidence_level: str
    prediction_count: int
    evaluated_count: int
    unevaluated_count: int
    correct_count: int
    correctness_rate: Optional[float] = None
    coverage: Optional[float] = None


class ReliabilityBinResponse(BaseModel):
    range: str
    count: int
    accuracy: Optional[float] = None
    confidence: Optional[float] = None
    calibration_error: Optional[float] = None


class NumericalMetricsResponse(BaseModel):
    status: str
    eligible_sample_size: int
    brier_score: Optional[float] = None
    ece: Optional[float] = None
    reliability_bins: List[ReliabilityBinResponse] = []
    reason: Optional[str] = None


class SourceBreakdownResponse(BaseModel):
    seeded_count: int
    live_injected_count: int
    total: int


class ConfidenceCalibrationResponse(BaseModel):
    snapshot_id: str
    status: str
    methodology_version: str
    prediction_type_filter: Optional[str] = None
    source_filter: Optional[str] = None
    total_predictions: int
    evaluated_predictions: int
    unevaluated_predictions: int
    correct_predictions: int
    coverage: Optional[float] = None
    correctness_rate: Optional[float] = None
    confidence_buckets: Dict[str, ConfidenceBucketResponse]
    numerical_metrics: NumericalMetricsResponse
    source_breakdown: SourceBreakdownResponse
    insufficiency_reasons: Optional[List[str]] = None
    disclaimer: str
    generated_at: str


@router.get("/confidence", response_model=ConfidenceCalibrationResponse, summary="Get Confidence Calibration")
def get_confidence_calibration(
    prediction_type: Optional[str] = Query(default=None, description="Filter by prediction type: INVESTIGATION, VERIFIER, DRIFT"),
    source: Optional[str] = Query(default=None, description="Filter by source: all, seeded, live-injected"),
    db: Session = Depends(get_db),
    x_request_id: Optional[str] = Header(None),
    x_actor_id: Optional[str] = Header("operator"),
) -> ConfidenceCalibrationResponse:
    """Retrieves empirical confidence calibration and reliability metrics across historical predictions.

    Calls PRD endpoint: GET /calibration/confidence
    Guarantees:
    - 100% deterministic evidence-based evaluation from persisted historical outcomes.
    - Zero fabricated probabilities, Brier scores, or outcomes.
    - Explicit INSUFFICIENT_DATA status when evaluated outcomes are sparse.
    - Strict benchmark isolation: seeded vs live-injected cases partitioned.
    """
    result = service.evaluate_calibration(
        session=db,
        prediction_type=prediction_type,
        source=source,
        persist=True,
        log_audit=True,
        actor_id=x_actor_id or "operator",
        request_id=x_request_id,
    )
    return ConfidenceCalibrationResponse(**result)
