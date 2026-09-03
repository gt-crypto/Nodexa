"""Comprehensive tests for Prompt 17 - ROI / Business Impact Tile."""
import json
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.main import app
from backend.impact.roi_service import BusinessImpactService
from backend.models.exceptions import ExceptionRecord
from backend.models.financial_sources import GatewayTransaction
from backend.models.cluster import ExceptionCluster
from backend.models.audit import AuditEvent
from backend.models.enums import ExceptionSeverity, ExceptionState
from backend.copilot.service import AskSentinelService


@pytest.fixture
def client():
    return TestClient(app)


def test_business_impact_empty_database(db_session: Session):
    """G. Empty dataset: valid zero-value response without errors."""
    service = BusinessImpactService()
    res = service.calculate_impact(session=db_session, log_audit=False)

    assert res["financial_exposure_identified"] == 0
    assert res["actionable_case_count"] == 0
    assert res["high_risk_case_count"] == 0
    assert res["recurring_pattern_count"] == 0
    assert res["merchants_impacted"] == 0
    assert res["seeded_case_count"] == 0
    assert res["live_injected_case_count"] == 0
    assert res["value_type"] == "POTENTIAL_EXPOSURE_SURFACED"
    assert res["realized_savings"] is None
    assert "not equivalent to recovered savings" in res["disclaimer"]


def test_business_impact_aggregation_and_duplicate_protection(db_session: Session):
    """A. Financial aggregation, B. Duplicate protection, C. Actionable count, D. High-risk count."""
    merchant_id = "mer_impact_test_1"

    # Insert 3 transactions for the same merchant
    t1 = GatewayTransaction(payment_id="PAY_IMP_1", merchant_id=merchant_id, amount=100000, currency="INR", status="CAPTURED", method="UPI")
    t2 = GatewayTransaction(payment_id="PAY_IMP_2", merchant_id=merchant_id, amount=200000, currency="INR", status="CAPTURED", method="UPI")
    t3 = GatewayTransaction(payment_id="PAY_IMP_3", merchant_id="mer_impact_test_2", amount=150000, currency="INR", status="CAPTURED", method="UPI")
    db_session.add_all([t1, t2, t3])

    # Insert 2 exceptions
    e1 = ExceptionRecord(
        exception_id="EXC_IMP_1",
        exception_type="GHOST_SETTLEMENT",
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DETECTED.value,
        exposure=50000,  # ₹500
        primary_payment_id="PAY_IMP_1",
        source_flag="seeded",
    )
    e2 = ExceptionRecord(
        exception_id="EXC_IMP_2",
        exception_type="SETTLEMENT_DELAY",
        severity=ExceptionSeverity.LOW.value,
        state=ExceptionState.DETECTED.value,
        exposure=75000,  # ₹750
        primary_payment_id="PAY_IMP_2",
        source_flag="seeded",
    )
    e3 = ExceptionRecord(
        exception_id="EXC_IMP_3",
        exception_type="DOUBLE_COUNTING",
        severity=ExceptionSeverity.CRITICAL.value,
        state=ExceptionState.DETECTED.value,
        exposure=100000,  # ₹1000
        primary_payment_id="PAY_IMP_3",
        source_flag="live-injected",
    )
    db_session.add_all([e1, e2, e3])
    db_session.commit()

    service = BusinessImpactService()
    res = service.calculate_impact(session=db_session, log_audit=False)

    # Total exposure = 50000 + 75000 + 100000 = 225000 paise (₹2,250)
    assert res["financial_exposure_identified"] == 225000
    assert res["actionable_case_count"] == 3
    # High risk cases = e1 (HIGH) + e3 (CRITICAL) = 2
    assert res["high_risk_case_count"] == 2
    # Merchants impacted = 2 distinct merchants
    assert res["merchants_impacted"] == 2
    # Seeded vs live injected
    assert res["seeded_case_count"] == 2
    assert res["seeded_exposure_identified"] == 125000
    assert res["live_injected_case_count"] == 1
    assert res["live_injected_exposure_identified"] == 100000


