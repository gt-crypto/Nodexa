"""Detection performance metrics engine for precision, recall, F1, and category breakdowns."""
from typing import Any, Dict, List, Tuple
from backend.models.enums import EvaluationMatchStatus, ExceptionType
from backend.evaluation.matcher import CaseMatchResult
from backend.evaluation.models import EvaluationMetricDetail

TupleMetric = Tuple[float, int]


def calculate_precision(tp: int, fp: int) -> TupleMetric:
    """Calculates precision float and integer basis points with 0 denominator protection."""
    total = tp + fp
    if total == 0:
        return 0.0, 0
    prec = tp / total
    prec_bps = (tp * 10000) // total
    return prec, prec_bps


def calculate_recall(tp: int, fn: int) -> TupleMetric:
    """Calculates recall float and integer basis points with 0 denominator protection."""
    total = tp + fn
    if total == 0:
        return 0.0, 0
    rec = tp / total
    rec_bps = (tp * 10000) // total
    return rec, rec_bps


def calculate_f1(precision: float, recall: float) -> TupleMetric:
    """Calculates F1 float and integer basis points with 0 denominator protection."""
    denom = precision + recall
    if denom == 0.0:
        return 0.0, 0
    f1 = round((2.0 * precision * recall) / denom, 6)
    f1_bps = int(f1 * 10000)
    return f1, f1_bps


class DetectionMetricsCalculator:
    """Computes overall and per-type detection accuracy metrics."""

    @staticmethod
    def compute_overall_metrics(match_results: List[CaseMatchResult]) -> Dict[str, Any]:
        """Calculates global TP, FP, FN, Precision, Recall, and F1 across all evaluated cases."""
        tp = sum(
            1 for m in match_results
            if m.match_status in (EvaluationMatchStatus.TRUE_POSITIVE, EvaluationMatchStatus.LEGITIMATE_CORRECT)
        )
        fp = sum(
            1 for m in match_results
            if m.match_status in (
                EvaluationMatchStatus.FALSE_POSITIVE,
                EvaluationMatchStatus.LEGITIMATE_FALSE_POSITIVE,
                EvaluationMatchStatus.TYPE_MISMATCH,
            )
        )
        fn = sum(
            1 for m in match_results
            if m.match_status == EvaluationMatchStatus.FALSE_NEGATIVE
        )

        prec, prec_bps = calculate_precision(tp, fp)
        rec, rec_bps = calculate_recall(tp, fn)
        f1, f1_bps = calculate_f1(prec, rec)

        return {
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "total_evaluated": len(match_results),
            "precision": prec,
            "precision_bps": prec_bps,
            "recall": rec,
            "recall_bps": rec_bps,
            "f1_score": f1,
            "f1_score_bps": f1_bps,
        }

    @staticmethod
    def compute_type_breakdown(match_results: List[CaseMatchResult]) -> Dict[str, EvaluationMetricDetail]:
        """Calculates per-anomaly-type precision, recall, and F1."""
        categories = [
            ExceptionType.GHOST_SETTLEMENT.value,
            ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value,
            ExceptionType.SETTLEMENT_SLA_BREACH.value,
            ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value,
            ExceptionType.PARTIAL_SETTLEMENT.value,
            ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value,
        ]

        breakdown: Dict[str, EvaluationMetricDetail] = {}

        for cat in categories:
            # Expected items in this category
            expected_cases = [
                m for m in match_results
                if m.ground_truth and m.ground_truth.anomaly_type == cat
            ]
            # Predicted items in this category
            predicted_cases = [
                m for m in match_results
                if m.prediction and m.prediction.exception_type == cat
            ]

            tp = sum(
                1 for m in match_results
                if m.ground_truth and m.ground_truth.anomaly_type == cat
                and m.prediction and m.prediction.exception_type == cat
            )
            fp = sum(
                1 for m in match_results
                if m.prediction and m.prediction.exception_type == cat
                and (not m.ground_truth or m.ground_truth.anomaly_type != cat)
            )
            fn = sum(
                1 for m in match_results
                if m.ground_truth and m.ground_truth.anomaly_type == cat
                and (not m.prediction or m.prediction.exception_type != cat)
            )

            prec, prec_bps = calculate_precision(tp, fp)
            rec, rec_bps = calculate_recall(tp, fn)
            f1, f1_bps = calculate_f1(prec, rec)

            breakdown[cat] = EvaluationMetricDetail(
                name=cat,
                expected_count=len(expected_cases),
                predicted_count=len(predicted_cases),
                true_positives=tp,
                false_positives=fp,
                false_negatives=fn,
                precision=prec,
                precision_bps=prec_bps,
                recall=rec,
                recall_bps=rec_bps,
                f1_score=f1,
                f1_score_bps=f1_bps,
            )

        return breakdown

    @staticmethod
    def compute_legitimate_case_metrics(match_results: List[CaseMatchResult]) -> Dict[str, Any]:
        """Evaluates legitimate observation handling (PARTIAL_SETTLEMENT and LEGITIMATE_TIMING_EXCEPTION)."""
        legit_results = [
            m for m in match_results
            if m.ground_truth and m.ground_truth.anomaly_type in (
                ExceptionType.PARTIAL_SETTLEMENT.value,
                ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value,
            )
        ]

        total_legit = len(legit_results)
        legit_correct = sum(
            1 for m in legit_results
            if m.match_status == EvaluationMatchStatus.LEGITIMATE_CORRECT
            and m.prediction and m.prediction.exposure == 0
        )
        legit_fp = sum(
            1 for m in legit_results
            if m.prediction and m.prediction.exposure > 0
        )

        fp_rate = (legit_fp / total_legit) if total_legit > 0 else 0.0

        return {
            "total_legitimate_cases": total_legit,
            "legitimate_correct_count": legit_correct,
            "legitimate_false_positive_count": legit_fp,
            "legitimate_false_positive_rate": fp_rate,
            "all_zero_exposure_verified": (legit_fp == 0),
        }

    @staticmethod
    def compute_normal_case_metrics(
        total_records: int,
        match_results: List[CaseMatchResult],
    ) -> Dict[str, Any]:
        """Calculates false positive rates on normal, non-anomalous operational transactions."""
        gt_count = sum(1 for m in match_results if m.ground_truth is not None)
        normal_count = max(0, total_records - gt_count)

        unmatched_fp = sum(
            1 for m in match_results
            if m.match_status in (
                EvaluationMatchStatus.FALSE_POSITIVE,
                EvaluationMatchStatus.LEGITIMATE_FALSE_POSITIVE,
            )
            and m.ground_truth is None
        )

        fp_rate = (unmatched_fp / normal_count) if normal_count > 0 else 0.0

        return {
            "normal_case_count": normal_count,
            "normal_false_positive_count": unmatched_fp,
            "normal_false_positive_rate": fp_rate,
            "zero_normal_false_positives_verified": (unmatched_fp == 0),
        }
