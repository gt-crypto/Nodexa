"""Comprehensive unit and integration tests for Prompt 20 - Escalation Webhook."""
import hmac
import hashlib
import json
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import pytest
import requests
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

import backend.models
from backend.main import app
from backend.models.exceptions import ExceptionRecord
from backend.models.policy import PolicyDecisionRecord
from backend.models.risk import RiskAssessment
from backend.models.escalation import EscalationWebhookDelivery
from backend.models.audit import AuditEvent
from backend.escalation.service import EscalationWebhookService
from backend.escalation.security import generate_hmac_signature, validate_webhook_url


@pytest.fixture
def mock_exception(db_session: Session) -> ExceptionRecord:
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC_ESC_TEST_001",
        exception_type="GHOST_SETTLEMENT",
        severity="CRITICAL",
        state="FAILED_ESCALATED",
        exposure=2500000,
        primary_payment_id="PAY_ESC_001",
        source_flag="seeded",
        detected_at=now,
    )
    pol = PolicyDecisionRecord(
        decision_id="POL_ESC_TEST_001",
        exception_id="EXC_ESC_TEST_001",
        requested_action="LEDGER_ADJUSTMENT",
        decision="BLOCK",
        policy_version="v1",
        allowed_actions="[]",
        prohibited_actions='["AUTO_REMEDIATE"]',
        approval_required=True,
        escalation_required=True,
        escalation_level="CRITICAL",
        escalation_reason="Material loss exceeding threshold",
        rationale="Automated block due to ghost settlement variance",
        risk_score=95,
        priority="P1",
        materiality="MATERIAL",
        exposure=2500000,
        evaluated_at=now,
        created_at=now,
    )
    risk = RiskAssessment(
        assessment_id="RISK_ESC_TEST_001",
        exception_id="EXC_ESC_TEST_001",
        deterministic_exposure=2500000,
        currency="INR",
        exposure_type="DIRECT_FINANCIAL_LOSS",
        gross_exposure=2500000,
        net_exposure=2500000,
        materiality="MATERIAL",
        risk_score=95,
        priority="P1",
        escalation="IMMEDIATE_ESCALATION",
        explanation="Severe exposure",
        calculated_at=now,
        created_at=now,
    )
    db_session.add_all([exc, pol, risk])
    db_session.commit()
    return exc


def test_webhook_disabled(db_session: Session, mock_exception: ExceptionRecord):
    """1. Webhook disabled returns DISABLED status without making network calls."""
    service = EscalationWebhookService(enabled=False, webhook_url="https://hooks.example.com/esc")
    res = service.trigger_escalation(session=db_session, exception_id=mock_exception.exception_id)

    assert res["status"] == "DISABLED"
    assert res["success"] is False
    assert "disabled" in res["message"].lower()

    deliv = db_session.query(EscalationWebhookDelivery).filter_by(exception_id=mock_exception.exception_id).first()
    assert deliv is not None
    assert deliv.delivery_status == "DISABLED"


def test_webhook_unconfigured(db_session: Session, mock_exception: ExceptionRecord):
    """2. Webhook enabled but URL unconfigured returns DISABLED status."""
    service = EscalationWebhookService(enabled=True, webhook_url=None)
    res = service.trigger_escalation(session=db_session, exception_id=mock_exception.exception_id)

    assert res["status"] == "DISABLED"
    assert "not configured" in res["message"].lower()


def test_payload_schema_and_deterministic_event_id(db_session: Session, mock_exception: ExceptionRecord):
    """4. Payload schema & 5. Deterministic event ID."""
    service = EscalationWebhookService(enabled=True, webhook_url="https://hooks.example.com/test")
    payload, event_id = service.build_escalation_payload(
        exception=mock_exception,
        policy=mock_exception.policy_decisions[0],
        risk=mock_exception.risk_assessments[0],
        request_id="req_test_123",
    )

    assert event_id.startswith("esc_evt_")
    assert payload["event_id"] == event_id
    assert payload["event_type"] == "EXCEPTION_ESCALATED"
    assert payload["schema_version"] == "v1"
    assert payload["exception"]["exception_id"] == mock_exception.exception_id
    assert payload["exception"]["exposure_paise"] == 2500000
    assert payload["risk"]["priority"] == "P1"
    assert payload["policy"]["decision"] == "BLOCK"
    assert payload["source_flag"] == "seeded"
    assert payload["request_id"] == "req_test_123"


