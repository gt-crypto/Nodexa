"""Unit tests for Evaluation REST API endpoints."""
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


def test_evaluation_api_full_workflow(client: TestClient, db_session: Session):
    """Verifies all REST API evaluation endpoints: run -> get run -> cases -> metrics -> errors -> benchmark."""
    # 1. Setup synthetic data
    summary = generate_dataset(session=db_session, record_count=30, seed=42)
    db_session.commit()
    dataset_id = summary["dataset_id"]

    det_service = ExceptionDetectionService()
    det_service.detect_exceptions(session=db_session)
    db_session.commit()

    # 2. Trigger POST /evaluation/run
    run_resp = client.post(
        "/evaluation/run",
        json={"dataset_id": dataset_id, "force_rerun": True},
    )
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    run_id = run_data["run"]["evaluation_run_id"]
    assert run_data["run"]["status"] == "COMPLETED"
    assert run_data["run"]["overall_score"] > 0

    # 3. GET /evaluation/runs
    list_resp = client.get("/evaluation/runs")
    assert list_resp.status_code == 200
    runs = list_resp.json()
    assert len(runs) >= 1
    assert any(r["evaluation_run_id"] == run_id for r in runs)

    # 4. GET /evaluation/runs/{id}
    get_run_resp = client.get(f"/evaluation/runs/{run_id}")
    assert get_run_resp.status_code == 200
    assert get_run_resp.json()["run"]["evaluation_run_id"] == run_id

    # 5. GET /evaluation/runs/{id}/cases
    cases_resp = client.get(f"/evaluation/runs/{run_id}/cases")
    assert cases_resp.status_code == 200

    # 6. GET /evaluation/runs/{id}/metrics
    metrics_resp = client.get(f"/evaluation/runs/{run_id}/metrics")
    assert metrics_resp.status_code == 200
    assert "scores" in metrics_resp.json()

    # 7. GET /evaluation/runs/{id}/errors
    errors_resp = client.get(f"/evaluation/runs/{run_id}/errors")
    assert errors_resp.status_code == 200
    assert "false_positives" in errors_resp.json()

    # 8. GET /evaluation/benchmark
    bench_resp = client.get("/evaluation/benchmark")
    assert bench_resp.status_code == 200
    assert bench_resp.json()["run"]["evaluation_run_id"] == run_id
