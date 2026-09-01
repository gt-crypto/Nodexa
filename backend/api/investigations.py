"""FastAPI REST endpoints for AI Investigation and Root-Cause Analysis."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.database import get_db
from backend.models.exceptions import ExceptionRecord
from backend.models.investigation import InvestigationRun
from backend.agent.service import InvestigationService

router = APIRouter(tags=["AI Investigation"])


class InvestigateRequest(BaseModel):
    reinvestigate: bool = Field(default=False, description="Whether to allow re-investigating an already diagnosed exception")


class InvestigationRunResponse(BaseModel):
    investigation_id: str
    exception_id: str
    status: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    agent_version: Optional[str] = None
    final_classification: Optional[str] = None
    root_cause: Optional[str] = None
    confidence: Optional[float] = None
    recommended_action: Optional[str] = None
    human_approval_required: bool = False
    error_info: Optional[str] = None
    created_at: str


class InvestigationExecutionResponse(BaseModel):
    status: str = "success"
    investigation_id: str
    exception_id: str
    current_stage: str
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    structured_output: Optional[Dict[str, Any]] = None


@router.post("/exceptions/{exception_id}/investigate", response_model=InvestigationExecutionResponse)
def post_investigate_exception(
    exception_id: str,
    req: InvestigateRequest = InvestigateRequest(),
    db: Session = Depends(get_db),
) -> InvestigationExecutionResponse:
    """Triggers AI investigation and root-cause analysis on an exception."""
    exc = db.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)).first()
    if not exc:
        raise HTTPException(status_code=404, detail=f"Exception '{exception_id}' not found.")

    service = InvestigationService()
    result = service.investigate_exception(
        session=db,
        exception_id=exception_id,
        reinvestigate=req.reinvestigate,
    )

    if result.get("status") == "FAILED":
        return InvestigationExecutionResponse(
            status="failed",
            investigation_id=result.get("investigation_id"),
            exception_id=exception_id,
            current_stage=result.get("current_stage", "FAILED"),
            error_message=result.get("error_message"),
            started_at=result.get("started_at"),
            completed_at=result.get("completed_at"),
            structured_output=None,
        )

    return InvestigationExecutionResponse(
        status="success",
        investigation_id=result.get("investigation_id"),
        exception_id=exception_id,
        current_stage=result.get("current_stage"),
        error_message=None,
        started_at=result.get("started_at"),
        completed_at=result.get("completed_at"),
        structured_output=result.get("structured_output"),
    )


@router.get("/exceptions/{exception_id}/investigations", response_model=List[InvestigationRunResponse])
def get_exception_investigations(
    exception_id: str,
    db: Session = Depends(get_db),
) -> List[InvestigationRunResponse]:
    """Retrieves all past investigation runs executed for a given exception."""
    exc = db.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)).first()
    if not exc:
        raise HTTPException(status_code=404, detail=f"Exception '{exception_id}' not found.")

    service = InvestigationService()
    runs = service.list_investigations_for_exception(session=db, exception_id=exception_id)

    return [
        InvestigationRunResponse(
            investigation_id=r.investigation_id,
            exception_id=r.exception_id,
            status=r.status,
            started_at=r.started_at.isoformat() if r.started_at else None,
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
            agent_version=r.agent_version,
            final_classification=r.final_classification,
            root_cause=r.root_cause,
            confidence=float(r.confidence) if r.confidence else None,
            recommended_action=r.recommended_action,
            human_approval_required=r.human_approval_required,
            error_info=r.error_info,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in runs
    ]


@router.get("/investigations/{investigation_id}", response_model=InvestigationRunResponse)
def get_investigation_run_detail(
    investigation_id: str,
    db: Session = Depends(get_db),
) -> InvestigationRunResponse:
    """Retrieves full details of a specific investigation run."""
    service = InvestigationService()
    run = service.get_investigation(session=db, investigation_id=investigation_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Investigation run '{investigation_id}' not found.")

    return InvestigationRunResponse(
        investigation_id=run.investigation_id,
        exception_id=run.exception_id,
        status=run.status,
        started_at=run.started_at.isoformat() if run.started_at else None,
        completed_at=run.completed_at.isoformat() if run.completed_at else None,
        agent_version=run.agent_version,
        final_classification=run.final_classification,
        root_cause=run.root_cause,
        confidence=float(run.confidence) if run.confidence else None,
        recommended_action=run.recommended_action,
        human_approval_required=run.human_approval_required,
        error_info=run.error_info,
        created_at=run.created_at.isoformat() if run.created_at else "",
    )