def test_hmac_signature_generation_and_tamper_detection():
    """6. HMAC signature & 7. Signature changes when payload changes."""
    secret = "super_secure_webhook_secret_12345"
    payload1 = b'{"event_id": "esc_evt_001", "decision": "BLOCK"}'
    payload2 = b'{"event_id": "esc_evt_001", "decision": "ALLOW"}'

    sig1 = generate_hmac_signature(secret, payload1)
    sig2 = generate_hmac_signature(secret, payload2)

    assert len(sig1) == 64  # SHA-256 hex digest
    assert sig1 != sig2

    # Verification with Python's standard hmac
    expected = hmac.new(secret.encode("utf-8"), payload1, hashlib.sha256).hexdigest()
    assert sig1 == expected


def test_ssrf_and_url_validation():
    """21. Arbitrary URL & 22. SSRF/private destination protections."""
    # Invalid schemes
    ok, err = validate_webhook_url("file:///etc/passwd")
    assert not ok
    assert "Invalid scheme" in err

    ok, err = validate_webhook_url("ftp://server/endpoint")
    assert not ok

    # Cloud metadata endpoints
    ok, err = validate_webhook_url("http://169.254.169.254/latest/meta-data/")
    assert not ok
    assert "metadata" in err

    ok, err = validate_webhook_url("http://metadata.google.internal/computeMetadata/v1/")
    assert not ok

    # Production localhost block
    ok, err = validate_webhook_url("http://localhost:8000/hook", environment="production")
    assert not ok
    assert "Localhost" in err

    # Valid HTTPS endpoint
    ok, err = validate_webhook_url("https://ops.example.com/api/v1/sentinel-webhook")
    assert ok


@patch("requests.post")
def test_successful_webhook_delivery(mock_post, db_session: Session, mock_exception: ExceptionRecord):
    """9. Successful delivery, 16. Audit event creation."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.text = '{"status": "received"}'
    mock_post.return_value = mock_resp

    service = EscalationWebhookService(
        enabled=True,
        webhook_url="https://ops.example.com/alerts",
        webhook_secret="test_secret_key",
        timeout_seconds=5,
    )

    res = service.trigger_escalation(
        session=db_session,
        exception_id=mock_exception.exception_id,
        actor_id="test_runner",
    )

    assert res["success"] is True
    assert res["status"] == "DELIVERED"
    assert res["response_status_code"] == 200
    assert mock_post.called

    # Check HMAC header passed to requests.post
    call_kwargs = mock_post.call_args[1]
    assert "X-Nodal-Sentinel-Signature" in call_kwargs["headers"]
    assert call_kwargs["headers"]["X-Nodal-Sentinel-Signature"].startswith("sha256=")

    # Verify database persistence
    deliv = db_session.query(EscalationWebhookDelivery).filter_by(exception_id=mock_exception.exception_id).first()
    assert deliv is not None
    assert deliv.delivery_status == "DELIVERED"
    assert deliv.delivered_at is not None

    # Verify audit events
    audit_events = db_session.query(AuditEvent).filter_by(exception_id=mock_exception.exception_id).all()
    event_types = [a.event_type for a in audit_events]
    assert "ESCALATION_TRIGGERED" in event_types
    assert "ESCALATION_DELIVERED" in event_types


@patch("requests.post")
def test_idempotent_repeated_trigger(mock_post, db_session: Session, mock_exception: ExceptionRecord):
    """15. Idempotent repeated trigger: duplicate call does not send repeat request."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_post.return_value = mock_resp

    service = EscalationWebhookService(
        enabled=True,
        webhook_url="https://ops.example.com/alerts",
        webhook_secret="test_secret",
    )

    # First call delivers
    res1 = service.trigger_escalation(session=db_session, exception_id=mock_exception.exception_id)
    assert res1["status"] == "DELIVERED"
    assert mock_post.call_count == 1

    # Second call returns ALREADY_DELIVERED without network call
    res2 = service.trigger_escalation(session=db_session, exception_id=mock_exception.exception_id)
    assert res2["status"] == "ALREADY_DELIVERED"
    assert mock_post.call_count == 1


