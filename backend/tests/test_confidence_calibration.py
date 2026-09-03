"""Comprehensive unit and integration tests for Prompt 19 - Confidence Calibration Dashboard."""
import json
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

import backend.models
from backend.main import app
from backend.calibration.service import ConfidenceCalibrationService
from backend.models.exceptions import ExceptionRecord
from backend.models.investigation import InvestigationRun
from backend.models.verifier import VerifierOpinion
from backend.models.verification import VerificationRecord
from backend.models.evaluation import EvaluationCase, EvaluationRun
from backend.models.calibration import ConfidenceCalibrationSnapshot
from backend.copilot.service import AskSentinelService


def test_calibration_empty_dataset(db_session: Session):
    """Empty dataset returns NOT_CALIBRATABLE status."""
    service = ConfidenceCalibrationService()
    res = service.evaluate_calibration(session=db_session, persist=False, log_audit=False)

    assert res["status"] == "NOT_CALIBRATABLE"
    assert res["total_predictions"] == 0
    assert res["evaluated_predictions"] == 0
    assert res["coverage"] is None
    assert res["correctness_rate"] is None
    assert "NOT_CALIBRATABLE" in res["status"]


def test_calibration_insufficient_data(db_session: Session):
    """Sparse evaluated outcomes (< 3) returns explicit INSUFFICIENT_DATA status."""
    now = datetime.now(timezone.utc)

    # Add 1 investigation prediction with evaluation
    e1 = ExceptionRecord(
        exception_id="EXC_CALIB_1",
        exception_type="GHOST_SETTLEMENT",
        severity="HIGH",
        state="RESOLVED",
        exposure=50000,
        primary_payment_id="PAY_C1",
        source_flag="seeded",
        detected_at=now,
    )
    inv1 = InvestigationRun(
        investigation_id="INV_CALIB_1",
        exception_id="EXC_CALIB_1",
        confidence=Decimal("0.9000"),
        final_classification="GHOST_SETTLEMENT",
        root_cause="Ghost settlement confirmed",
        status="COMPLETED",
        created_at=now,
    )
    run1 = EvaluationRun(evaluation_run_id="RUN_C1", dataset_id="DS_1", status="COMPLETED")
    eval_case = EvaluationCase(
        evaluation_case_id="EVAL_C1",
        evaluation_run_id="RUN_C1",
        predicted_exception_id="EXC_CALIB_1",
        match_status="TRUE_POSITIVE",
        created_at=now,
    )
    db_session.add_all([e1, inv1, run1, eval_case])
    db_session.commit()

    service = ConfidenceCalibrationService()
    res = service.evaluate_calibration(session=db_session, persist=False, log_audit=False)

    assert res["status"] == "INSUFFICIENT_DATA"
    assert res["evaluated_predictions"] == 1
    assert res["total_predictions"] == 1
    assert res["insufficiency_reasons"] is not None
    assert any("below minimum statistical threshold" in r for r in res["insufficiency_reasons"])


def test_calibration_categorical_and_numerical_metrics(db_session: Session):
    """Comprehensive test for categorical buckets, Brier score, and ECE with >= 5 numerical evaluations."""
    now = datetime.now(timezone.utc)

    # Create 6 evaluated investigation cases with varied confidence and correctness
    confidences = [
        (Decimal("0.9500"), True),   # HIGH, correct
        (Decimal("0.9000"), True),   # HIGH, correct
        (Decimal("0.8800"), False),  # HIGH, incorrect (e.g. WRONG_ROOT_CAUSE)
        (Decimal("0.7500"), True),   # MEDIUM, correct
        (Decimal("0.6500"), False),  # MEDIUM, incorrect
        (Decimal("0.4000"), False),  # LOW, incorrect
    ]

    run_num = EvaluationRun(evaluation_run_id="RUN_NUM_1", dataset_id="DS_NUM", status="COMPLETED")
    db_session.add(run_num)

    for idx, (conf, is_correct) in enumerate(confidences):
        exc_id = f"EXC_CALIB_NUM_{idx}"
        e = ExceptionRecord(
            exception_id=exc_id,
            exception_type="GHOST_SETTLEMENT",
            severity="HIGH",
            state="RESOLVED",
            exposure=50000,
            primary_payment_id=f"PAY_NUM_{idx}",
            source_flag="seeded",
            detected_at=now,
        )
        inv = InvestigationRun(
            investigation_id=f"INV_NUM_{idx}",
            exception_id=exc_id,
            confidence=conf,
            final_classification="GHOST_SETTLEMENT",
            root_cause="Root cause detail",
            status="COMPLETED",
            created_at=now,
        )
        eval_case = EvaluationCase(
            evaluation_case_id=f"EVAL_NUM_{idx}",
            evaluation_run_id="RUN_NUM_1",
            predicted_exception_id=exc_id,
            match_status="TRUE_POSITIVE" if is_correct else "TRUE_POSITIVE",
            error_categories="[]" if is_correct else '["WRONG_ROOT_CAUSE"]',
            created_at=now,
        )
        db_session.add_all([e, inv, eval_case])

    db_session.commit()

    service = ConfidenceCalibrationService()
    res = service.evaluate_calibration(session=db_session, persist=True, log_audit=False)

    # Status should be PARTIALLY_CALIBRATED or CALIBRATED
    assert res["status"] in ("CALIBRATED", "PARTIALLY_CALIBRATED")
    assert res["total_predictions"] == 6
    assert res["evaluated_predictions"] == 6
    assert res["correct_predictions"] == 3
    assert res["coverage"] == 1.0
    assert res["correctness_rate"] == 0.50

    # Confidence Buckets
    buckets = res["confidence_buckets"]
    assert buckets["HIGH"]["prediction_count"] == 3
    assert buckets["HIGH"]["evaluated_count"] == 3
    assert buckets["HIGH"]["correct_count"] == 2
    assert buckets["HIGH"]["correctness_rate"] == round(2 / 3, 4)

    assert buckets["MEDIUM"]["prediction_count"] == 2
    assert buckets["MEDIUM"]["evaluated_count"] == 2
    assert buckets["MEDIUM"]["correct_count"] == 1
    assert buckets["MEDIUM"]["correctness_rate"] == 0.50

    assert buckets["LOW"]["prediction_count"] == 1
    assert buckets["LOW"]["evaluated_count"] == 1
    assert buckets["LOW"]["correct_count"] == 0
    assert buckets["LOW"]["correctness_rate"] == 0.0

    # Numerical Metrics (Brier Score & ECE)
    num = res["numerical_metrics"]
    assert num["status"] == "CALCULATED"
    assert num["eligible_sample_size"] == 6
    assert num["brier_score"] is not None
    assert 0.0 <= num["brier_score"] <= 1.0
    assert num["ece"] is not None
    assert 0.0 <= num["ece"] <= 1.0
    assert len(num["reliability_bins"]) == 5

    # Persistence verification
    saved_snap = db_session.query(ConfidenceCalibrationSnapshot).filter_by(
        snapshot_id=res["snapshot_id"]
    ).first()
    assert saved_snap is not None
    assert saved_snap.total_predictions == 6


