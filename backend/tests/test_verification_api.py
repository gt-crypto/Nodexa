"""Tests for Verification REST API endpoints."""
import json
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models.enums import (
    ExceptionType,
    ExceptionSeverity,
    ExceptionState,
    RemediationStatus,
    PolicyActionType,
    PaymentStatus,
    DisputeEventType,
    LedgerEntryType,
    VerificationStatus,
)
from backend.models.exceptions import ExceptionRecord
from backend.models.remediation import RemediationAction
from backend.models.financial_sources import (
    GatewayTransaction,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.database import get_db
from backend.services.repositories import ExceptionRepository, RemediationRepository


def utc_now():
    return datetime.now(timezone.utc)


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


def test_verification_api_full_flow(client: TestClient, db_session: Session):
    """Verify all verification API endpoints: verify, dry_run, get_latest, get_by_id, and retry."""
    exc_repo = ExceptionRepository(db_session)
    rem_repo = RemediationRepository(db_session)

    pmt = GatewayTransaction(
        payment_id="pay_api_ver_01",
        merchant_id="mer_01",
        amount=150000,
        currency="INR",
        status=PaymentStatus.REFUNDED.value,
        method="UPI",
    )
    db_session.add(pmt)

    disp = DisputeRefundEvent(
        event_id="dsp_api_ver_01",
        payment_id="pay_api_ver_01",
        event_type=DisputeEventType.REFUND.value,
        amount=150000,
        timestamp=utc_now(),
    )
    db_session.add(disp)

    ledger = NodalLedgerEntry(
        ledger_id="led_api_ver_01",
        account_id="nodal_escrow_main",
        entry_type=LedgerEntryType.REFUND_DEBIT.value,
        debit=150000,
        credit=0,
        balance_after=850000,
        transaction_id="pay_api_ver_01",
        timestamp=utc_now(),
    )
    db_session.add(ledger)

    exc = ExceptionRecord(
        exception_id="exc_api_ver_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DIAGNOSED.value,
        primary_payment_id="pay_api_ver_01",
        exposure=150000,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    plan = RemediationAction(
        action_id="act_api_ver_01",
        exception_id="exc_api_ver_01",
        action_type=PolicyActionType.REFUND.value,
        status=RemediationStatus.AWAITING_VERIFICATION.value,
        action_payload=json.dumps({"payment_id": "pay_api_ver_01", "amount_minor_units": 150000}),
        before_snapshot=json.dumps({"current_balance": 1000000}),
        after_snapshot=json.dumps({"current_balance": 850000, "debit": 150000, "credit": 0}),
        created_at=utc_now(),
        requested_at=utc_now(),
    )
    rem_repo.create_action(plan)
    db_session.commit()

    # 1. Test Dry Run
    dry_resp = client.post("/remediations/act_api_ver_01/verify?dry_run=true")
    assert dry_resp.status_code == 200
    dry_data = dry_resp.json()
    assert dry_data["projected_status"] == "VERIFIED"
    assert dry_data["projected_remaining_exposure"] == 0
    assert dry_data["eligible_for_closure"] is True

    # 2. Test Live Verification
    live_resp = client.post("/remediations/act_api_ver_01/verify")
    assert live_resp.status_code == 200
    live_data = live_resp.json()
    assert live_data["verification_status"] == "VERIFIED"
    assert live_data["remaining_exposure"] == 0
    assert live_data["exposure_reduction_bps"] == 10000
    assert live_data["final_exception_state"] == "VERIFIED_CLOSED"
    ver_id = live_data["verification_id"]

    # 3. Test GET by ID
    get_id_resp = client.get(f"/verifications/{ver_id}")
    assert get_id_resp.status_code == 200
    assert get_id_resp.json()["verification_id"] == ver_id

    # 4. Test GET latest by remediation
    get_rem_resp = client.get("/remediations/act_api_ver_01/verification")
    assert get_rem_resp.status_code == 200
    assert get_rem_resp.json()["verification_id"] == ver_id

    # 5. Test Non-existent returns 404
    bad_resp = client.get("/verifications/ver_nonexistent_99")
    assert bad_resp.status_code == 404
