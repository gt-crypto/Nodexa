"""Unit tests for Risk and Exposure REST API endpoints."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models.database import get_db
from backend.data.generator.service import generate_dataset
from backend.exceptions.service import ExceptionDetectionService


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


def test_risk_api_full_flow(client: TestClient, db_session: Session):
    """Verifies POST /exceptions/{id}/assess-risk, GET /exceptions/{id}/risk, and GET /risk/queue."""
    generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()

    det_service = ExceptionDetectionService()
    det_report = det_service.detect_exceptions(session=db_session)
    db_session.commit()

    first_exc_id = det_report.exceptions[0]["exception_id"]

    # 1. POST /exceptions/{id}/assess-risk
    post_resp = client.post(f"/exceptions/{first_exc_id}/assess-risk", json={"force_recalculate": False})
    assert post_resp.status_code == 200
    post_data = post_resp.json()
    assert post_data["exception_id"] == first_exc_id
    assert post_data["risk_score"] >= 0
    assert post_data["priority"] in ("P1", "P2", "P3", "P4")
    assert post_data["materiality"] in ("NONE", "LOW", "MEDIUM", "HIGH", "MATERIAL", "SEVERE")
    assert "score_breakdown" in post_data

    # 2. GET /exceptions/{id}/risk
    get_resp = client.get(f"/exceptions/{first_exc_id}/risk")
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["assessment_id"] == post_data["assessment_id"]

    # 3. GET /risk/queue
    queue_resp = client.get("/risk/queue?limit=10")
    assert queue_resp.status_code == 200
    queue = queue_resp.json()
    assert len(queue) >= 1
    assert queue[0]["priority"] in ("P1", "P2", "P3", "P4")

    # 4. Filters on /risk/queue
    p1_resp = client.get("/risk/queue?priority=P1")
    assert p1_resp.status_code == 200
    p1_items = p1_resp.json()
    assert all(i["priority"] == "P1" for i in p1_items)

    # 5. 404 for unknown exception
    err_post = client.post("/exceptions/EXC-NONEXISTENT-999/assess-risk", json={})
    assert err_post.status_code == 404

    err_get = client.get("/exceptions/EXC-NONEXISTENT-999/risk")
    assert err_get.status_code == 404