def test_business_impact_pattern_integration_no_double_counting(db_session: Session):
    """E. Pattern count, P. Pattern integration (no double counting through overlapping cluster joins)."""
    # 2 exceptions
    e1 = ExceptionRecord(exception_id="EXC_PAT_1", exception_type="GHOST_SETTLEMENT", severity="HIGH", state="DETECTED", exposure=10000, primary_payment_id="P1", source_flag="seeded")
    e2 = ExceptionRecord(exception_id="EXC_PAT_2", exception_type="GHOST_SETTLEMENT", severity="HIGH", state="DETECTED", exposure=20000, primary_payment_id="P2", source_flag="seeded")
    db_session.add_all([e1, e2])

    # 2 clusters that BOTH contain EXC_PAT_1 (overlapping pattern signatures)
    c1 = ExceptionCluster(
        cluster_id="cl_overlap_1",
        cluster_key="k1",
        pattern_type="EXCEPTION_TYPE_CONCENTRATION",
        pattern_label="Ghost Settlements",
        description="Ghost settlements",
        exception_count=2,
        exception_ids=json.dumps(["EXC_PAT_1", "EXC_PAT_2"]),
        merchants=json.dumps(["m1"]),
        total_exposure=30000,
    )
    c2 = ExceptionCluster(
        cluster_id="cl_overlap_2",
        cluster_key="k2",
        pattern_type="HIGH_EXPOSURE_CORRIDOR",
        pattern_label="High Exposure",
        description="High exposure corridor",
        exception_count=2,
        exception_ids=json.dumps(["EXC_PAT_1", "EXC_PAT_2"]),
        merchants=json.dumps(["m1"]),
        total_exposure=30000,
    )
    db_session.add_all([c1, c2])
    db_session.commit()

    service = BusinessImpactService()
    res = service.calculate_impact(session=db_session, log_audit=False)

    assert res["recurring_pattern_count"] == 2
    # Total exposure identified must remain strictly deduplicated: 10000 + 20000 = 30000 (NOT 60000!)
    assert res["financial_exposure_identified"] == 30000
    assert res["pattern_exposure_identified"] == 30000


def test_business_impact_determinism(db_session: Session):
    """K. Determinism: repeated calculation produces identical metrics."""
    service = BusinessImpactService()
    r1 = service.calculate_impact(session=db_session, log_audit=False)
    r2 = service.calculate_impact(session=db_session, log_audit=False)

    for k in [
        "financial_exposure_identified",
        "actionable_case_count",
        "high_risk_case_count",
        "recurring_pattern_count",
        "merchants_impacted",
        "seeded_case_count",
        "live_injected_case_count",
    ]:
        assert r1[k] == r2[k]


def test_business_impact_api_get_roi(client):
    """L. API: GET /impact/roi returns 200 and schema."""
    response = client.get("/impact/roi")
    assert response.status_code == 200
    data = response.json()

    assert "financial_exposure_identified" in data
    assert data["financial_exposure_currency"] == "INR"
    assert "actionable_case_count" in data
    assert "high_risk_case_count" in data
    assert "recurring_pattern_count" in data
    assert "merchants_impacted" in data
    assert "value_type" in data
    assert data["value_type"] == "POTENTIAL_EXPOSURE_SURFACED"
    assert data["realized_savings"] is None
    assert "disclaimer" in data
    assert "methodology" in data


def test_ask_sentinel_business_impact_and_no_fake_savings(db_session: Session):
    """N. Ask Sentinel: uses business-impact tool, cites metrics, does not claim exposure = saved money."""
    # Seed an exception so there is real exposure
    t = GatewayTransaction(payment_id="PAY_ASK_IMP", merchant_id="mer_ask_test", amount=500000, currency="INR", status="CAPTURED", method="UPI")
    e = ExceptionRecord(
        exception_id="EXC_ASK_IMP",
        exception_type="GHOST_SETTLEMENT",
        severity="HIGH",
        state="DETECTED",
        exposure=500000,  # ₹5,000
        primary_payment_id="PAY_ASK_IMP",
        source_flag="seeded",
    )
    db_session.add_all([t, e])
    db_session.commit()

    service = AskSentinelService()

    # Query 1: Business impact inquiry
    res1 = service.ask(session=db_session, question="What business impact has Sentinel demonstrated?")
    assert "get_business_impact" in res1["tools_used"]
    assert not res1["abstained"]
    assert "₹" in res1["answer"]
    assert "actionable" in res1["answer"].lower()

    # Query 2: Money saved inquiry - MUST NOT claim exposure = money saved
    res2 = service.ask(session=db_session, question="How much money did Sentinel save?")
    assert "get_business_impact" in res2["tools_used"]
    ans2 = res2["answer"].lower()
    # Must explicitly state it should not be interpreted as money saved
    assert "not be interpreted as money saved" in ans2 or "not equivalent to recovered savings" in ans2


def test_realized_savings_semantics(client: TestClient, db_session: Session):
    """Validate that realized_savings contract enforces unmeasured state (None) vs fabricated values."""
    response = client.get("/impact/roi")
    assert response.status_code == 200
    data = response.json()
    # Explicitly None (null in JSON) - not fabricated
    assert data["realized_savings"] is None
    # Disclaimer explicitly explains why it is unmeasured
    assert "not equivalent to recovered savings" in data["disclaimer"]
    assert "No post-remediation realized savings are fabricated" in data["disclaimer"]

