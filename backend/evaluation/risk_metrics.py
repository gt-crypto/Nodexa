"""Risk metrics engine evaluating severity and priority classification accuracy."""
from typing import Any, Dict, List
from backend.evaluation.matcher import CaseMatchResult
from backend.evaluation.models import ConfusionMatrixItem
from backend.models.enums import EvaluationErrorCategory, ExceptionSeverity, PriorityLevel


class RiskMetricsCalculator:
    """Computes exact accuracy and multi-class confusion matrices for Severity and Priority levels."""

    @staticmethod
    def evaluate_severity_and_priority(
        match_results: List[CaseMatchResult],
        risk_assessments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compares expected severity and risk priority against operational determinations.
        
        Args:
            match_results: Matched pairs.
            risk_assessments: Map of exception_id -> RiskAssessment object.
        """
        total_eval = 0
        sev_correct = 0
        pri_correct = 0

        sev_matrix: Dict[str, Dict[str, int]] = {
            s.value: {s2.value: 0 for s2 in ExceptionSeverity} for s in ExceptionSeverity
        }
        pri_matrix: Dict[str, Dict[str, int]] = {
            p.value: {p2.value: 0 for p2 in PriorityLevel} for p in PriorityLevel
        }

        for m in match_results:
            if not m.ground_truth:
                continue

            total_eval += 1
            exp_sev = DeterministicExpectedMapper.get_expected_severity(m.ground_truth.anomaly_type)
            exp_pri = DeterministicExpectedMapper.get_expected_priority(m.ground_truth.anomaly_type)

            pred_sev = m.prediction.severity if m.prediction else "UNKNOWN"
            pred_pri = "UNKNOWN"

            if m.prediction and m.prediction.exception_id in risk_assessments:
                ra = risk_assessments[m.prediction.exception_id]
                pred_pri = getattr(ra, "priority", getattr(ra, "priority_level", "UNKNOWN")) or "UNKNOWN"

            # Severity comparison
            if exp_sev == pred_sev:
                sev_correct += 1
            else:
                m.error_categories.append(EvaluationErrorCategory.WRONG_SEVERITY)

            if exp_sev in sev_matrix and pred_sev in sev_matrix[exp_sev]:
                sev_matrix[exp_sev][pred_sev] += 1

            # Priority comparison
            if exp_pri == pred_pri or (exp_pri == "P4" and pred_pri in ("P4", "P3")):
                pri_correct += 1
            else:
                m.error_categories.append(EvaluationErrorCategory.WRONG_PRIORITY)

            if exp_pri in pri_matrix and pred_pri in pri_matrix[exp_pri]:
                pri_matrix[exp_pri][pred_pri] += 1

        sev_acc = (sev_correct / total_eval) if total_eval > 0 else 0.0
        pri_acc = (pri_correct / total_eval) if total_eval > 0 else 0.0

        # Convert to serializable confusion matrix items
        sev_items = [
            ConfusionMatrixItem(expected_class=exp, predicted_class=pred, count=cnt)
            for exp, row in sev_matrix.items()
            for pred, cnt in row.items()
            if cnt > 0
        ]
        pri_items = [
            ConfusionMatrixItem(expected_class=exp, predicted_class=pred, count=cnt)
            for exp, row in pri_matrix.items()
            for pred, cnt in row.items()
            if cnt > 0
        ]

        return {
            "total_evaluated": total_eval,
            "severity_accuracy": sev_acc,
            "severity_accuracy_bps": int(sev_acc * 10000),
            "priority_accuracy": pri_acc,
            "priority_accuracy_bps": int(pri_acc * 10000),
            "severity_confusion_matrix": sev_items,
            "priority_confusion_matrix": pri_items,
        }


class DeterministicExpectedMapper:
    """Provides standard expected risk baselines for benchmark scenarios."""

    @staticmethod
    def get_expected_severity(anomaly_type: str) -> str:
        if anomaly_type == "GHOST_SETTLEMENT":
            return ExceptionSeverity.HIGH.value
        elif anomaly_type == "REFUND_CHARGEBACK_DOUBLE_DIP":
            return ExceptionSeverity.HIGH.value
        elif anomaly_type == "SETTLEMENT_SLA_BREACH":
            return ExceptionSeverity.MEDIUM.value
        elif anomaly_type == "MISSING_UNALLOCATED_SETTLEMENT":
            return ExceptionSeverity.MEDIUM.value
        elif anomaly_type == "PARTIAL_SETTLEMENT":
            return ExceptionSeverity.LOW.value
        elif anomaly_type == "LEGITIMATE_TIMING_EXCEPTION":
            return ExceptionSeverity.LOW.value
        return ExceptionSeverity.LOW.value

    @staticmethod
    def get_expected_priority(anomaly_type: str) -> str:
        if anomaly_type in ("GHOST_SETTLEMENT", "REFUND_CHARGEBACK_DOUBLE_DIP"):
            return PriorityLevel.P1.value
        elif anomaly_type in ("SETTLEMENT_SLA_BREACH", "MISSING_UNALLOCATED_SETTLEMENT"):
            return PriorityLevel.P2.value
        elif anomaly_type in ("PARTIAL_SETTLEMENT", "LEGITIMATE_TIMING_EXCEPTION"):
            return PriorityLevel.P4.value
        return PriorityLevel.P4.value
