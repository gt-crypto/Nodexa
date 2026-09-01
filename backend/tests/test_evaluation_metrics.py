"""Unit tests for precision, recall, F1, and category detection metrics."""
import pytest
from backend.models.enums import EvaluationMatchStatus, ExceptionType
from backend.evaluation.matcher import CaseMatchResult
from backend.evaluation.detection_metrics import (
    calculate_precision,
    calculate_recall,
    calculate_f1,
    DetectionMetricsCalculator,
)


def test_metric_formulas_and_zero_denominator_protection():
    """Validates that zero denominators return 0.0 and 0 bps without NaN or ZeroDivisionError."""
    # 0 / 0 case
    prec, prec_bps = calculate_precision(0, 0)
    assert prec == 0.0
    assert prec_bps == 0

    rec, rec_bps = calculate_recall(0, 0)
    assert rec == 0.0
    assert rec_bps == 0

    f1, f1_bps = calculate_f1(0.0, 0.0)
    assert f1 == 0.0
    assert f1_bps == 0

    # Normal case: 8 TP, 2 FP -> Precision = 8/10 = 0.80 (8000 bps)
    prec, prec_bps = calculate_precision(8, 2)
    assert prec == 0.8
    assert prec_bps == 8000

    # Normal case: 8 TP, 2 FN -> Recall = 8/10 = 0.80 (8000 bps)
    rec, rec_bps = calculate_recall(8, 2)
    assert rec == 0.8
    assert rec_bps == 8000

    # F1 = 2 * 0.8 * 0.8 / 1.6 = 0.80 (8000 bps)
    f1, f1_bps = calculate_f1(prec, rec)
    assert f1 == 0.8
    assert f1_bps == 8000


def test_detection_metrics_calculator_overall():
    """Tests overall detection metrics calculation across multiple match results."""
    matches = [
        CaseMatchResult(None, None, EvaluationMatchStatus.TRUE_POSITIVE, "test"),
        CaseMatchResult(None, None, EvaluationMatchStatus.TRUE_POSITIVE, "test"),
        CaseMatchResult(None, None, EvaluationMatchStatus.LEGITIMATE_CORRECT, "test"),
        CaseMatchResult(None, None, EvaluationMatchStatus.FALSE_POSITIVE, "test"),
        CaseMatchResult(None, None, EvaluationMatchStatus.FALSE_NEGATIVE, "test"),
    ]

    metrics = DetectionMetricsCalculator.compute_overall_metrics(matches)
    assert metrics["true_positives"] == 3  # 2 TP + 1 LEGITIMATE_CORRECT
    assert metrics["false_positives"] == 1
    assert metrics["false_negatives"] == 1
    assert metrics["total_evaluated"] == 5

    # Precision = 3 / (3 + 1) = 0.75 (7500 bps)
    assert metrics["precision"] == 0.75
    assert metrics["precision_bps"] == 7500

    # Recall = 3 / (3 + 1) = 0.75 (7500 bps)
    assert metrics["recall"] == 0.75
    assert metrics["recall_bps"] == 7500

    # F1 = 0.75 (7500 bps)
    assert metrics["f1_score"] == 0.75
    assert metrics["f1_score_bps"] == 7500
