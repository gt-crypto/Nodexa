"""Unit tests for severity and priority accuracy and confusion matrices."""
from datetime import datetime, timezone
import pytest

from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.exceptions import ExceptionRecord
from backend.models.risk import RiskAssessment
from backend.models.enums import ExceptionType, ExceptionSeverity, PriorityLevel, EvaluationMatchStatus
from backend.evaluation.matcher import CaseMatchResult
from backend.evaluation.risk_metrics import RiskMetricsCalculator


def utc_now():
    return datetime.now(timezone.utc)


def test_severity_and_priority_accuracy_and_confusion_matrix():
    """Verifies severity and priority accuracy scoring and confusion matrix generation."""
    gt1 = EvaluationGroundTruth(
        case_id="GT-01",
        anomaly_type=ExceptionType.GHOST_SETTLEMENT.value,  # Expected: HIGH, P1
        expected_root_cause="rc",
        expected_exposure=50000,
        expected_resolution_class="REFUND",
        expected_verification_state="VERIFIED_CLOSED",
        created_at=utc_now(),
    )
    pred1 = ExceptionRecord(
        exception_id="exc_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        created_at=utc_now(),
    )
    ra1 = RiskAssessment(
        assessment_id="ra_01",
        exception_id="exc_01",
        deterministic_exposure=50000,
        currency="INR",
        exposure_type="UNSETTLED_FUNDS",
        gross_exposure=50000,
        net_exposure=50000,
        materiality="HIGH",
        risk_score=90,
        priority=PriorityLevel.P1.value,
        escalation="NONE",
        explanation="High risk exception",
        created_at=utc_now(),
    )

    matches = [
        CaseMatchResult(gt1, pred1, EvaluationMatchStatus.TRUE_POSITIVE, "test"),
    ]
    assessments = {"exc_01": ra1}

    res = RiskMetricsCalculator.evaluate_severity_and_priority(matches, assessments)
    assert res["total_evaluated"] == 1
    assert res["severity_accuracy"] == 1.0
    assert res["priority_accuracy"] == 1.0

    sev_cm = res["severity_confusion_matrix"]
    assert len(sev_cm) == 1
    assert sev_cm[0].expected_class == "HIGH"
    assert sev_cm[0].predicted_class == "HIGH"
    assert sev_cm[0].count == 1
