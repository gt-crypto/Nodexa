"""Nodal Sentinel - AI Finance Controller for Nodal Account Health
Main FastAPI application entrypoint.
"""
import time
import uuid
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.config import settings
from backend.logging import logger
from backend.models.database import init_db, SessionLocal
from backend.data.seed_clean import ensure_canonical_seed
from backend.middleware.request_context import RequestContextMiddleware
from backend.middleware.rate_limit import RateLimitMiddleware
from backend.errors.handlers import register_error_handlers

from backend.api.health import router as health_router
from backend.api.diagnostics import router as diagnostics_router
from backend.api.data import router as data_router
from backend.api.nodal import router as nodal_router
from backend.api.exceptions import router as exceptions_router
from backend.api.investigations import router as investigations_router
from backend.api.risk import router as risk_router
from backend.api.policy import router as policy_router
from backend.api.remediation import router as remediation_router
from backend.api.verification import router as verification_router
from backend.api.evaluation import evaluation_router
from backend.api.demo import router as demo_router
from backend.api.copilot import router as copilot_router
from backend.api.verifier import router as verifier_router
from backend.api.patterns import router as patterns_router
from backend.api.merchants import router as merchants_router
from backend.api.impact import router as impact_router
from backend.api.predictions import router as predictions_router
from backend.api.calibration import router as calibration_router
from backend.api.escalation import router as escalation_router

load_dotenv()


STARTUP_ERROR: Optional[dict] = None


def get_startup_error() -> Optional[dict]:
    """Returns any recorded startup error for diagnostic telemetry."""
    return STARTUP_ERROR


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to validate configuration, initialize database schema, and seed canonical dataset."""
    global STARTUP_ERROR
    t_startup_start = time.perf_counter()

    # 1. Strict Configuration & Startup Validation
    t0 = time.perf_counter()
    try:
        settings.validate_startup()
        t_cfg = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            operation="STARTUP_CONFIG_VALIDATED",
            message=f"System configuration validated successfully in {t_cfg}ms.",
            details=settings.masked_dict(),
        )
    except Exception as e:
        t_cfg = round((time.perf_counter() - t0) * 1000, 2)
        import traceback
        tb = traceback.format_exc()
        STARTUP_ERROR = {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": tb,
        }
        logger.error(operation="STARTUP_CONFIG_ERROR", message=str(e), details={"traceback": tb})

    # 2. Database Schema Creation and Column Migrations
    t0 = time.perf_counter()
    try:
        init_db()
        t_db = round((time.perf_counter() - t0) * 1000, 2)
        logger.info(
            operation="STARTUP_SCHEMA_READY",
            message=f"Database schema verified/migrated in {t_db}ms.",
        )
    except Exception as e:
        t_db = round((time.perf_counter() - t0) * 1000, 2)
        import traceback
        tb = traceback.format_exc()
        STARTUP_ERROR = {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": tb,
        }
        logger.error(operation="STARTUP_INIT_DB_ERROR", message=str(e), details={"traceback": tb})

    # 3. Canonical Synthetic Seed Verification
    t0 = time.perf_counter()
    seed_summary = {}
    try:
        db = SessionLocal()
        try:
            seed_summary = ensure_canonical_seed(db)
            t_seed = round((time.perf_counter() - t0) * 1000, 2)
            logger.info(
                operation="CANONICAL_SEED_VERIFIED",
                message=f"Canonical synthetic dataset verified and ready in {t_seed}ms.",
                details=seed_summary,
            )
        finally:
            db.close()
    except Exception as e:
        t_seed = round((time.perf_counter() - t0) * 1000, 2)
        import traceback
        tb = traceback.format_exc()
        STARTUP_ERROR = {
            "error": str(e),
            "type": type(e).__name__,
            "traceback": tb,
        }
        logger.error(
            operation="STARTUP_SEED_ERROR",
            message=f"Failed to ensure canonical seed on startup: {str(e)}",
            details={"error": str(e), "traceback": tb},
        )

    t_total = round((time.perf_counter() - t_startup_start) * 1000, 2)
    logger.info(
        operation="STARTUP_PERFORMANCE",
        message=f"Total application startup ready in {t_total}ms (config: {t_cfg}ms, db_schema: {t_db}ms, seed_check: {t_seed}ms).",
        details={
            "total_startup_ms": t_total,
            "config_ms": t_cfg,
            "db_schema_ms": t_db,
            "seed_check_ms": t_seed,
            "seed_status": seed_summary.get("status"),
        },
    )

    yield


app = FastAPI(
    title="Nodexa API",
    description="Deterministic AI Finance Controller for Nodal Account Health with Invariant Guarantees",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Robust CORS Configuration with Security Gating
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"https://.*\.onrender\.com|http://localhost:\d+|http://127\.0\.0\.1:\d+",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def audit_logging_middleware(request: Request, call_next):
    """Enforces request tracing, logging, and performance tracking."""
    req_id = request.headers.get("X-Request-ID", f"req_{uuid.uuid4().hex[:12]}")
    request.state.request_id = req_id
    start_time = time.perf_counter()

    response = await call_next(request)

    latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Response-Time"] = f"{latency_ms}ms"

    # Health and diagnostics check logging sampled or silent to avoid log pollution
    if not request.url.path.startswith("/health"):
        logger.info(
            operation="HTTP_REQUEST",
            message=f"{request.method} {request.url.path} -> {response.status_code} ({latency_ms}ms)",
            details={
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "latency_ms": latency_ms,
                "request_id": req_id,
            },
        )
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", "req_system_internal")
    import traceback
    tb = traceback.format_exc()
    logger.error(
        operation="UNHANDLED_EXCEPTION",
        message=str(exc),
        details={"path": str(request.url), "request_id": req_id, "traceback": tb},
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": str(exc),
            "detail": str(exc),
            "request_id": req_id,
            "details": {"traceback": tb.splitlines()[-6:] if tb else []},
        },
    )


# 1. Custom Error Handlers (Unified JSON Error Payloads with Request Correlation)
register_error_handlers(app)

# 2. Middleware Stack (Order: Request Context -> Rate Limiter -> CORS)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RateLimitMiddleware)

# 3. Router Registrations
app.include_router(health_router)
app.include_router(diagnostics_router)
app.include_router(data_router)
app.include_router(nodal_router)
app.include_router(exceptions_router)
app.include_router(investigations_router)
app.include_router(risk_router)
app.include_router(policy_router)
app.include_router(remediation_router)
app.include_router(verification_router)
app.include_router(evaluation_router)
app.include_router(demo_router)
app.include_router(copilot_router)
app.include_router(verifier_router)
app.include_router(patterns_router)
app.include_router(merchants_router)
app.include_router(impact_router)
app.include_router(predictions_router)
app.include_router(calibration_router)
app.include_router(escalation_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=(settings.environment == "development"),
    )
