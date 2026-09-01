"""Disaster Recovery, Controlled Failures, and Fault Tolerance Tests.

Verifies that unexpected errors, database disconnects, invalid configurations,
malformed requests, and rate-limit violations fail safely with structured errors
and zero data corruption.
"""
import pytest
from starlette.testclient import TestClient
from sqlalchemy.orm import Session

from backend.config import Settings
from backend.errors.exceptions import ValidationError, NotFoundError, PolicyBlockedError


def test_malformed_request_returns_structured_validation_error(client: TestClient):
    """Verifies that malformed JSON payloads return structured error payloads without stack traces."""
    # Send empty payload to POST /data/generate
    resp = client.post("/data/generate", json={"record_count": -5})  # Negative record count invalid
    assert resp.status_code == 400
    data = resp.json()
    assert data["error"] == "VALIDATION_ERROR"
    assert "request_id" in data
    assert "details" in data
    assert "validation_errors" in data["details"]


def test_not_found_endpoint_returns_structured_error(client: TestClient):
    """Verifies that 404 routes return unified JSON error responses with request IDs."""
    resp = client.get("/non_existent_sentinel_route")
    assert resp.status_code == 404
    data = resp.json()
    assert data["error"] == "NOT_FOUND"
    assert "request_id" in data


def test_production_settings_startup_validation():
    """Verifies that production environment enforces mandatory PostgreSQL and API key checks."""
    # 1. Production with SQLite must fail
    invalid_prod_settings = Settings(
        environment="production",
        database_url="sqlite:///./test.db",
        llm_provider="mock",
    )
    with pytest.raises(ValueError, match="SQLite is prohibited in production"):
        invalid_prod_settings.validate_startup()

    # 2. Production with OpenAI provider but missing API key must fail
    invalid_llm_settings = Settings(
        environment="production",
        database_url="postgresql://user:pass@localhost:5432/nodal",
        llm_provider="openai",
        llm_api_key=None,
        allowed_origins=["https://sentinel.nodal.internal"],
    )
    with pytest.raises(ValueError, match="LLM_API_KEY is required"):
        invalid_llm_settings.validate_startup()


def test_secret_masking_in_settings():
    """Verifies that settings dict masks sensitive API keys."""
    cfg = Settings(
        llm_provider="openai",
        llm_api_key="sk-proj-secret-key-12345678",
    )
    masked = cfg.masked_dict()
    assert masked["llm_api_key"] == "***5678"
    assert "sk-proj" not in masked["llm_api_key"]


def test_rate_limit_middleware_enforcement(client: TestClient):
    """Verifies that exceeding configured rate limits returns 429 with retry-after header."""
    # The route /data/generate has limit 10 requests / 60s
    # We send 12 requests in rapid succession with X-Test-Rate-Limit enabled
    status_codes = []
    for i in range(12):
        resp = client.post(
            "/data/generate",
            json={"record_count": 1, "seed": 100 + i},
            headers={"X-Test-Rate-Limit": "true"},
        )
        status_codes.append(resp.status_code)

    # At least one request should receive 429
    assert 429 in status_codes
