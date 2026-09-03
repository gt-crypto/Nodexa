"""Predictive Nodal Drift Radar API endpoints."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.predictions.drift_service import PredictiveDriftService

router = APIRouter(prefix="/predictions", tags=["Predictive Drift Radar"])
service = PredictiveDriftService()


class ObservationWindowResponse(BaseModel):
    baseline_start: Optional[str] = None
    baseline_end: Optional[str] = None
    current_start: Optional[str] = None
    current_end: Optional[str] = None


class SignalContributionResponse(BaseModel):
    signal: str
    name: str
    baseline: Any
    current: Any
    delta: Any
    direction: str
    contribution: int
    explanation: str
    evidence_ids: List[str] = []
    growth_rate: Optional[float] = None


class SourceMetadataResponse(BaseModel):
    seeded_count: int
    live_injected_count: int
    total_observations: int
    synthetic_included: bool


class DriftPredictionResponse(BaseModel):
    prediction_id: str
    nodal_account_id: str
    prediction_timestamp: str
    observation_window: ObservationWindowResponse
    horizon: str
    drift_score: int
    risk_band: str
    direction: str
    confidence: str
    predicted_dimension: str
    signals: List[SignalContributionResponse]
    baseline_metrics: Dict[str, Any]
    current_metrics: Dict[str, Any]
    delta_metrics: Dict[str, Any]
    evidence_ids: List[str]
    source: SourceMetadataResponse
    methodology_version: str
    disclaimer: str


@router.get("/drift", response_model=DriftPredictionResponse, summary="Get Predictive Nodal Drift Radar")
def get_nodal_drift_prediction(
    nodal_account_id: str = Query(default="nodal_escrow_main", description="Nodal account identifier"),
    horizon: str = Query(default="NEXT_SETTLEMENT_CYCLE", description="Prediction horizon"),
    db: Session = Depends(get_db),
    x_request_id: Optional[str] = Header(None),
    x_actor_id: Optional[str] = Header("operator"),
) -> DriftPredictionResponse:
    """Retrieves deterministic leading early-warning operational drift signals for a nodal account.

    Calls PRD endpoint: GET /predictions/drift
    Guarantees:
    - 100% deterministic mathematical formulas without LLM calculation.
    - Zero synthetic future incidents fabricated.
    - Explicit INSUFFICIENT_DATA state if temporal observations are sparse.
    - Strictly analytical early-warning with zero automated policy mutations.
    """
    result = service.evaluate_drift(
        session=db,
        nodal_account_id=nodal_account_id,
        horizon=horizon,
        persist=True,
        log_audit=True,
        actor_id=x_actor_id or "operator",
        request_id=x_request_id,
    )
    return DriftPredictionResponse(**result)
