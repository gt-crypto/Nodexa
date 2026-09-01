"""FastAPI REST endpoints for Financial Exposure, Materiality & Risk Prioritization."""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.database import get_db
from backend.models.exceptions import ExceptionRecord
from backend.exposure.models import (
    RiskAssessmentResponse,
    RiskQueueItemResponse,
    AccountRiskSummaryResponse,
)
from backend.exposure.service import RiskAssessmentService
from backend.exposure.prioritization import get_prioritized_risk_queue, get_account_risk_summary

router = APIRouter(tags=["Financial Risk & Exposure"])


class AssessRiskRequest(BaseModel):
    force_recalculate: bool = False


@router.post("/exceptions/{exception_id}/assess-risk", response_model=RiskAssessmentResponse)
def post_assess_exception_risk(
    exception_id: str,
    req: AssessRiskRequest = AssessRiskRequest(),
    db: Session = Depends(get_db),
) -> RiskAssessmentResponse:
    """Calculates, scores, and persists deterministic financial risk and materiality assessment."""
    exc = db.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)).first()
    if not exc:
        raise HTTPException(status_code=404, detail=f"Exception '{exception_id}' not found.")

    service = RiskAssessmentService()
    assessment = service.assess_exception_risk(
        session=db,
        exception_id=exception_id,
        force_recalculate=req.force_recalculate,
    )
    db.commit()

    return RiskAssessmentResponse(
        assessment_id=assessment.assessment_id,
        exception_id=assessment.exception_id,
        deterministic_exposure=assessment.deterministic_exposure,
        currency=assessment.currency,
        exposure_type=assessment.exposure_type,
        gross_exposure=assessment.gross_exposure,
        recoverable_amount=assessment.recoverable_amount,
        net_exposure=assessment.net_exposure,
        materiality=assessment.materiality,
        risk_score=assessment.risk_score,
        score_breakdown=json.loads(assessment.score_breakdown or "{}"),
        risk_factors=json.loads(assessment.risk_factors or "{}"),
        priority=assessment.priority,
        escalation=assessment.escalation,
        explanation=assessment.explanation,
        policy_version=assessment.policy_version,
        scoring_version=assessment.scoring_version,
        threshold_version=assessment.threshold_version,
        calculated_at=assessment.calculated_at.isoformat() if assessment.calculated_at else "",
        created_at=assessment.created_at.isoformat() if assessment.created_at else "",
    )


@router.get("/exceptions/{exception_id}/risk", response_model=RiskAssessmentResponse)
def get_exception_risk(
    exception_id: str,
    db: Session = Depends(get_db),
) -> RiskAssessmentResponse:
    """Retrieves latest risk assessment for an exception."""
    exc = db.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)).first()
    if not exc:
        raise HTTPException(status_code=404, detail=f"Exception '{exception_id}' not found.")

    service = RiskAssessmentService()
    assessment = service.get_latest_risk_assessment(session=db, exception_id=exception_id)
    if not assessment:
        # Automatically compute if missing
        assessment = service.assess_exception_risk(session=db, exception_id=exception_id)
        db.commit()

    return RiskAssessmentResponse(
        assessment_id=assessment.assessment_id,
        exception_id=assessment.exception_id,
        deterministic_exposure=assessment.deterministic_exposure,
        currency=assessment.currency,
        exposure_type=assessment.exposure_type,
        gross_exposure=assessment.gross_exposure,
        recoverable_amount=assessment.recoverable_amount,
        net_exposure=assessment.net_exposure,
        materiality=assessment.materiality,
        risk_score=assessment.risk_score,
        score_breakdown=json.loads(assessment.score_breakdown or "{}"),
        risk_factors=json.loads(assessment.risk_factors or "{}"),
        priority=assessment.priority,
        escalation=assessment.escalation,
        explanation=assessment.explanation,
        policy_version=assessment.policy_version,
        scoring_version=assessment.scoring_version,
        threshold_version=assessment.threshold_version,
        calculated_at=assessment.calculated_at.isoformat() if assessment.calculated_at else "",
        created_at=assessment.created_at.isoformat() if assessment.created_at else "",
    )


@router.get("/risk/queue", response_model=List[RiskQueueItemResponse])
def get_risk_queue(
    priority: Optional[str] = Query(None, description="Filter by priority: P1, P2, P3, P4"),
    severity: Optional[str] = Query(None, description="Filter by severity: LOW, MEDIUM, HIGH, CRITICAL"),
    materiality: Optional[str] = Query(None, description="Filter by materiality: NONE, LOW, MEDIUM, HIGH, MATERIAL, SEVERE"),
    exception_type: Optional[str] = Query(None, description="Filter by exception taxonomy"),
    min_exposure: Optional[int] = Query(None, description="Minimum exposure in minor integer units"),
    max_exposure: Optional[int] = Query(None, description="Maximum exposure in minor integer units"),
    escalation: Optional[str] = Query(None, description="Filter by escalation recommendation"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[RiskQueueItemResponse]:
    """Retrieves prioritized exception risk queue with deterministic multi-level tie-breaking."""
    # Ensure open exceptions have assessments
    service = RiskAssessmentService()
    service.assess_all_open_exceptions(session=db)
    db.commit()

    items, _ = get_prioritized_risk_queue(
        session=db,
        priority=priority,
        severity=severity,
        materiality=materiality,
        exception_type=exception_type,
        min_exposure=min_exposure,
        max_exposure=max_exposure,
        escalation=escalation,
        limit=limit,
        offset=offset,
    )
    return items


@router.get("/risk/account", response_model=AccountRiskSummaryResponse)
def get_account_risk(
    account_id: str = Query("nodal_escrow_main", description="Nodal account identifier"),
    db: Session = Depends(get_db),
) -> AccountRiskSummaryResponse:
    """Aggregates account-level financial risk exposure, concentration, and priority counts."""
    # Ensure open exceptions have assessments
    service = RiskAssessmentService()
    service.assess_all_open_exceptions(session=db)
    db.commit()

    return get_account_risk_summary(session=db, account_id=account_id)
