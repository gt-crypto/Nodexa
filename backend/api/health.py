"""Health, Readiness, and Observability Endpoints for Nodal Sentinel."""
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text, select, func
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.models.exceptions import ExceptionRecord
from backend.models.remediation import RemediationAction
from backend.models.verification import VerificationRecord
from backend.models.evaluation import EvaluationRun
from backend.config import settings

router = APIRouter(tags=["Observability"])


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    timestamp: str


class ReadinessResponse(BaseModel):
    status: str
    database: str
    environment: str
    llm_provider: str
    timestamp: str


class OperationalMetricsResponse(BaseModel):
    service: str
    timestamp: str
    total_exceptions: int
    open_exceptions: int
    resolved_exceptions: int
    total_remediations: int
    total_verifications: int
    latest_benchmark_score: Optional[int] = None
    latest_benchmark_safety: Optional[str] = None


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Lightweight liveness probe ensuring API server is responsive.
    
    Guaranteed to be non-blocking with zero database access or AI processing.
    """
    return HealthResponse(
        status="healthy",
        service="nodal-sentinel-backend",
        version="0.1.0",
        environment=settings.environment,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/ready", response_model=ReadinessResponse)
def get_readiness(session: Session = Depends(get_db)):
    """Readiness probe verifying operational database connectivity and core configuration."""
    try:
        # Verify database connection with lightweight query
        session.execute(text("SELECT 1"))
        return ReadinessResponse(
            status="ready",
            database="connected",
            environment=settings.environment,
            llm_provider=settings.llm_provider,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
    except Exception as e:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": "disconnected",
                "error": "Database connectivity check failed",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )


@router.get("/metrics", response_model=OperationalMetricsResponse)
def get_operational_metrics(session: Session = Depends(get_db)) -> OperationalMetricsResponse:
    """Safe operational metrics aggregator providing real-time telemetry counters."""
    now = datetime.now(timezone.utc).isoformat()

    try:
        total_exc = session.scalar(select(func.count(ExceptionRecord.id))) or 0
        open_exc = session.scalar(
            select(func.count(ExceptionRecord.id)).where(
                ExceptionRecord.state.notin_(["VERIFIED_CLOSED", "FAILED_ESCALATED"])
            )
        ) or 0
        closed_exc = session.scalar(
            select(func.count(ExceptionRecord.id)).where(
                ExceptionRecord.state == "VERIFIED_CLOSED"
            )
        ) or 0

        total_rem = session.scalar(select(func.count(RemediationAction.id))) or 0
        total_ver = session.scalar(select(func.count(VerificationRecord.id))) or 0

        latest_eval = session.scalars(
            select(EvaluationRun).order_by(EvaluationRun.created_at.desc())
        ).first()

        latest_score = latest_eval.overall_score if latest_eval else None
        latest_safety = latest_eval.safety_status if latest_eval else None

        return OperationalMetricsResponse(
            service="nodal-sentinel",
            timestamp=now,
            total_exceptions=total_exc,
            open_exceptions=open_exc,
            resolved_exceptions=closed_exc,
            total_remediations=total_rem,
            total_verifications=total_ver,
            latest_benchmark_score=latest_score,
            latest_benchmark_safety=latest_safety,
        )
    except Exception:
        return OperationalMetricsResponse(
            service="nodal-sentinel",
            timestamp=now,
            total_exceptions=0,
            open_exceptions=0,
            resolved_exceptions=0,
            total_remediations=0,
            total_verifications=0,
        )
