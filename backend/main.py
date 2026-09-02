"""Nodal Sentinel - AI Finance Controller for Nodal Account Health
Main FastAPI application entrypoint.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from backend.config import settings
from backend.logging import logger
from backend.models.database import init_db
from backend.middleware.request_context import RequestContextMiddleware
from backend.middleware.rate_limit import RateLimitMiddleware
from backend.errors.handlers import register_error_handlers

from backend.api.health import router as health_router
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

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager to validate configuration and initialize database schema on startup."""
    # 1. Strict Configuration & Startup Validation
    settings.validate_startup()
    logger.info(
        operation="STARTUP",
        message="Nodal Sentinel backend initialized with configuration validation",
        details=settings.masked_dict(),
    )

    # 2. Initialize Database Schema
    init_db()
    yield

    logger.info(operation="SHUTDOWN", message="Nodal Sentinel backend shutting down")


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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=(settings.environment == "development"),
    )
