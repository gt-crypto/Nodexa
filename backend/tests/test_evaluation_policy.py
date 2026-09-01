"""Unit tests for policy decision evaluation metrics."""
from datetime import datetime, timezone
import pytest

from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.exceptions import ExceptionRecord
from backend.models.policy import PolicyDecisionRecord
from backend.models.enums import (
    ExceptionType,
    PolicyDecisionType,
    PolicyActionType,
    EvaluationMatchStatus,
)
from backend.evaluation.matcher import CaseMatchResult
from backend.evaluation.policy_metrics import PolicyMetricsCalculator


def utc_now():
    return datetime.now(timezone.utc)


def test_policy_decision_evaluation():
    """Verifies policy accuracy scoring for compliant vs non-compliant decisions."""
    gt_ghost = EvaluationGroundTruth(
        case_id="GT-GHOST-01",
        anomaly_type=ExceptionType.GHOST_SETTLEMENT.value,
        expected_root_cause="rc",
        expected_exposure=50000,
        expected_resolution_class="REFUND",
        expected_verification_state="VERIFIED_CLOSED",
        created_at=utc_now(),
    )
    pred_ghost = ExceptionRecord(
        exception_id="exc_ghost_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        exposure=50000,
        created_at=utc_now(),
    )
    policy_ghost = PolicyDecisionRecord(
        decision_id="pol_01",
        exception_id="exc_ghost_01",
        requested_action=PolicyActionType.REFUND.value,
        decision=PolicyDecisionType.REQUIRE_APPROVAL.value,
        allowed_actions="[\"REFUND\"]",
        prohibited_actions="[]",
        rationale="Approval required for refund",
        created_at=utc_now(),
    )

    matches = [
        CaseMatchResult(gt_ghost, pred_ghost, EvaluationMatchStatus.TRUE_POSITIVE, "test"),
    ]
    decisions = {"exc_ghost_01": policy_ghost}

    res = PolicyMetricsCalculator.evaluate_policy_decisions(matches, decisions)
    assert res["total_evaluated"] == 1
    assert res["policy_correct"] == 1
    assert res["policy_incorrect"] == 0
    assert res["policy_accuracy"] == 1.0
