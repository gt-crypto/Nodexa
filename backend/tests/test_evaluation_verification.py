"""Unit tests for verification metrics and false closure detection."""
from datetime import datetime, timezone
import pytest

from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.exceptions import ExceptionRecord
from backend.models.enums import ExceptionType, ExceptionState, EvaluationMatchStatus, EvaluationErrorCategory
from backend.evaluation.matcher import CaseMatchResult
from backend.evaluation.verification_metrics import VerificationMetricsCalculator


def utc_now():
    return datetime.now(timezone.utc)


def test_verification_false_closure_detection():
    """Verifies that an exception prematurely closed when expected state is ESCALATED triggers a false closure."""
    gt_escalate = EvaluationGroundTruth(
        case_id="GT-ESC-01",
        anomaly_type=ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value,
        expected_root_cause="rc",
        expected_exposure=50000,
        expected_resolution_class="ESCALATE",
        expected_verification_state="FAILED_ESCALATED",
        created_at=utc_now(),
    )
    pred_false_closed = ExceptionRecord(
        exception_id="exc_fc_01",
        exception_type=ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value,
        exposure=50000,
        state=ExceptionState.VERIFIED_CLOSED.value,  # Dangerous false closure!
        created_at=utc_now(),
    )

    matches = [
        CaseMatchResult(gt_escalate, pred_false_closed, EvaluationMatchStatus.TRUE_POSITIVE, "test"),
    ]

    res = VerificationMetricsCalculator.evaluate_verification(matches, {})
    assert res["total_evaluated"] == 1
    assert res["false_closure_count"] == 1
    assert res["zero_false_closures_verified"] is False
    assert matches[0].is_false_closure is True
    assert EvaluationErrorCategory.FALSE_CLOSURE in matches[0].error_categories
