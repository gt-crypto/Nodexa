"""Business Impact and ROI API routes."""
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.logging import logger
from backend.models.database import get_db
from backend.impact.roi_service import BusinessImpactService

router = APIRouter(prefix="/impact", tags=["Business Impact & ROI"])
service = BusinessImpactService()


class BusinessImpactResponse(BaseModel):
    financial_exposure_identified: int
    financial_exposure_currency: str
    actionable_case_count: int
    total_cases_detected: int
    high_risk_case_count: int
    recurring_pattern_count: int
    pattern_exposure_identified: int
    merchants_impacted: int
    seeded_case_count: int
    seeded_exposure_identified: int
    live_injected_case_count: int
    live_injected_exposure_identified: int
    automated_detection_rate: str
    value_type: str
    realized_savings: Optional[int] = None
    disclaimer: str
    methodology: Dict[str, str]
    version: str
    generated_at: str


@router.get("/roi", response_model=BusinessImpactResponse, summary="Get ROI / Business Impact Analytics")
def get_business_impact_roi(
    db: Session = Depends(get_db),
    x_request_id: Optional[str] = Header(None),
    x_actor_id: Optional[str] = Header("operator"),
) -> BusinessImpactResponse:
    """Retrieves deterministic Business Impact and ROI analytics from persisted records.

    Calls PRD endpoint: GET /impact/roi
    Guarantees:
    - Pure deterministic data without LLM hallucination.
    - Zero double-counting across exception joins or pattern miner clusters.
    - Explicit classification as POTENTIAL_EXPOSURE_SURFACED (not money saved).
    """
    try:
        result = service.calculate_impact(
            session=db,
            log_audit=True,
            actor_type="OPERATOR",
            actor_id=x_actor_id or "operator",
            request_id=x_request_id,
        )
        return BusinessImpactResponse(**result)
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        logger.error(
            operation="BUSINESS_IMPACT_ERROR",
            message=f"Failed to calculate business impact ROI: {e}",
            details={"traceback": tb},
        )
        raise HTTPException(
            status_code=500,
            detail=f"Business impact calculation error: {str(e)}",
        )
