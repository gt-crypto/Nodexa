"""Unit tests for Risk Policy Gating REST API endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models.database import get_db
from backend.models.enums import ExceptionState, ExceptionType, PolicyActionType
from backend.models.exceptions import ExceptionRecord


@pytest.fixture
def client(db_session: Session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def test_policy_api_endpoints_and_simulation(client: TestClient, db_session: Session):
    """Verifies POST /exceptions/{id}/policy-check, GET history, GET by ID, simulation mode, and GET config."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-API-TEST-1-PAY-000001",
        primary_payment_id="PAY-000001",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="CRITICAL",
        state=ExceptionState.DIAGNOSED.value,
        exposure=5000000,
        detected_at=now,
        created_at=now,
    )
    db_session.add(exc)
    db_session.commit()

    # 1. GET /policy/config
    cfg_resp = client.get("/policy/config")
    assert cfg_resp.status_code == 200
    cfg_data = cfg_resp.json()
    assert cfg_data["policy_version"] == "v1"
    assert len(cfg_data["allowlisted_actions"]) == 10

    # 2. Simulation mode: POST policy-check with simulation=true
    sim_resp = client.post(
        "/exceptions/EXC-API-TEST-1-PAY-000001/policy-check",
        json={"requested_action": PolicyActionType.REFUND.value, "simulation": True},
    )
    assert sim_resp.status_code == 200
    sim_data = sim_resp.json()
    assert sim_data["decision_id"].startswith("SIM-")

    # Verify no history persisted yet
    hist_before = client.get("/exceptions/EXC-API-TEST-1-PAY-000001/policy-decisions")
    assert hist_before.status_code == 200
    assert len(hist_before.json()) == 0

    # 3. Standard mode: POST policy-check with simulation=false
    post_resp = client.post(
        "/exceptions/EXC-API-TEST-1-PAY-000001/policy-check",
        json={"requested_action": PolicyActionType.REFUND.value, "simulation": False},
    )
    assert post_resp.status_code == 200
    post_data = post_resp.json()
    assert post_data["decision_id"].startswith("PD-")
    assert post_data["decision"] in ("REQUIRE_APPROVAL", "REQUIRE_ESCALATION")

    # Verify history is persisted
    hist_after = client.get("/exceptions/EXC-API-TEST-1-PAY-000001/policy-decisions")
    assert hist_after.status_code == 200
    assert len(hist_after.json()) == 1

    # 4. GET /policy/decisions/{decision_id}
    dec_id = post_data["decision_id"]
    get_dec = client.get(f"/policy/decisions/{dec_id}")
    assert get_dec.status_code == 200
    assert get_dec.json()["decision_id"] == dec_id

    # 5. 404 for unknown exception and decision
    err_exc = client.post("/exceptions/EXC-UNKNOWN-999/policy-check", json={"requested_action": "REFUND"})
    assert err_exc.status_code == 404

    err_dec = client.get("/policy/decisions/PD-NONEXISTENT-999")
    assert err_dec.status_code == 404
