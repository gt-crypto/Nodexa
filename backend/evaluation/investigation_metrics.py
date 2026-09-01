"""Investigation root-cause and explanation evaluation metrics."""
from typing import Any, Dict, List
from backend.evaluation.matcher import CaseMatchResult
from backend.models.enums import EvaluationErrorCategory


class InvestigationMetricsCalculator:
    """Evaluates AI investigation accuracy against ground truth root causes without LLM bias."""

    @staticmethod
    def evaluate_root_causes(
        match_results: List[CaseMatchResult],
        investigation_runs: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compares expected ground truth root causes with predicted AI investigation findings.
        
        Args:
            match_results: Matched ground truth vs prediction pairs.
            investigation_runs: Dictionary mapping exception_id -> InvestigationRun object.
        """
        total_eval = 0
        correct_count = 0
        incorrect_count = 0
        missing_count = 0
        family_breakdown: Dict[str, Dict[str, Any]] = {}

        for m in match_results:
            if not m.ground_truth:
                continue

            total_eval += 1
            fam = m.ground_truth.anomaly_type
            if fam not in family_breakdown:
                family_breakdown[fam] = {"expected": 0, "correct": 0, "incorrect": 0, "missing": 0}
            family_breakdown[fam]["expected"] += 1

            if not m.prediction:
                missing_count += 1
                family_breakdown[fam]["missing"] += 1
                m.error_categories.append(EvaluationErrorCategory.WRONG_ROOT_CAUSE)
                continue

            inv = investigation_runs.get(m.prediction.exception_id)
            if not inv:
                missing_count += 1
                family_breakdown[fam]["missing"] += 1
                m.error_categories.append(EvaluationErrorCategory.WRONG_ROOT_CAUSE)
                continue

            expected_rc = m.ground_truth.expected_root_cause.strip().lower()
            pred_rc = (getattr(inv, "root_cause", "") or getattr(inv, "final_classification", "") or "").strip().lower()
            anomaly_clean = m.ground_truth.anomaly_type.lower().replace("_", " ")

            # Deterministic semantic alignment check
            is_match = (
                expected_rc in pred_rc
                or pred_rc in expected_rc
                or (anomaly_clean in pred_rc)
                or ("ghost" in expected_rc and any(k in pred_rc for k in ("ghost", "failed", "failure", "contradiction")))
                or (("double" in expected_rc or "refund" in expected_rc or "chargeback" in expected_rc) and any(k in pred_rc for k in ("refund", "chargeback", "overlap", "double")))
                or (("sla" in expected_rc or "window" in expected_rc) and any(k in pred_rc for k in ("sla", "window", "timing", "breach")))
                or (("partial" in expected_rc) and ("partial" in pred_rc or "settlement" in pred_rc))
                or (("missing" in expected_rc or "downstream" in expected_rc) and any(k in pred_rc for k in ("missing", "zero", "downstream", "settlement")))
                or (("unallocated" in expected_rc or "inflow" in expected_rc or "orphan" in expected_rc) and any(k in pred_rc for k in ("unallocated", "orphan", "inflow", "bank")))
                or (("timing" in expected_rc or "window" in expected_rc) and any(k in pred_rc for k in ("timing", "window", "calendar", "legitimate")))
            )

            if is_match:
                correct_count += 1
                family_breakdown[fam]["correct"] += 1
            else:
                incorrect_count += 1
                family_breakdown[fam]["incorrect"] += 1
                m.error_categories.append(EvaluationErrorCategory.WRONG_ROOT_CAUSE)

        acc = (correct_count / total_eval) if total_eval > 0 else 0.0
        acc_bps = int(acc * 10000)

        return {
            "total_evaluated": total_eval,
            "correct_root_causes": correct_count,
            "incorrect_root_causes": incorrect_count,
            "missing_root_causes": missing_count,
            "root_cause_accuracy": acc,
            "root_cause_accuracy_bps": acc_bps,
            "family_breakdown": family_breakdown,
        }
