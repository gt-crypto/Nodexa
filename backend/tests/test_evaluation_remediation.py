"""Unit tests for remediation outcome evaluation."""
from datetime import datetime, timezone
import pytest

from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.exceptions import ExceptionRecord
from backend.models.remediation import RemediationAction
from backend.models.enums import ExceptionType, RemediationStatus, PolicyActionType, EvaluationMatchStatus
from backend.evaluation.matcher import CaseMatchResult
from backend.evaluation.remediation_metrics import RemediationMetricsCalculator


def utc_now():
    return datetime.now(timezone.utc)


def test_remediation_outcome_evaluation_and_unauthorized_detection():
    """Verifies remediation success rate calculation and unauthorized execution flagging."""
    # 1. Valid executed remediation
    gt1 = EvaluationGroundTruth(
        case_id="GT-01",
        anomaly_type=ExceptionType.GHOST_SETTLEMENT.value,
        expected_root_cause="rc",
        expected_exposure=50000,
        expected_resolution_class="REFUND",
        expected_verification_state="VERIFIED_CLOSED",
        created_at=utc_now(),
    )
    pred1 = ExceptionRecord(
        exception_id="exc_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        exposure=50000,
        created_at=utc_now(),
    )
    rem1 = RemediationAction(
        action_id="act_01",
        exception_id="exc_01",
        action_type=PolicyActionType.REFUND.value,
        status=RemediationStatus.AWAITING_VERIFICATION.value,
        created_at=utc_now(),
    )

    # 2. Legitimate zero-exposure case with unauthorized remediation execution
    gt_legit = EvaluationGroundTruth(
        case_id="GT-LEGIT",
        anomaly_type=ExceptionType.PARTIAL_SETTLEMENT.value,
        expected_root_cause="rc",
        expected_exposure=0,
        expected_resolution_class="OBSERVATION",
        expected_verification_state="DIAGNOSED",
        created_at=utc_now(),
    )
    pred_legit = ExceptionRecord(
        exception_id="exc_legit",
        exception_type=ExceptionType.PARTIAL_SETTLEMENT.value,
        exposure=0,
        created_at=utc_now(),
    )
    rem_unauthorized = RemediationAction(
        action_id="act_bad",
        exception_id="exc_legit",
        action_type=PolicyActionType.REFUND.value,
        status=RemediationStatus.EXECUTED.value,  # Unauthorized!
        created_at=utc_now(),
    )

    matches = [
        CaseMatchResult(gt1, pred1, EvaluationMatchStatus.TRUE_POSITIVE, "test"),
        CaseMatchResult(gt_legit, pred_legit, EvaluationMatchStatus.LEGITIMATE_CORRECT, "test"),
    ]
    actions = {
        "exc_01": rem1,
        "exc_legit": rem_unauthorized,
    }

    res = RemediationMetricsCalculator.evaluate_remediation_outcomes(matches, actions)
    assert res["total_evaluated"] == 2
    assert res["remediation_success_count"] == 1
    assert res["unauthorized_action_count"] == 1
    assert res["remediation_success_rate"] == 0.5
