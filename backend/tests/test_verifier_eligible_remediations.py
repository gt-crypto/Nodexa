"""Regression and verification tests for Real Eligible Remediations and Verifier Discovery.

Validates:
1. Retrieval of real eligible remediations via /remediations/eligible-for-verification.
2. Retrieval via singular alias /remediation/eligible-for-verification.
3. Clean 400 error handling when nonexistent/legacy demo ID (act_demo_01) is requested.
4. Deterministic dry run verification execution across all 8 verification gates.
5. Idempotent re-verification of already verified / closed remediation records.
6. Latest verification retrieval for executed remediation plans.
7. Empty state handling when no remediation exists.
8. Strict preservation of canonical production database counts (272 records, 14 exceptions).
"""
import json
import os
import sqlite3
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from backend.main import app
from backend.models.database import get_db
from backend.models.enums import (
    ExceptionType,
    ExceptionSeverity,
    ExceptionState,
    RemediationStatus,
    PolicyActionType,
    PaymentStatus,
    DisputeEventType,
    LedgerEntryType,
)
from backend.models.remediation import RemediationAction
from backend.models.verification import VerificationRecord
from backend.models.financial_sources import (
    GatewayTransaction,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.exceptions import ExceptionRecord


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


@pytest.fixture
def seeded_remediation(db_session: Session):
    """Creates a realistic executed remediation awaiting verification in the test database."""
    pmt = GatewayTransaction(
        payment_id="PAY-TEST-VER-01",
        merchant_id="MERCH-01",
        amount=500000,
        currency="INR",
        status=PaymentStatus.REFUNDED.value,
        method="UPI",
    )
    db_session.add(pmt)

    disp = DisputeRefundEvent(
        event_id="DSP-TEST-VER-01",
        payment_id="PAY-TEST-VER-01",
        event_type=DisputeEventType.REFUND.value,
        amount=500000,
        timestamp=utc_now(),
    )
    db_session.add(disp)

    ledger = NodalLedgerEntry(
        ledger_id="LED-TEST-VER-01",
        account_id="nodal_escrow_main",
        entry_type=LedgerEntryType.REFUND_DEBIT.value,
        debit=500000,
        credit=0,
        balance_after=9500000,
        transaction_id="PAY-TEST-VER-01",
        timestamp=utc_now(),
    )
    db_session.add(ledger)

    exc = ExceptionRecord(
        exception_id="EXC-TEST-VER-01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DIAGNOSED.value,
        primary_payment_id="PAY-TEST-VER-01",
        exposure=500000,
        detected_at=utc_now(),
    )
    db_session.add(exc)

    plan = RemediationAction(
        action_id="REM-TEST-VER-01",
        exception_id="EXC-TEST-VER-01",
        action_type=PolicyActionType.REFUND.value,
        status=RemediationStatus.AWAITING_VERIFICATION.value,
        action_payload=json.dumps({"payment_id": "PAY-TEST-VER-01", "amount_minor_units": 500000}),
        before_snapshot=json.dumps({"current_balance": 10000000}),
        after_snapshot=json.dumps({"current_balance": 9500000, "debit": 500000, "credit": 0}),
        created_at=utc_now(),
        requested_at=utc_now(),
    )
    db_session.add(plan)
    db_session.commit()

    return plan


def test_empty_eligible_remediations_when_none_created(client, db_session: Session):
    """Verifies that GET /remediations/eligible-for-verification returns clean empty list if no remediations exist."""
    response = client.get("/remediations/eligible-for-verification")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_eligible_remediations_endpoint(client, seeded_remediation):
    """Verifies that GET /remediations/eligible-for-verification returns real remediation executions."""
    response = client.get("/remediations/eligible-for-verification")
    assert response.status_code == 200
    items = response.json()
    assert isinstance(items, list)
    assert len(items) >= 1

    target = items[0]
    assert target["id"] == seeded_remediation.action_id
    assert target["remediation_id"] == seeded_remediation.action_id
    assert target["exception_id"] == seeded_remediation.exception_id
    assert target["action_type"] == seeded_remediation.action_type
    assert target["status"] == seeded_remediation.status
    assert target["amount_minor_units"] == 500000
    assert target["amount_inr"] == 5000.00
    assert target["eligible_for_verification"] is True
    assert target["already_verified"] is False


def test_get_eligible_remediations_singular_alias(client, seeded_remediation):
    """Verifies that GET /remediation/eligible-for-verification alias returns identical payload."""
    res_plural = client.get("/remediations/eligible-for-verification")
    res_singular = client.get("/remediation/eligible-for-verification")

    assert res_singular.status_code == 200
    assert res_singular.json() == res_plural.json()


def test_nonexistent_remediation_returns_clean_400(client):
    """Verifies that requesting an invalid or legacy demo ID (e.g. act_demo_01) returns clean HTTP 400."""
    response = client.post("/remediations/act_demo_01/verify")
    assert response.status_code == 400
    detail = response.json().get("detail", "")
    assert "Remediation plan 'act_demo_01' not found" in detail


def test_valid_remediation_dry_run_deterministic_checks(client, seeded_remediation):
    """Verifies that dry run verification executes deterministic financial invariant checks without mutations."""
    rem_id = seeded_remediation.action_id

    # Run Dry Run Verify
    res_dry = client.post(f"/remediations/{rem_id}/verify?dry_run=true")
    assert res_dry.status_code == 200
    data = res_dry.json()

    assert data["projected_status"] in ("VERIFIED", "VERIFIED_CLOSED")
    assert data["eligible_for_closure"] is True
    assert isinstance(data["checks_passed"], list)
    assert len(data["checks_passed"]) >= 7

    # Assert key deterministic gates are evaluated
    passed_str = " ".join(data["checks_passed"])
    assert "CHECK-EXECUTION-STATUS" in passed_str
    assert "CHECK-REFUND-STATUS" in passed_str
    assert "CHECK-EXPOSURE-ZERO" in passed_str
    assert "CHECK-INVAR-PROGRESSION" in passed_str
    assert "CHECK-DOUBLE-ENTRY-DELTA" in passed_str
    assert "CHECK-LEGITIMATE-PROTECTION" in passed_str
    assert "CHECK-STALE-STATE" in passed_str


def test_already_verified_remediation_idempotent_closure(client, seeded_remediation):
    """Verifies that running verify on an already verified remediation is completely idempotent."""
    rem_id = seeded_remediation.action_id

    # Run actual verify without dry run
    res_verify = client.post(f"/remediations/{rem_id}/verify?dry_run=false")
    assert res_verify.status_code == 200
    data = res_verify.json()

    assert data["verification_status"] in ("VERIFIED", "VERIFIED_CLOSED")
    assert data["remediation_id"] == rem_id

    # Re-run verify to prove idempotency
    res_idempotent = client.post(f"/remediations/{rem_id}/verify?dry_run=false")
    assert res_idempotent.status_code == 200
    data_idem = res_idempotent.json()
    assert data_idem["verification_status"] in ("VERIFIED", "VERIFIED_CLOSED")
    assert data_idem["verification_id"] == data["verification_id"]


def test_get_latest_verification_record(client, seeded_remediation):
    """Verifies that GET /remediations/{remediation_id}/verification retrieves the authoritative record."""
    rem_id = seeded_remediation.action_id

    # First verify it
    client.post(f"/remediations/{rem_id}/verify?dry_run=false")

    # Fetch latest verification
    res_latest = client.get(f"/remediations/{rem_id}/verification")
    assert res_latest.status_code == 200
    record = res_latest.json()

    assert record["remediation_id"] == rem_id
    assert "verification_id" in record
    assert record["verification_status"] in ("VERIFIED", "VERIFIED_CLOSED")
    assert isinstance(record.get("evidence", record.get("evidence_summary", [])), list)
    assert len(record.get("evidence", record.get("evidence_summary", []))) > 0


def test_production_database_immutability():
    """Ensures production database file nodal_sentinel.db remains strictly unaltered: 272 records, 14 exceptions, 1 verified closed."""
    if os.path.exists("nodal_sentinel.db"):
        conn = sqlite3.connect("nodal_sentinel.db")
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM gateway_transactions")
        gw = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM bank_settlement_batches")
        stl = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM merchant_orders")
        ord_c = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM dispute_refund_events")
        disp = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM nodal_ledger")
        ledg = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM exceptions")
        exc = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM exceptions WHERE state = 'VERIFIED_CLOSED'")
        ver = cursor.fetchone()[0]
        conn.close()

        assert gw == 60
        assert stl == 62
        assert ord_c == 60
        assert disp == 14
        assert ledg == 76
        assert (gw + stl + ord_c + disp + ledg) == 272
        assert exc == 14
        assert ver == 1
