"""Financial exposure accuracy metrics engine with integer minor-unit precision."""
from typing import Any, Dict, List
from backend.evaluation.matcher import CaseMatchResult
from backend.evaluation.models import ExposureAccuracySummary
from backend.models.enums import EvaluationErrorCategory


class ExposureMetricsCalculator:
    """Computes exact-match and error distribution metrics for financial exposure in paise minor units."""

    @staticmethod
    def compute_exposure_metrics(match_results: List[CaseMatchResult]) -> ExposureAccuracySummary:
        """Compares ground truth expected exposure against operational predicted exposure.
        
        Zero floating point operations are used for monetary accumulation.
        """
        exact_matches = 0
        total_eval = 0
        total_expected = 0
        total_predicted = 0
        total_abs_error = 0
        max_abs_error = 0
        zero_cases_verified = 0

        for m in match_results:
            if not m.ground_truth:
                continue

            total_eval += 1
            exp_amt = int(m.ground_truth.expected_exposure)
            pred_amt = int(m.prediction.exposure) if m.prediction else 0

            total_expected += exp_amt
            total_predicted += pred_amt

            abs_err = abs(exp_amt - pred_amt)
            total_abs_error += abs_err
            if abs_err > max_abs_error:
                max_abs_error = abs_err

            if exp_amt == 0:
                if pred_amt == 0:
                    zero_cases_verified += 1
                else:
                    m.error_categories.append(EvaluationErrorCategory.LEGITIMATE_CASE_CORRUPTION)

            if abs_err == 0:
                exact_matches += 1
            else:
                m.error_categories.append(EvaluationErrorCategory.WRONG_EXPOSURE)

        match_rate = (exact_matches / total_eval) if total_eval > 0 else 0.0
        match_rate_bps = (exact_matches * 10000) // total_eval if total_eval > 0 else 0
        mae = (total_abs_error / total_eval) if total_eval > 0 else 0.0

        return ExposureAccuracySummary(
            exact_matches=exact_matches,
            total_evaluated=total_eval,
            exact_match_rate=match_rate,
            exact_match_rate_bps=match_rate_bps,
            total_expected_exposure=total_expected,
            total_predicted_exposure=total_predicted,
            total_absolute_error=total_abs_error,
            max_absolute_error=max_abs_error,
            mean_absolute_error=mae,
            zero_exposure_cases_verified=zero_cases_verified,
        )
