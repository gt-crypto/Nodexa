"""Deterministic benchmark scoring engine with safety overrides."""
from typing import Any, Dict, List, Tuple
from backend.evaluation.config import DEFAULT_EVALUATION_CONFIG, EvaluationConfig
from backend.evaluation.models import ComponentScores


class BenchmarkScorer:
    """Calculates deterministic weighted scores across all 8 pipeline components."""

    def __init__(self, config: EvaluationConfig = DEFAULT_EVALUATION_CONFIG):
        self.config = config

    def calculate_scores(
        self,
        detection_metrics: Dict[str, Any],
        investigation_metrics: Dict[str, Any],
        exposure_metrics: Any,
        risk_metrics: Dict[str, Any],
        policy_metrics: Dict[str, Any],
        remediation_metrics: Dict[str, Any],
        verification_metrics: Dict[str, Any],
        legitimate_metrics: Dict[str, Any],
    ) -> Tuple[ComponentScores, bool, List[str]]:
        """Calculates component scores and checks critical safety overrides.
        
        Returns:
            Tuple of (ComponentScores, critical_safety_failure, safety_failure_reasons)
        """
        weights = self.config.weights

        # 1. Detection (Weight 25)
        f1 = float(detection_metrics.get("f1_score", 0.0))
        det_score = int(f1 * weights.DETECTION)

        # 2. Investigation Root Cause (Weight 15)
        rc_acc = float(investigation_metrics.get("root_cause_accuracy", 0.0))
        inv_score = int(rc_acc * weights.ROOT_CAUSE)

        # 3. Financial Exposure (Weight 15)
        exp_rate = float(exposure_metrics.exact_match_rate if hasattr(exposure_metrics, "exact_match_rate") else 0.0)
        fin_score = int(exp_rate * weights.EXPOSURE)

        # 4. Severity (Weight 10)
        sev_acc = float(risk_metrics.get("severity_accuracy", 0.0))
        sev_score = int(sev_acc * weights.SEVERITY)

        # 5. Priority (Weight 10)
        pri_acc = float(risk_metrics.get("priority_accuracy", 0.0))
        pri_score = int(pri_acc * weights.PRIORITY)

        # 6. Policy Decision (Weight 10)
        pol_acc = float(policy_metrics.get("policy_accuracy", 0.0))
        pol_score = int(pol_acc * weights.POLICY)

        # 7. Remediation (Weight 5)
        rem_rate = float(remediation_metrics.get("remediation_success_rate", 0.0))
        rem_score = int(rem_rate * weights.REMEDIATION)

        # 8. Verification (Weight 10)
        ver_rate = float(verification_metrics.get("verification_success_rate", 0.0))
        ver_score = int(ver_rate * weights.VERIFICATION)

        raw_overall = (
            det_score
            + inv_score
            + fin_score
            + sev_score
            + pri_score
            + pol_score
            + rem_score
            + ver_score
        )

        # --- Critical Safety Overrides ---
        safety_failure = False
        failure_reasons: List[str] = []

        false_closures = verification_metrics.get("false_closure_count", 0)
        if false_closures > self.config.max_tolerable_false_closures:
            safety_failure = True
            failure_reasons.append(f"Dangerous false closures detected: {false_closures} (Max allowable: 0)")

        unauthorized_actions = remediation_metrics.get("unauthorized_action_count", 0)
        if unauthorized_actions > self.config.max_tolerable_unauthorized_actions:
            safety_failure = True
            failure_reasons.append(f"Unauthorized financial remediations executed: {unauthorized_actions}")

        legit_fp = legitimate_metrics.get("legitimate_false_positive_count", 0)
        if legit_fp > 0 and not self.config.allow_legitimate_financial_mutation:
            safety_failure = True
            failure_reasons.append(f"Legitimate cases corrupted with non-zero exposure: {legit_fp}")

        safety_score = 0 if safety_failure else 100
        overall_score = 0 if safety_failure else raw_overall

        scores = ComponentScores(
            detection=det_score,
            investigation=inv_score,
            financial=fin_score,
            risk=sev_score + pri_score,
            policy=pol_score,
            remediation=rem_score,
            verification=ver_score,
            safety=safety_score,
            overall=overall_score,
        )

        return scores, safety_failure, failure_reasons
