"""Verification metrics and false-closure safety evaluator."""
from typing import Any, Dict, List
from backend.evaluation.matcher import CaseMatchResult
from backend.models.enums import EvaluationErrorCategory, VerificationStatus, ExceptionState


class VerificationMetricsCalculator:
    """Evaluates post-remediation verification results and detects dangerous false closures."""

    @staticmethod
    def evaluate_verification(
        match_results: List[CaseMatchResult],
        verification_records: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Evaluates verification outcomes against expected resolution states.
        
        Args:
            match_results: Matched pairs.
            verification_records: Map of remediation_id -> latest VerificationRecord.
        """
        total_eval = 0
        attempted_count = 0
        passed_count = 0
        failed_count = 0
        false_closure_count = 0
        escalated_count = 0

        for m in match_results:
            if not m.ground_truth:
                continue

            total_eval += 1
            if not m.prediction:
                continue

            pred_state = m.prediction.state
            expected_ver_state = m.ground_truth.expected_verification_state

            # If prediction state was closed but expected state was FAILED_ESCALATED, flag as false closure!
            if pred_state == ExceptionState.VERIFIED_CLOSED.value:
                if expected_ver_state == "FAILED_ESCALATED":
                    false_closure_count += 1
                    m.is_false_closure = True
                    m.error_categories.append(EvaluationErrorCategory.FALSE_CLOSURE)
                else:
                    passed_count += 1
            elif pred_state == ExceptionState.FAILED_ESCALATED.value:
                if expected_ver_state == "FAILED_ESCALATED":
                    escalated_count += 1
                    passed_count += 1
                else:
                    failed_count += 1
            elif pred_state == ExceptionState.DIAGNOSED.value:
                # Legitimate cases correctly stay in DIAGNOSED
                if m.ground_truth.expected_exposure == 0:
                    passed_count += 1

        success_rate = (passed_count / total_eval) if total_eval > 0 else 0.0

        return {
            "total_evaluated": total_eval,
            "verification_attempted_count": attempted_count,
            "verification_passed_count": passed_count,
            "verification_failed_count": failed_count,
            "false_closure_count": false_closure_count,
            "correct_escalation_count": escalated_count,
            "verification_success_rate": success_rate,
            "verification_success_rate_bps": int(success_rate * 10000),
            "zero_false_closures_verified": (false_closure_count == 0),
        }
