"""Unit tests for Remediation REST API endpoints."""
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models.database import get_db
from backend.models.enums import ExceptionState, ExceptionType, PolicyActionType, PaymentStatus
from backend.models.exceptions import ExceptionRecord
from backend.models.financial_sources import GatewayTransaction, NodalLedgerEntry
from backend.models.investigation import InvestigationRun


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


def test_remediation_api_full_workflow(client: TestClient, db_session: Session):
    """Verifies complete REST API workflow: plan -> approve -> dry-run -> execute -> get history."""
    now = datetime.now(timezone.utc)
    
    gt = GatewayTransaction(
        payment_id="PAY-API-REM-001",
        merchant_id="MERCH-001",
        amount=3000000,
        currency="INR",
        method="CARD",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
    )
    nle = NodalLedgerEntry(
        ledger_id="NLE-API-INIT",
        account_id="nodal_escrow_main",
        entry_type="OPENING_BALANCE",
        debit=0,
        credit=50000000,
        balance_after=50000000,
        reference="INIT",
        timestamp=now,
    )
    exc = ExceptionRecord(
        exception_id="EXC-API-REM-PAY-API-REM-001",
        primary_payment_id="PAY-API-REM-001",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="CRITICAL",
        state=ExceptionState.DIAGNOSED.value,
        exposure=3000000,
        detected_at=now,
        created_at=now,
    )
    inv = InvestigationRun(
        investigation_id="INV-API-REM-001",
        exception_id="EXC-API-REM-PAY-API-REM-001",
        status="COMPLETED",
        final_classification="PAYMENT_STATE_CONTRADICTION",
        confidence="0.95",
        root_cause="Diagnosed ghost settlement",
        created_at=now,
    )
    db_session.add_all([gt, nle, exc, inv])
    db_session.commit()

    # 1. POST /exceptions/{id}/remediation-plan
    plan_resp = client.post(
        "/exceptions/EXC-API-REM-PAY-API-REM-001/remediation-plan",
        json={
            "action": "REFUND",
            "parameters": {"payment_id": "PAY-API-REM-001", "amount_minor_units": 3000000, "reason": "API refund plan"},
            "requested_by": "operator-api-01",
        },
    )
    assert plan_resp.status_code == 200
    plan_data = plan_resp.json()
    rem_id = plan_data["remediation_id"]
    assert plan_data["status"] == "PENDING_APPROVAL"

    # 2. GET /remediations/{id}
    get_plan = client.get(f"/remediations/{rem_id}")
    assert get_plan.status_code == 200
    assert get_plan.json()["remediation_id"] == rem_id

    # 3. POST /remediations/{id}/approve
    appr_resp = client.post(
        f"/remediations/{rem_id}/approve",
        json={
            "approved_by": "finance-admin-01",
            "decision": "APPROVED",
            "reason": "Approved via API",
        },
    )
    assert appr_resp.status_code == 200
    assert appr_resp.json()["decision"] == "APPROVED"

    # 4. POST /remediations/{id}/dry-run
    dry_resp = client.post(f"/remediations/{rem_id}/dry-run")
    assert dry_resp.status_code == 200
    assert dry_resp.json()["eligible"] is True

    # 5. POST /remediations/{id}/execute
    exec_resp = client.post(f"/remediations/{rem_id}/execute")
    assert exec_resp.status_code == 200
    assert exec_resp.json()["status"] == "AWAITING_VERIFICATION"

    # 6. GET /exceptions/{id}/remediations
    list_resp = client.get("/exceptions/EXC-API-REM-PAY-API-REM-001/remediations")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1
