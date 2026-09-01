"""Granular unit tests for individual AI Investigation REST API endpoints."""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.main import app
from backend.models.database import get_db
from backend.models.enums import ExceptionState
from backend.models.exceptions import ExceptionRecord
from backend.models.financial_sources import GatewayTransaction, BankSettlementBatch
from backend.data.generator.service import generate_dataset


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


def test_post_investigate_valid_exception_success(client: TestClient, db_session: Session):
    """POST /exceptions/{id}/investigate executes successfully, returns structured analysis, and updates lifecycle."""
    now = datetime.now(timezone.utc)
    pmt = GatewayTransaction(
        payment_id="PAY-API-INV-1",
        merchant_id="M1",
        amount=1500000,
        currency="INR",
        status="FAILED",
        created_at=now,
        method="CARD",
    )
    settle = BankSettlementBatch(
        settlement_id="SET-API-INV-1",
        payment_id="PAY-API-INV-1",
        acquirer_id="A1",
        net_amount=1477500,
        clearing_timestamp=now,
    )
    exc = ExceptionRecord(
        exception_id="EXC-API-INV-1",
        exception_type="GHOST_SETTLEMENT",
        severity="CRITICAL",
        state=ExceptionState.DETECTED.value,
        exposure=1477500,
        primary_payment_id="PAY-API-INV-1",
        detected_at=now,
        created_at=now,
    )
    db_session.add_all([pmt, settle, exc])
    db_session.commit()

    resp = client.post("/exceptions/EXC-API-INV-1/investigate", json={"reinvestigate": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "success"
    assert data["exception_id"] == "EXC-API-INV-1"
    assert data["structured_output"] is not None
    assert data["structured_output"]["root_cause_category"] == "PAYMENT_STATE_CONTRADICTION"

    # Verify lifecycle state updated in DB
    updated = db_session.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == "EXC-API-INV-1")).first()
    assert updated.state == ExceptionState.DIAGNOSED.value


def test_post_investigate_nonexistent_exception_returns_404(client: TestClient):
    """POST /exceptions/{id}/investigate returns 404 when exception does not exist."""
    resp = client.post("/exceptions/EXC-NONEXISTENT-999/investigate", json={})
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_post_investigate_invalid_lifecycle_state(client: TestClient, db_session: Session):
    """POST /exceptions/{id}/investigate fails gracefully when exception is in an uninvestigable state."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-RESOLVING-STATE",
        exception_type="GHOST_SETTLEMENT",
        severity="HIGH",
        state=ExceptionState.RESOLVING.value,  # Invalid starting state
        exposure=1000000,
        primary_payment_id="PAY-NONE",
        detected_at=now,
        created_at=now,
    )
    db_session.add(exc)
    db_session.commit()

    resp = client.post("/exceptions/EXC-RESOLVING-STATE/investigate", json={"reinvestigate": False})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "failed"
    assert "cannot investigate" in data["error_message"].lower()


def test_get_exception_investigations_history(client: TestClient, db_session: Session):
    """GET /exceptions/{id}/investigations returns full history of runs for the exception."""
    generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()

    detect_res = client.post("/exceptions/detect", json={}).json()
    first_exc_id = detect_res["exceptions"][0]["exception_id"]

    # Initial investigation
    inv1 = client.post(f"/exceptions/{first_exc_id}/investigate", json={"reinvestigate": False}).json()

    # Reinvestigation
    inv2 = client.post(f"/exceptions/{first_exc_id}/investigate", json={"reinvestigate": True}).json()

    # Fetch history
    history_resp = client.get(f"/exceptions/{first_exc_id}/investigations")
    assert history_resp.status_code == 200
    runs = history_resp.json()
    assert len(runs) == 2
    assert all(r["status"] == "COMPLETED" for r in runs)


def test_get_exception_investigations_nonexistent_returns_404(client: TestClient):
    """GET /exceptions/{id}/investigations returns 404 for unknown exception."""
    resp = client.get("/exceptions/EXC-UNKNOWN-404/investigations")
    assert resp.status_code == 404


def test_get_investigation_run_detail_all_fields(client: TestClient, db_session: Session):
    """GET /investigations/{id} returns comprehensive details of a completed investigation run."""
    now = datetime.now(timezone.utc)
    pmt = GatewayTransaction(
        payment_id="PAY-DETAIL-1",
        merchant_id="M1",
        amount=2000000,
        currency="INR",
        status="FAILED",
        created_at=now,
        method="CARD",
    )
    settle = BankSettlementBatch(
        settlement_id="SET-DETAIL-1",
        payment_id="PAY-DETAIL-1",
        acquirer_id="A1",
        net_amount=1970000,
        clearing_timestamp=now,
    )
    exc = ExceptionRecord(
        exception_id="EXC-DETAIL-1",
        exception_type="GHOST_SETTLEMENT",
        severity="CRITICAL",
        state=ExceptionState.DETECTED.value,
        exposure=1970000,
        primary_payment_id="PAY-DETAIL-1",
        detected_at=now,
        created_at=now,
    )
    db_session.add_all([pmt, settle, exc])
    db_session.commit()

    inv_post = client.post("/exceptions/EXC-DETAIL-1/investigate", json={}).json()
    inv_id = inv_post["investigation_id"]

    detail_resp = client.get(f"/investigations/{inv_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["investigation_id"] == inv_id
    assert detail["exception_id"] == "EXC-DETAIL-1"
    assert detail["status"] == "COMPLETED"
    assert detail["final_classification"] == "PAYMENT_STATE_CONTRADICTION"
    assert detail["root_cause"] is not None
    assert detail["confidence"] is not None
    assert detail["agent_version"] == "v1.0.0-agent"
    assert detail["human_approval_required"] is True  # CRITICAL severity triggers approval flag


def test_get_investigation_run_detail_nonexistent_returns_404(client: TestClient):
    """GET /investigations/{id} returns 404 for unknown investigation ID."""
    resp = client.get("/investigations/inv_nonexistent_000")
    assert resp.status_code == 404
