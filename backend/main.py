"""Nodal Sentinel - AI Finance Controller for Nodal Account Health
Main FastAPI application entrypoint.
"""
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
from fastapi import FastAPI
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
    # 1. Strict Configuration & Startup Validation
    settings.validate_startup()
    logger.info(
        operation="STARTUP",
        message="Nodexa backend initialized with configuration validation",
        details=settings.masked_dict(),
    )

    # 2. Initialize Database Schema & Ensure Canonical Seed
    init_db()
    db = SessionLocal()
    try:
        seed_summary = ensure_canonical_seed(db)
        tx_c = seed_summary.get("gateway_transactions_count", seed_summary.get("gateway_transactions", 0))
        exc_c = seed_summary.get("exceptions_total", seed_summary.get("exceptions_detected", 0))
        logger.info(
            operation="STARTUP_SEED",
            message=(
                f"Nodexa startup | Database initialized | "
                f"Operational records: {tx_c} | "
                f"Exceptions: {exc_c} | "
                f"Benchmark: available"
            ),
            details=seed_summary,
        )
    except Exception as e:
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
    finally:
        db.close()

    yield

    logger.info(operation="SHUTDOWN", message="Nodexa backend shutting down")


app = FastAPI(
    title="Nodal Sentinel API",
    description="Deterministic AI Finance Controller for Nodal Account Health with Invariant Guarantees",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# 1. Custom Error Handlers (Unified JSON Error Payloads with Request Correlation)
register_error_handlers(app)

# 2. Middleware Stack (Order: Request Context -> Rate Limiter -> CORS)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
