"""Granular unit tests for Exception REST API endpoints (POST /exceptions/detect, GET /exceptions, GET /exceptions/{id})."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.main import app
from backend.models.database import get_db
from backend.data.generator.service import generate_dataset
from backend.models.dataset import DatasetMetadata


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


def test_post_exceptions_detect_and_idempotency(client: TestClient, db_session: Session):
    """Verifies POST /exceptions/detect returns structured report and is idempotent on repeat execution."""
    summary = generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()

    # First detection execution
    res1 = client.post("/exceptions/detect", json={"account_id": "nodal_escrow_main"})
    assert res1.status_code == 200
    report1 = res1.json()
    assert report1["status"] == "success"
    assert report1["dataset_id"] == summary["dataset_id"]
    assert report1["total_detected_count"] == 14
    assert report1["new_exception_count"] == 14
    assert report1["existing_exception_count"] == 0
    assert report1["legitimate_case_count"] == 4
    assert report1["total_exposure"] > 0
    assert len(report1["exceptions"]) == 14

    # Second detection execution (Idempotent)
    res2 = client.post("/exceptions/detect", json={"account_id": "nodal_escrow_main"})
    assert res2.status_code == 200
    report2 = res2.json()
    assert report2["status"] == "success"
    assert report2["total_detected_count"] == 14
    assert report2["new_exception_count"] == 0
    assert report2["existing_exception_count"] == 14


def test_get_exceptions_filters_and_pagination(client: TestClient, db_session: Session):
    """Verifies all filtering options (state, type, severity, min_exposure, dataset_id) and pagination (limit, offset)."""
    summary = generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()
    client.post("/exceptions/detect", json={})

    # 1. Base list
    res = client.get("/exceptions")
    assert res.status_code == 200
    all_exceptions = res.json()
    assert len(all_exceptions) == 14

    # 2. State filter
    res_state = client.get("/exceptions?state=DETECTED")
    assert res_state.status_code == 200
    assert len(res_state.json()) == 14

    # 3. Exception Type filter
    res_type = client.get("/exceptions?exception_type=GHOST_SETTLEMENT")
    assert res_type.status_code == 200
    ghost_list = res_type.json()
    assert len(ghost_list) == 2
    assert all(e["exception_type"] == "GHOST_SETTLEMENT" for e in ghost_list)

    # 4. Severity filter
    res_sev = client.get("/exceptions?severity=LOW")
    assert res_sev.status_code == 200
    low_list = res_sev.json()
    assert len(low_list) == 4
    assert all(e["severity"] == "LOW" and e["exposure"] == 0 for e in low_list)

    # 5. Min exposure filter
    res_exp = client.get("/exceptions?min_exposure=3000000")
    assert res_exp.status_code == 200
    high_exp_list = res_exp.json()
    assert len(high_exp_list) > 0
    assert all(e["exposure"] >= 3000000 for e in high_exp_list)

    # 6. Dataset ID filter
    res_ds = client.get(f"/exceptions?dataset_id={summary['dataset_id']}")
    assert res_ds.status_code == 200
    assert len(res_ds.json()) == 14

    res_ds_fake = client.get("/exceptions?dataset_id=ds_nonexistent_99999")
    assert res_ds_fake.status_code == 200
    assert len(res_ds_fake.json()) == 0

    # 7. Pagination: limit and offset
    res_limit = client.get("/exceptions?limit=5")
    assert res_limit.status_code == 200
    first_page = res_limit.json()
    assert len(first_page) == 5

    res_offset = client.get("/exceptions?limit=5&offset=5")
    assert res_offset.status_code == 200
    second_page = res_offset.json()
    assert len(second_page) == 5
    assert first_page[0]["exception_id"] != second_page[0]["exception_id"]


def test_get_exception_detail_and_404(client: TestClient, db_session: Session):
    """Verifies GET /exceptions/{id} returns full structure with affected records, transitions, and audit events."""
    generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()
    detect_res = client.post("/exceptions/detect", json={}).json()
    first_exc_id = detect_res["exceptions"][0]["exception_id"]

    # 1. Valid detail retrieval
    res = client.get(f"/exceptions/{first_exc_id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["exception_id"] == first_exc_id
    assert detail["state"] == "DETECTED"
    assert "affected_records" in detail
    assert len(detail["affected_records"]) >= 1
    assert "transitions" in detail
    assert len(detail["transitions"]) >= 1
    assert detail["transitions"][0]["actor_type"] == "SYSTEM"
    assert detail["transitions"][0]["to_state"] == "DETECTED"
    assert "audit_events" in detail
    assert len(detail["audit_events"]) >= 1

    # 2. Nonexistent 404
    res_404 = client.get("/exceptions/EXC-UNKNOWN-999999")
    assert res_404.status_code == 404
    assert "not found" in res_404.json()["detail"].lower()