@patch("requests.post")
def test_bounded_retries_and_policy_failure_isolation(mock_post, db_session: Session, mock_exception: ExceptionRecord):
    """14. Bounded retries, 17. Policy decision unchanged after delivery failure (Invariant)."""
    # Simulate connection error
    mock_post.side_effect = requests.exceptions.ConnectionError("Downstream server unreachable")

    service = EscalationWebhookService(
        enabled=True,
        webhook_url="https://ops.example.com/alerts",
        max_retries=3,
        timeout_seconds=2,
    )

    res = service.trigger_escalation(session=db_session, exception_id=mock_exception.exception_id)

    assert res["success"] is False
    assert res["status"] == "FAILED"
    assert res["attempt_count"] == 3  # Bounded to exactly 3 retries
    assert mock_post.call_count == 3

    # CRITICAL INVARIANT: Policy decision must NOT be downgraded or altered
    pol = db_session.query(PolicyDecisionRecord).filter_by(exception_id=mock_exception.exception_id).first()
    assert pol.decision == "BLOCK"
    assert pol.escalation_required is True

    # Exception state must remain unchanged
    exc = db_session.query(ExceptionRecord).filter_by(exception_id=mock_exception.exception_id).first()
    assert exc.state == "FAILED_ESCALATED"


def test_live_injected_case_escalation(db_session: Session):
    """18 & 19. Live-injected exception follows identical path with source_flag = live-injected."""
    now = datetime.now(timezone.utc)
    exc_inj = ExceptionRecord(
        exception_id="EXC_INJ_ESC_001",
        exception_type="GHOST_SETTLEMENT",
        severity="HIGH",
        state="FAILED_ESCALATED",
        exposure=500000,
        primary_payment_id="PAY_INJ_001",
        source_flag="live-injected",
        detected_at=now,
    )
    pol_inj = PolicyDecisionRecord(
        decision_id="POL_INJ_ESC_001",
        exception_id="EXC_INJ_ESC_001",
        requested_action="ESCALATE",
        decision="HUMAN_REVIEW",
        policy_version="v1",
        allowed_actions="[]",
        prohibited_actions="[]",
        escalation_required=True,
        rationale="Live injected ghost settlement",
        risk_score=80,
        priority="P2",
        materiality="MATERIAL",
        exposure=500000,
        created_at=now,
    )
    db_session.add_all([exc_inj, pol_inj])
    db_session.commit()

    service = EscalationWebhookService(enabled=False)
    res = service.trigger_escalation(session=db_session, exception_id=exc_inj.exception_id)

    assert res["status"] == "DISABLED"
    deliv = db_session.query(EscalationWebhookDelivery).filter_by(exception_id=exc_inj.exception_id).first()
    assert deliv.source_flag == "live-injected"


def test_api_escalation_endpoints(client, db_session: Session, mock_exception: ExceptionRecord):
    """API: GET /escalations/config and GET /escalations/deliveries."""
    # Config endpoint (no secrets returned)
    r_cfg = client.get("/escalations/config")
    assert r_cfg.status_code == 200
    cfg = r_cfg.json()
    assert "enabled" in cfg
    assert "configured" in cfg
    assert "destination_url" in cfg
    assert "escalation_webhook_secret" not in cfg

    # Deliveries list
    r_dels = client.get("/escalations/deliveries")
    assert r_dels.status_code == 200
    assert isinstance(r_dels.json(), list)


def test_ask_sentinel_escalation_webhook_tool(db_session: Session):
    """Ask Sentinel invokes get_escalation_status tool and emphasizes policy independence."""
    from backend.copilot.service import AskSentinelService
    service = AskSentinelService()
    res = service.ask(session=db_session, question="What is the status of the escalation webhook?")

    assert "get_escalation_status" in res["tools_used"]
    ans = res["answer"]
    assert "webhook" in ans.lower() or "escalation" in ans.lower()
    assert "policy" in ans.lower()

