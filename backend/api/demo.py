"""FastAPI REST & Streaming endpoints for Live Digital-Twin Synthetic Injection Console."""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.database import get_db, SessionLocal
from backend.models.injected_cases import InjectedCase
from backend.demo.injection_service import LiveDigitalTwinInjectionService

router = APIRouter(prefix="/demo", tags=["Live Digital Twin Console"])


class LiveInjectionRequest(BaseModel):
    exception_family: str = Field(
        ...,
        description="Supported anomaly family (e.g. GHOST_SETTLEMENT, REFUND_CHARGEBACK_DOUBLE_DIP, SETTLEMENT_SLA_BREACH)",
    )
    triggered_by: str = Field(
        default="demo-operator",
        description="Identifier of operator or judge triggering the live injection",
    )
    idempotency_key: Optional[str] = Field(
        default=None,
        description="Optional idempotency key to protect against duplicate submissions",
    )
    account_id: str = Field(
        default="nodal_escrow_main",
        description="Target nodal account identifier",
    )


class InjectedCaseSummaryResponse(BaseModel):
    injection_id: str
    exception_family: str
    triggered_by: str
    triggered_at: str
    source_flag: str
    linked_exception_id: Optional[str] = None
    status: str
    generated_identifiers: Optional[Dict[str, Any]] = None
    details: Optional[Dict[str, Any]] = None


class LiveInjectionResponse(BaseModel):
    injection_id: str
    exception_family: str
    source_flag: str = "live-injected"
    triggered_at: str
    generated_record_identifiers: Dict[str, Any]
    processing_status: str
    linked_exception_id: Optional[str] = None
    exception_state: Optional[str] = None
    exception_type: Optional[str] = None
    exposure: Optional[int] = None
    message: str
    stages: List[Dict[str, Any]] = []


class SupportedFamilyResponse(BaseModel):
    family: str
    description: str
    category: str
    severity: str
    is_legitimate: bool


@router.get("/supported-families", response_model=List[SupportedFamilyResponse])
def get_supported_families() -> List[SupportedFamilyResponse]:
    """Lists all supported anomaly families available for live synthetic injection."""
    return [SupportedFamilyResponse(**f) for f in LiveDigitalTwinInjectionService.get_supported_families()]


@router.post("/inject", response_model=LiveInjectionResponse)
def post_inject_anomaly(
    req: LiveInjectionRequest,
    db: Session = Depends(get_db),
) -> LiveInjectionResponse:
    """Synchronously generates a fresh synthetic anomaly and executes the end-to-end pipeline."""
    service = LiveDigitalTwinInjectionService()
    try:
        service.validate_family(req.exception_family)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    try:
        result = service.execute_injection(
            session=db,
            exception_family=req.exception_family,
            triggered_by=req.triggered_by,
            idempotency_key=req.idempotency_key,
            account_id=req.account_id,
        )
        # Strip nested 'data' from stage events to avoid circular reference in Pydantic serialization.
        # The INJECTION_COMPLETE stage embeds a data={...} that is the same shape as this response.
        sanitized_stages = [
            {k: v for k, v in s.items() if k != "data"} if isinstance(s, dict) else s
            for s in result.get("stages", [])
        ]
        return LiveInjectionResponse(
            injection_id=result["injection_id"],
            exception_family=result["exception_family"],
            source_flag=result.get("source_flag", "live-injected"),
            triggered_at=result["triggered_at"],
            generated_record_identifiers=result.get("generated_record_identifiers", {}),
            processing_status=result.get("processing_status", "COMPLETED"),
            linked_exception_id=result.get("linked_exception_id"),
            exception_state=result.get("exception_state"),
            exception_type=result.get("exception_type"),
            exposure=result.get("exposure"),
            message=result.get("message", "Injection completed"),
            stages=sanitized_stages,
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Live injection pipeline execution failed: {str(e)}",
        )


@router.get("/inject/stream")
def get_stream_inject_anomaly(
    family: str = Query(..., description="Anomaly family to inject"),
    triggered_by: str = Query("demo-operator", description="Operator identifier"),
    idempotency_key: Optional[str] = Query(None, description="Optional idempotency key"),
    account_id: str = Query("nodal_escrow_main", description="Nodal account identifier"),
) -> StreamingResponse:
    """Streams live real-time pipeline execution progress events via Server-Sent Events (SSE)."""
    service = LiveDigitalTwinInjectionService()
    try:
        service.validate_family(family)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )

    def event_generator():
        db = SessionLocal()
        try:
            for progress_event in service.stream_injection_progress(
                session=db,
                exception_family=family,
                triggered_by=triggered_by,
                idempotency_key=idempotency_key,
                account_id=account_id,
            ):
                payload = json.dumps(progress_event, default=str)
                yield f"data: {payload}\n\n"
        except Exception as err:
            err_payload = json.dumps({
                "stage": "ERROR",
                "message": f"Streaming injection failed: {str(err)}",
            })
            yield f"data: {err_payload}\n\n"
        finally:
            db.close()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/injected-cases", response_model=List[InjectedCaseSummaryResponse])
def list_injected_cases(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[InjectedCaseSummaryResponse]:
    """Lists historical live-injected cases in reverse chronological order."""
    stmt = select(InjectedCase).order_by(InjectedCase.triggered_at.desc()).limit(limit).offset(offset)
    records = list(db.scalars(stmt).all())

    return [
        InjectedCaseSummaryResponse(
            injection_id=r.injection_id,
            exception_family=r.exception_family,
            triggered_by=r.triggered_by,
            triggered_at=r.triggered_at.isoformat() if r.triggered_at else "",
            source_flag=r.source_flag,
            linked_exception_id=r.linked_exception_id,
            status=r.status,
            generated_identifiers=json.loads(r.generated_identifiers) if r.generated_identifiers else None,
            details=json.loads(r.details_json) if r.details_json else None,
        )
        for r in records
    ]


@router.get("/injected-cases/{injection_id}", response_model=InjectedCaseSummaryResponse)
def get_injected_case(
    injection_id: str,
    db: Session = Depends(get_db),
) -> InjectedCaseSummaryResponse:
    """Retrieves full details of a specific live synthetic injection."""
    stmt = select(InjectedCase).where(InjectedCase.injection_id == injection_id)
    rec = db.scalars(stmt).first()
    if not rec:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Injected case '{injection_id}' not found.",
        )

    return InjectedCaseSummaryResponse(
        injection_id=rec.injection_id,
        exception_family=rec.exception_family,
        triggered_by=rec.triggered_by,
        triggered_at=rec.triggered_at.isoformat() if rec.triggered_at else "",
        source_flag=rec.source_flag,
        linked_exception_id=rec.linked_exception_id,
        status=rec.status,
        generated_identifiers=json.loads(rec.generated_identifiers) if rec.generated_identifiers else None,
        details=json.loads(rec.details_json) if rec.details_json else None,
    )
