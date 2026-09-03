"""Comprehensive unit and integration tests for Prompt 18 - Predictive Nodal Drift Radar."""
import json
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from backend.main import app
from backend.predictions.drift_service import PredictiveDriftService
from backend.models.exceptions import ExceptionRecord
from backend.models.cluster import ExceptionCluster
from backend.models.drift_prediction import DriftPrediction
from backend.models.enums import ExceptionSeverity, ExceptionState
from backend.copilot.service import AskSentinelService
import backend.models


def test_drift_insufficient_data(db_session: Session):
    """E. Insufficient data: sparse history (<2 records) produces explicit insufficient-data state."""
    service = PredictiveDriftService()
    res = service.evaluate_drift(session=db_session, nodal_account_id="nodal_escrow_main", persist=False, log_audit=False)

    assert res["direction"] == "INSUFFICIENT_DATA"
    assert res["confidence"] == "LOW"
    assert res["drift_score"] == 0
    assert res["risk_band"] == "STABLE"
    assert "INSUFFICIENT DATA" in res["disclaimer"]


def test_drift_score_bounds_and_contributions(db_session: Session):
    """A. Determinism, B. Score bounds, F. Baseline/current, H. Signal contributions, M. Persistence."""
    now = datetime.now(timezone.utc)
    t_base = now - timedelta(hours=48)
    t_curr = now - timedelta(hours=12)

    # 2 exceptions in baseline (low severity, small exposure)
    e1 = ExceptionRecord(
        exception_id="EXC_DRIFT_B1",
        exception_type="GHOST_SETTLEMENT",
        severity=ExceptionSeverity.LOW.value,
        state=ExceptionState.DETECTED.value,
        exposure=5000,
        primary_payment_id="PAY_B1",
        source_flag="seeded",
        detected_at=t_base,
    )
    e2 = ExceptionRecord(
        exception_id="EXC_DRIFT_B2",
        exception_type="SETTLEMENT_DELAY",
        severity=ExceptionSeverity.LOW.value,
        state=ExceptionState.DETECTED.value,
        exposure=5000,
        primary_payment_id="PAY_B2",
        source_flag="seeded",
        detected_at=t_base + timedelta(hours=1),
    )

    # 6 exceptions in current window (high severity, large exposure, SLA breaches)
    current_excs = []
    for i in range(6):
        current_excs.append(
            ExceptionRecord(
                exception_id=f"EXC_DRIFT_C{i}",
                exception_type="SETTLEMENT_SLA_BREACH" if i % 2 == 0 else "GHOST_SETTLEMENT",
                severity=ExceptionSeverity.HIGH.value if i >= 2 else ExceptionSeverity.CRITICAL.value,
                state=ExceptionState.DETECTED.value,
                exposure=200000,  # ₹2,000 each
                primary_payment_id=f"PAY_C{i}",
                source_flag="seeded",
                detected_at=t_curr + timedelta(hours=i),
            )
        )

    db_session.add_all([e1, e2] + current_excs)
    db_session.commit()

    service = PredictiveDriftService()
    res1 = service.evaluate_drift(session=db_session, nodal_account_id="nodal_escrow_main", persist=True, log_audit=False)

    # Score bounds
    assert 0 <= res1["drift_score"] <= 100
    assert res1["drift_score"] > 0
    assert res1["direction"] == "DETERIORATING"
    assert res1["risk_band"] in ("WATCH", "ELEVATED", "HIGH_DRIFT")

    # Verify baseline and current metrics
    assert res1["baseline_metrics"]["exception_count"] == 2
    assert res1["current_metrics"]["exception_count"] == 6
    assert res1["delta_metrics"]["delta_exceptions"] == 4

    # Verify persistence
    saved_pred = db_session.query(DriftPrediction).filter_by(prediction_id=res1["prediction_id"]).first()
    assert saved_pred is not None
    assert saved_pred.drift_score == res1["drift_score"]

    # Test determinism on repeat call (idempotent)
    res2 = service.evaluate_drift(session=db_session, nodal_account_id="nodal_escrow_main", persist=True, log_audit=False)
    assert res1["drift_score"] == res2["drift_score"]
    assert res1["risk_band"] == res2["risk_band"]
    assert res1["direction"] == res2["direction"]


def test_drift_live_injection_provenance(db_session: Session):
    """J. Live-injection: synthetic case flows through normal data, provenance preserved."""
    now = datetime.now(timezone.utc)
    t_base = now - timedelta(hours=36)
    t_curr = now - timedelta(hours=2)

    e1 = ExceptionRecord(
        exception_id="EXC_BASE_1",
        exception_type="GHOST_SETTLEMENT",
        severity=ExceptionSeverity.LOW.value,
        state=ExceptionState.DETECTED.value,
        exposure=10000,
        primary_payment_id="PAY_B1",
        source_flag="seeded",
        detected_at=t_base,
    )
    e2 = ExceptionRecord(
        exception_id="EXC_INJ_1",
        exception_type="GHOST_SETTLEMENT",
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DETECTED.value,
        exposure=50000,
        primary_payment_id="PAY_INJ_1",
        source_flag="live-injected",
        detected_at=t_curr,
    )
    db_session.add_all([e1, e2])
    db_session.commit()

    service = PredictiveDriftService()
    res = service.evaluate_drift(session=db_session, nodal_account_id="nodal_escrow_main", persist=False, log_audit=False)

    assert res["source"]["seeded_count"] == 1
    assert res["source"]["live_injected_count"] == 1
    assert res["source"]["synthetic_included"] is True


def test_drift_api_get_drift(client):
    """N. API: GET /predictions/drift returns 200 and schema."""
    response = client.get("/predictions/drift?nodal_account_id=nodal_escrow_main")
    assert response.status_code == 200
    data = response.json()

    assert "prediction_id" in data
    assert "nodal_account_id" in data
    assert "drift_score" in data
    assert "risk_band" in data
    assert "direction" in data
    assert "confidence" in data
    assert "signals" in data
    assert "observation_window" in data
    assert "disclaimer" in data


def test_ask_sentinel_drift_tool_and_grounding(db_session: Session):
    """O. Ask Sentinel: uses structured drift tool, distinguishes prediction from fact."""
    now = datetime.now(timezone.utc)
    t_base = now - timedelta(hours=24)
    t_curr = now - timedelta(hours=1)

    e1 = ExceptionRecord(exception_id="EXC_ASK_D1", exception_type="GHOST_SETTLEMENT", severity="LOW", state="DETECTED", exposure=10000, primary_payment_id="P1", source_flag="seeded", detected_at=t_base)
    e2 = ExceptionRecord(exception_id="EXC_ASK_D2", exception_type="GHOST_SETTLEMENT", severity="HIGH", state="DETECTED", exposure=50000, primary_payment_id="P2", source_flag="seeded", detected_at=t_curr)
    db_session.add_all([e1, e2])
    db_session.commit()

    service = AskSentinelService()
    res = service.ask(session=db_session, question="Is nodal health deteriorating?")

    assert "get_drift_prediction" in res["tools_used"]
    assert not res["abstained"]
    ans = res["answer"]
    assert "Drift Score" in ans or "drift" in ans.lower()
    # Must distinguish prediction from absolute certainty
    assert "early-warning" in ans.lower() or "prediction" in ans.lower() or "signals" in ans.lower()
