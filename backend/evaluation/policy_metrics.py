"""Policy decision evaluation metrics engine."""
from typing import Any, Dict, List
from backend.evaluation.matcher import CaseMatchResult
from backend.models.enums import EvaluationErrorCategory, PolicyDecisionType, PolicyActionType


class PolicyMetricsCalculator:
    """Evaluates governance policy decisions against ground truth scenario mandates."""

    @staticmethod
    def evaluate_policy_decisions(
        match_results: List[CaseMatchResult],
        policy_decisions: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compares expected policy actions against actual PolicyDecisionRecord outputs.
        
        Args:
            match_results: Matched pairs.
            policy_decisions: Map of exception_id -> PolicyDecisionRecord object.
        """
        total_eval = 0
        policy_correct = 0
        policy_incorrect = 0

        for m in match_results:
            if not m.ground_truth:
                continue

            total_eval += 1
            if not m.prediction:
                policy_incorrect += 1
                m.error_categories.append(EvaluationErrorCategory.WRONG_POLICY)
                continue

            dec = policy_decisions.get(m.prediction.exception_id)
            if not dec:
                # Legitimate cases may not require active policy intervention if left untouched
                if m.ground_truth.expected_exposure == 0:
                    policy_correct += 1
                else:
                    policy_incorrect += 1
                    m.error_categories.append(EvaluationErrorCategory.WRONG_POLICY)
                continue

            anomaly_type = m.ground_truth.anomaly_type
            action_type = getattr(dec, "requested_action", getattr(dec, "action_type", ""))
            decision_type = getattr(dec, "decision", getattr(dec, "decision_type", ""))

            # Check expected policy alignment
            is_valid = True
            if anomaly_type in ("PARTIAL_SETTLEMENT", "LEGITIMATE_TIMING_EXCEPTION"):
                # Must NOT allow financial remediation on legitimate cases
                if action_type in (PolicyActionType.REFUND.value, PolicyActionType.REVERSE_REFUND.value):
                    is_valid = False
            elif anomaly_type in ("GHOST_SETTLEMENT", "REFUND_CHARGEBACK_DOUBLE_DIP"):
                # High risk: requires approval or strict refund/reverse
                if decision_type == PolicyDecisionType.BLOCK.value and action_type != PolicyActionType.NO_ACTION.value:
                    is_valid = False

            if is_valid:
                policy_correct += 1
            else:
                policy_incorrect += 1
                m.error_categories.append(EvaluationErrorCategory.WRONG_POLICY)

        acc = (policy_correct / total_eval) if total_eval > 0 else 0.0

        return {
            "total_evaluated": total_eval,
            "policy_correct": policy_correct,
            "policy_incorrect": policy_incorrect,
            "policy_accuracy": acc,
            "policy_accuracy_bps": int(acc * 10000),
        }