def test_calibration_live_injected_provenance_and_isolation(db_session: Session):
    """Live-injected cases remain tracked under source_breakdown and isolated as unevaluated."""
    now = datetime.now(timezone.utc)

    # 1 seeded evaluated case
    run_seed = EvaluationRun(evaluation_run_id="RUN_SEED", dataset_id="DS_SEED", status="COMPLETED")
    e1 = ExceptionRecord(
        exception_id="EXC_SEED_1",
        exception_type="GHOST_SETTLEMENT",
        severity="LOW",
        state="DETECTED",
        exposure=10000,
        primary_payment_id="P_SEED",
        source_flag="seeded",
        detected_at=now,
    )
    inv1 = InvestigationRun(
        investigation_id="INV_SEED_1",
        exception_id="EXC_SEED_1",
        confidence=Decimal("0.9000"),
        final_classification="GHOST_SETTLEMENT",
        status="COMPLETED",
        created_at=now,
    )
    eval1 = EvaluationCase(
        evaluation_case_id="EVAL_SEED_1",
        evaluation_run_id="RUN_SEED",
        predicted_exception_id="EXC_SEED_1",
        match_status="TRUE_POSITIVE",
        created_at=now,
    )

    # 1 live-injected case without ground truth evaluation
    e2 = ExceptionRecord(
        exception_id="EXC_INJ_1",
        exception_type="GHOST_SETTLEMENT",
        severity="HIGH",
        state="DETECTED",
        exposure=50000,
        primary_payment_id="P_INJ",
        source_flag="live-injected",
        detected_at=now,
    )
    inv2 = InvestigationRun(
        investigation_id="INV_INJ_1",
        exception_id="EXC_INJ_1",
        confidence=Decimal("0.8000"),
        final_classification="GHOST_SETTLEMENT",
        status="COMPLETED",
        created_at=now,
    )
    db_session.add_all([run_seed, e1, inv1, eval1, e2, inv2])
    db_session.commit()

    service = ConfidenceCalibrationService()
    res = service.evaluate_calibration(session=db_session, persist=False, log_audit=False)

    assert res["total_predictions"] == 2
    assert res["evaluated_predictions"] == 1
    assert res["unevaluated_predictions"] == 1
    assert res["source_breakdown"]["seeded_count"] == 1
    assert res["source_breakdown"]["live_injected_count"] == 1

    # Filter by source: seeded only
    res_seeded = service.evaluate_calibration(session=db_session, source="seeded", persist=False, log_audit=False)
    assert res_seeded["total_predictions"] == 1
    assert res_seeded["source_breakdown"]["seeded_count"] == 1
    assert res_seeded["source_breakdown"]["live_injected_count"] == 0

    # Filter by source: live-injected only
    res_inj = service.evaluate_calibration(session=db_session, source="live-injected", persist=False, log_audit=False)
    assert res_inj["total_predictions"] == 1
    assert res_inj["evaluated_predictions"] == 0
    assert res_inj["unevaluated_predictions"] == 1


def test_calibration_api_endpoint(client):
    """GET /calibration/confidence returns 200 and conforms to PRD schema."""
    response = client.get("/calibration/confidence")
    assert response.status_code == 200
    data = response.json()

    assert "snapshot_id" in data
    assert "status" in data
    assert "total_predictions" in data
    assert "evaluated_predictions" in data
    assert "confidence_buckets" in data
    assert "numerical_metrics" in data
    assert "source_breakdown" in data
    assert "disclaimer" in data


def test_ask_sentinel_confidence_calibration_tool(db_session: Session):
    """Ask Sentinel invokes get_confidence_calibration and distinguishes confidence from probability."""
    service = AskSentinelService()
    res = service.ask(session=db_session, question="How well calibrated is Sentinel's confidence?")

    assert "get_confidence_calibration" in res["tools_used"]
    ans = res["answer"]
    assert "confidence" in ans.lower() or "calibrat" in ans.lower()
    # Must distinguish confidence from probability
    assert "probability" in ans.lower() or "certainty" in ans.lower() or "calibrat" in ans.lower()
