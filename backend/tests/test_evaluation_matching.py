"""Unit tests for deterministic hierarchical matching in benchmark evaluation."""
from datetime import datetime, timezone
import pytest

from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.exceptions import ExceptionRecord
from backend.models.enums import ExceptionType, EvaluationMatchStatus
from backend.evaluation.matcher import DeterministicMatcher


def utc_now():
    return datetime.now(timezone.utc)


def test_deterministic_matcher_exact_type_and_sequence():
    """Verifies pairing of ground truth cases and predictions by type and order."""
    gt1 = EvaluationGroundTruth(
        case_id="CASE-GHOST-0001",
        anomaly_type=ExceptionType.GHOST_SETTLEMENT.value,
        expected_root_cause="Ghost settlement without payment",
        expected_exposure=50000,
        expected_resolution_class="REFUND",
        expected_verification_state="VERIFIED_CLOSED",
        created_at=utc_now(),
    )
    gt2 = EvaluationGroundTruth(
        case_id="CASE-GHOST-0002",
        anomaly_type=ExceptionType.GHOST_SETTLEMENT.value,
        expected_root_cause="Ghost settlement duplicate credit",
        expected_exposure=75000,
        expected_resolution_class="REFUND",
        expected_verification_state="VERIFIED_CLOSED",
        created_at=utc_now(),
    )

    pred1 = ExceptionRecord(
        exception_id="exc_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        primary_payment_id="PAY-000001",
        exposure=50000,
        created_at=utc_now(),
    )
    pred2 = ExceptionRecord(
        exception_id="exc_02",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        primary_payment_id="PAY-000002",
        exposure=75000,
        created_at=utc_now(),
    )

    results = DeterministicMatcher.match_all([gt1, gt2], [pred1, pred2])
    assert len(results) == 2
    assert results[0].match_status == EvaluationMatchStatus.TRUE_POSITIVE
    assert results[0].ground_truth.case_id == "CASE-GHOST-0001"
    assert results[0].prediction.exception_id == "exc_01"

    assert results[1].match_status == EvaluationMatchStatus.TRUE_POSITIVE
    assert results[1].ground_truth.case_id == "CASE-GHOST-0002"
    assert results[1].prediction.exception_id == "exc_02"


def test_deterministic_matcher_false_positive_and_false_negative():
    """Verifies detection of unmatched ground truth cases (FN) and spurious exceptions (FP)."""
    gt_missed = EvaluationGroundTruth(
        case_id="CASE-SLABREACH-0001",
        anomaly_type=ExceptionType.SETTLEMENT_SLA_BREACH.value,
        expected_root_cause="SLA breached",
        expected_exposure=120000,
        expected_resolution_class="ESCALATE",
        expected_verification_state="FAILED_ESCALATED",
        created_at=utc_now(),
    )

    pred_spurious = ExceptionRecord(
        exception_id="exc_spurious_01",
        exception_type=ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value,
        primary_payment_id="PAY-NORMAL-999",
        exposure=30000,
        created_at=utc_now(),
    )

    results = DeterministicMatcher.match_all([gt_missed], [pred_spurious])
    assert len(results) == 2

    # One false negative (ground truth was missed)
    fn_matches = [r for r in results if r.match_status == EvaluationMatchStatus.FALSE_NEGATIVE]
    assert len(fn_matches) == 1
    assert fn_matches[0].ground_truth.case_id == "CASE-SLABREACH-0001"

    # One false positive (spurious exception reported)
    fp_matches = [r for r in results if r.match_status == EvaluationMatchStatus.FALSE_POSITIVE]
    assert len(fp_matches) == 1
    assert fp_matches[0].prediction.exception_id == "exc_spurious_01"
