"""Remediation outcome evaluation metrics engine."""
from typing import Any, Dict, List
from backend.evaluation.matcher import CaseMatchResult
from backend.models.enums import EvaluationErrorCategory, RemediationStatus


class RemediationMetricsCalculator:
    """Evaluates the execution success and safety of remediation actions."""

    @staticmethod
    def evaluate_remediation_outcomes(
        match_results: List[CaseMatchResult],
        remediation_actions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Evaluates remediation execution against ground truth expectations.
        
        Args:
            match_results: Matched pairs.
            remediation_actions: Map of exception_id -> RemediationAction object.
        """
        total_eval = 0
        rem_planned_count = 0
        rem_success_count = 0
        unauthorized_count = 0
        failed_count = 0
        rollback_count = 0

        for m in match_results:
            if not m.ground_truth:
                continue

            total_eval += 1
            exp_amt = m.ground_truth.expected_exposure

            if not m.prediction:
                continue

            rem = remediation_actions.get(m.prediction.exception_id)
            if not rem:
                # If zero exposure was expected, not having a remediation plan is correct
                if exp_amt == 0:
                    rem_success_count += 1
                continue

            rem_planned_count += 1
            status = rem.status

            # Check unauthorized action on zero exposure cases
            if exp_amt == 0 and status in (
                RemediationStatus.EXECUTING.value,
                RemediationStatus.EXECUTED.value,
                RemediationStatus.AWAITING_VERIFICATION.value,
            ):
                unauthorized_count += 1
                m.error_categories.append(EvaluationErrorCategory.WRONG_REMEDIATION)
                continue

            if status in (
                RemediationStatus.EXECUTED.value,
                RemediationStatus.AWAITING_VERIFICATION.value,
            ):
                rem_success_count += 1
            elif status == RemediationStatus.FAILED.value:
                failed_count += 1
                m.error_categories.append(EvaluationErrorCategory.WRONG_REMEDIATION)
            elif status == RemediationStatus.CANCELLED.value:
                rollback_count += 1

        success_rate = (rem_success_count / total_eval) if total_eval > 0 else 0.0

        return {
            "total_evaluated": total_eval,
            "remediations_planned": rem_planned_count,
            "remediation_success_count": rem_success_count,
            "remediation_success_rate": success_rate,
            "remediation_success_rate_bps": int(success_rate * 10000),
            "unauthorized_action_count": unauthorized_count,
            "failed_remediation_count": failed_count,
            "rollback_count": rollback_count,
        }
