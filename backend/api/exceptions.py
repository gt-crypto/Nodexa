"""FastAPI REST endpoints for Exception Detection and Exception Management."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.database import get_db
from backend.models.exceptions import ExceptionRecord, ExceptionAffectedRecord, ExceptionStateTransition
from backend.models.audit import AuditEvent
from backend.services.repositories.exception_repository import ExceptionRepository
from backend.services.repositories.audit_repository import AuditRepository
from backend.exceptions.service import ExceptionDetectionService

router = APIRouter(prefix="/exceptions", tags=["Exceptions"])


class DetectExceptionsRequest(BaseModel):
    dataset_id: Optional[str] = Field(default=None, description="Optional dataset ID identifier")
    account_id: str = Field(default="nodal_escrow_main", description="Nodal account identifier")


class ExceptionSummaryResponse(BaseModel):
    exception_id: str
    exception_type: str
    severity: str
    state: str
    exposure: int
    confidence: float
    source_flag: str = "seeded"
    description: Optional[str]
    primary_payment_id: Optional[str]
    primary_order_id: Optional[str]
    detected_at: str
    created_at: str
    updated_at: str


class DetectionReportResponse(BaseModel):
    status: str = "success"
    dataset_id: Optional[str]
    evaluated_at: str
    controls_run_count: int
    findings_count: int
    total_detected_count: int
    new_exception_count: int
    existing_exception_count: int
    legitimate_case_count: int
    total_exposure: int
    severity_breakdown: Dict[str, int]
    exception_type_breakdown: Dict[str, int]
    exceptions: List[Dict[str, Any]]


class AffectedRecordResponse(BaseModel):
    record_type: str
    record_identifier: str
    metadata_json: Optional[str] = None


class StateTransitionResponse(BaseModel):
    transition_id: str
    from_state: str
    to_state: str
    timestamp: str
    reason: Optional[str]
    actor_type: str
    actor_id: Optional[str]


class AuditEventResponse(BaseModel):
    audit_event_id: str
    event_type: str
    timestamp: str
    actor_type: str
    actor_id: Optional[str]
    event_summary: str


class ExceptionDetailResponse(BaseModel):
    exception_id: str
    exception_type: str
    severity: str
    state: str
    exposure: int
    confidence: float
    source_flag: str = "seeded"
    description: Optional[str]
    primary_payment_id: Optional[str]
    primary_order_id: Optional[str]
    detected_at: str
    created_at: str
    updated_at: str
    affected_records: List[AffectedRecordResponse]
    transitions: List[StateTransitionResponse]
    audit_events: List[AuditEventResponse]


@router.post("/detect", response_model=DetectionReportResponse)
def post_detect_exceptions(
    req: DetectExceptionsRequest = DetectExceptionsRequest(),
    db: Session = Depends(get_db),
) -> DetectionReportResponse:
    """Runs deterministic exception detection and persists newly discovered exceptions."""
    service = ExceptionDetectionService()
    report = service.detect_exceptions(
        session=db,
        account_id=req.account_id,
        dataset_id=req.dataset_id,
    )
    db.commit()
    return DetectionReportResponse(
        status="success",
        dataset_id=report.dataset_id,
        evaluated_at=report.evaluated_at.isoformat(),
        controls_run_count=report.controls_run_count,
        findings_count=report.findings_count,
        total_detected_count=report.total_detected_count,
        new_exception_count=report.new_exception_count,
        existing_exception_count=report.existing_exception_count,
        legitimate_case_count=report.legitimate_case_count,
        total_exposure=report.total_exposure,
        severity_breakdown=report.severity_breakdown,
        exception_type_breakdown=report.exception_type_breakdown,
        exceptions=report.exceptions,
    )


@router.get("", response_model=List[ExceptionSummaryResponse])
def get_exceptions(
    state: Optional[str] = Query(default=None, description="Filter by lifecycle state (e.g. DETECTED)"),
    exception_type: Optional[str] = Query(default=None, description="Filter by exception type"),
    severity: Optional[str] = Query(default=None, description="Filter by severity (LOW, MEDIUM, HIGH, CRITICAL)"),
    min_exposure: Optional[int] = Query(default=None, description="Filter by minimum exposure minor units"),
    source_flag: Optional[str] = Query(default=None, description="Filter by source flag (seeded, live-injected)"),
    dataset_id: Optional[str] = Query(default=None, description="Filter by dataset ID"),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> List[ExceptionSummaryResponse]:
    """Lists persisted exception records with optional filtering."""
    if dataset_id:
        from backend.models.dataset import DatasetMetadata
        ds = db.scalars(select(DatasetMetadata).where(DatasetMetadata.dataset_id == dataset_id)).first()
        if not ds:
            return []

    stmt = select(ExceptionRecord)
    if state:
        stmt = stmt.where(ExceptionRecord.state == state)
    if exception_type:
        stmt = stmt.where(ExceptionRecord.exception_type == exception_type)
    if severity:
        stmt = stmt.where(ExceptionRecord.severity == severity)
    if min_exposure is not None:
        stmt = stmt.where(ExceptionRecord.exposure >= min_exposure)
    if source_flag:
        stmt = stmt.where(ExceptionRecord.source_flag == source_flag)

    stmt = stmt.order_by(ExceptionRecord.detected_at.desc()).limit(limit).offset(offset)
    records = list(db.scalars(stmt).all())

    return [
        ExceptionSummaryResponse(
            exception_id=r.exception_id,
            exception_type=r.exception_type,
            severity=r.severity,
            state=r.state,
            exposure=r.exposure,
            confidence=float(r.confidence),
            source_flag=r.source_flag or "seeded",
            description=r.description,
            primary_payment_id=r.primary_payment_id,
            primary_order_id=r.primary_order_id,
            detected_at=r.detected_at.isoformat() if r.detected_at else "",
            created_at=r.created_at.isoformat() if r.created_at else "",
            updated_at=r.updated_at.isoformat() if r.updated_at else "",
        )
        for r in records
    ]


@router.get("/{exception_id}", response_model=ExceptionDetailResponse)
def get_exception_detail(
    exception_id: str,
    db: Session = Depends(get_db),
) -> ExceptionDetailResponse:
    """Retrieves full details for a single exception including affected records, state transitions, and audit logs."""
    repo = ExceptionRepository(db)
    exc = repo.get_exception(exception_id)
    if not exc:
        raise HTTPException(status_code=404, detail=f"Exception '{exception_id}' not found.")

    aff_records = repo.get_affected_records(exception_id)
    transitions = repo.get_state_transitions(exception_id)
    
    audit_repo = AuditRepository(db)
    audit_events = audit_repo.list_events_for_exception(exception_id)

    return ExceptionDetailResponse(
        exception_id=exc.exception_id,
        exception_type=exc.exception_type,
        severity=exc.severity,
        state=exc.state,
        exposure=exc.exposure,
        confidence=float(exc.confidence),
        source_flag=exc.source_flag or "seeded",
        description=exc.description,
        primary_payment_id=exc.primary_payment_id,
        primary_order_id=exc.primary_order_id,
        detected_at=exc.detected_at.isoformat() if exc.detected_at else "",
        created_at=exc.created_at.isoformat() if exc.created_at else "",
        updated_at=exc.updated_at.isoformat() if exc.updated_at else "",
        affected_records=[
            AffectedRecordResponse(
                record_type=a.record_type,
                record_identifier=a.record_identifier,
                metadata_json=a.metadata_json,
            )
            for a in aff_records
        ],
        transitions=[
            StateTransitionResponse(
                transition_id=t.transition_id,
                from_state=t.from_state,
                to_state=t.to_state,
                timestamp=t.timestamp.isoformat() if t.timestamp else "",
                reason=t.reason,
                actor_type=t.actor_type,
                actor_id=t.actor_id,
            )
            for t in transitions
        ],
        audit_events=[
            AuditEventResponse(
                audit_event_id=ae.audit_event_id,
                event_type=ae.event_type,
                timestamp=ae.timestamp.isoformat() if ae.timestamp else "",
                actor_type=ae.actor_type,
                actor_id=ae.actor_id,
                event_summary=ae.event_summary,
            )
            for ae in audit_events
        ],
    )


@router.get("/{exception_id}/lineage")
def get_exception_lineage(
    exception_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Reconstructs the complete entity provenance and lifecycle trace for an exception."""
    from backend.services.lineage_service import EntityLineageService
    try:
        return EntityLineageService.get_exception_lineage(session=db, exception_id=exception_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/diagnostics/integrity")
def run_database_integrity_diagnostics(
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Executes read-only relational and financial integrity diagnostic checks."""
    from backend.services.integrity_service import DatabaseIntegrityDiagnosticService
    return DatabaseIntegrityDiagnosticService.run_integrity_diagnostics(session=db)
