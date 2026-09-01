"""Unit tests for Account-Level Risk Aggregation endpoint."""
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


def test_account_risk_summary_endpoint(client: TestClient, db_session: Session):
    """Verifies GET /risk/account returns aggregated financial exposure, concentration, and priority distribution."""
    generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()

    det_service = ExceptionDetectionService()
    det_report = det_service.detect_exceptions(session=db_session)
    db_session.commit()

    resp = client.get("/risk/account?account_id=nodal_escrow_main")
    assert resp.status_code == 200
    data = resp.json()

    assert data["account_id"] == "nodal_escrow_main"
    assert data["total_open_exposure"] > 0
    assert data["total_material_exposure"] > 0
    assert data["total_exceptions_count"] == det_report.total_detected_count

    # Verify P1-P4 counts sum to total exceptions
    p_sum = data["p1_count"] + data["p2_count"] + data["p3_count"] + data["p4_count"]
    assert p_sum == data["total_exceptions_count"]

    assert data["highest_risk_exception_id"] is not None
    assert data["highest_risk_score"] > 0

    # Top exposure list validation
    assert len(data["top_exposure_exceptions"]) <= 5
    for i in range(len(data["top_exposure_exceptions"]) - 1):
        assert data["top_exposure_exceptions"][i]["exposure"] >= data["top_exposure_exceptions"][i + 1]["exposure"]

    # Top risk list validation
    assert len(data["top_risk_exceptions"]) <= 5
    for i in range(len(data["top_risk_exceptions"]) - 1):
        assert data["top_risk_exceptions"][i]["risk_score"] >= data["top_risk_exceptions"][i + 1]["risk_score"]

    # Concentration bps <= 10000
    assert 0 <= data["exposure_concentration_top3_bps"] <= 10000
