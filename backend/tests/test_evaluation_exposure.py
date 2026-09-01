"""Unit tests for exposure accuracy in integer paise minor units."""
from datetime import datetime, timezone
import pytest

from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.exceptions import ExceptionRecord
from backend.models.enums import ExceptionType, EvaluationMatchStatus
from backend.evaluation.matcher import CaseMatchResult
from backend.evaluation.exposure_metrics import ExposureMetricsCalculator


def utc_now():
    return datetime.now(timezone.utc)


def test_exposure_exact_match_and_mae_calculation():
    """Verifies integer exposure exact matches, total error accumulation, and MAE."""
    gt1 = EvaluationGroundTruth(
        case_id="GT-01",
        anomaly_type=ExceptionType.GHOST_SETTLEMENT.value,
        expected_root_cause="rc1",
        expected_exposure=100000,  # ₹1000.00
        expected_resolution_class="REFUND",
        expected_verification_state="VERIFIED_CLOSED",
        created_at=utc_now(),
    )
    pred1 = ExceptionRecord(
        exception_id="exc_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        exposure=100000,  # exact match
        created_at=utc_now(),
    )

    gt2 = EvaluationGroundTruth(
        case_id="GT-02",
        anomaly_type=ExceptionType.SETTLEMENT_SLA_BREACH.value,
        expected_root_cause="rc2",
        expected_exposure=50000,  # ₹500.00
        expected_resolution_class="ESCALATE",
        expected_verification_state="FAILED_ESCALATED",
        created_at=utc_now(),
    )
    pred2 = ExceptionRecord(
        exception_id="exc_02",
        exception_type=ExceptionType.SETTLEMENT_SLA_BREACH.value,
        exposure=40000,  # off by 10000 paise (₹100)
        created_at=utc_now(),
    )

    matches = [
        CaseMatchResult(gt1, pred1, EvaluationMatchStatus.TRUE_POSITIVE, "test"),
        CaseMatchResult(gt2, pred2, EvaluationMatchStatus.TRUE_POSITIVE, "test"),
    ]

    summary = ExposureMetricsCalculator.compute_exposure_metrics(matches)
    assert summary.total_evaluated == 2
    assert summary.exact_matches == 1
    assert summary.exact_match_rate == 0.5
    assert summary.exact_match_rate_bps == 5000
    assert summary.total_expected_exposure == 150000
    assert summary.total_predicted_exposure == 140000
    assert summary.total_absolute_error == 10000
    assert summary.max_absolute_error == 10000
    assert summary.mean_absolute_error == 5000.0


def test_zero_exposure_cases_verified():
    """Verifies that legitimate zero exposure cases (0 expected & 0 predicted) pass verification."""
    gt_legit = EvaluationGroundTruth(
        case_id="GT-LEGIT-01",
        anomaly_type=ExceptionType.PARTIAL_SETTLEMENT.value,
        expected_root_cause="Partial settlement under active window",
        expected_exposure=0,
        expected_resolution_class="OBSERVATION",
        expected_verification_state="DIAGNOSED",
        created_at=utc_now(),
    )
    pred_legit = ExceptionRecord(
        exception_id="exc_legit_01",
        exception_type=ExceptionType.PARTIAL_SETTLEMENT.value,
        exposure=0,
        created_at=utc_now(),
    )

    matches = [
        CaseMatchResult(gt_legit, pred_legit, EvaluationMatchStatus.LEGITIMATE_CORRECT, "test"),
    ]

    summary = ExposureMetricsCalculator.compute_exposure_metrics(matches)
    assert summary.total_evaluated == 1
    assert summary.exact_matches == 1
    assert summary.zero_exposure_cases_verified == 1
    assert summary.total_absolute_error == 0
