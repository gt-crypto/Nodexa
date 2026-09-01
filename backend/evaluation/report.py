"""Structured benchmark report builder and serializer."""
import json
from typing import Any, Dict, List
from backend.evaluation.matcher import CaseMatchResult
from backend.evaluation.models import (
    EvaluationRunResponse,
    EvaluationCaseResponse,
    EvaluationReportSummary,
    ExposureAccuracySummary,
    ComponentScores,
)
from backend.models.enums import EvaluationMatchStatus


class EvaluationReportBuilder:
    """Constructs comprehensive evaluation report summaries and serialized exports."""

    @staticmethod
    def build_report_summary(
        run: EvaluationRunResponse,
        match_results: List[CaseMatchResult],
        type_breakdown: Dict[str, Any],
        exposure_summary: ExposureAccuracySummary,
        risk_metrics: Dict[str, Any],
        legitimate_summary: Dict[str, Any],
        normal_summary: Dict[str, Any],
        safety_violations: List[str],
    ) -> EvaluationReportSummary:
        """Assembles all evaluation artifacts into a structured EvaluationReportSummary."""
        case_responses = [
            EvaluationReportBuilder.serialize_match_result(run.evaluation_run_id, m, idx)
            for idx, m in enumerate(match_results)
        ]

        false_positives = [
            c for c in case_responses
            if c.match_status in (
                EvaluationMatchStatus.FALSE_POSITIVE.value,
                EvaluationMatchStatus.LEGITIMATE_FALSE_POSITIVE.value,
            )
        ]
        false_negatives = [
            c for c in case_responses
            if c.match_status == EvaluationMatchStatus.FALSE_NEGATIVE.value
        ]
        misclassifications = [
            c for c in case_responses
            if len(c.error_categories) > 0
        ]

        confusion_matrices = {
            "severity": risk_metrics.get("severity_confusion_matrix", []),
            "priority": risk_metrics.get("priority_confusion_matrix", []),
        }

        return EvaluationReportSummary(
            run=run,
            detection_by_type=type_breakdown,
            exposure_accuracy=exposure_summary,
            confusion_matrices=confusion_matrices,
            legitimate_cases_summary=legitimate_summary,
            normal_cases_summary=normal_summary,
            false_positives=false_positives,
            false_negatives=false_negatives,
            misclassifications=misclassifications,
            critical_safety_violations=safety_violations,
        )

    @staticmethod
    def serialize_match_result(
        run_id: str,
        match: CaseMatchResult,
        index: int,
    ) -> EvaluationCaseResponse:
        """Transforms a CaseMatchResult into a serializable EvaluationCaseResponse."""
        gt = match.ground_truth
        pred = match.prediction

        exp_exposure = int(gt.expected_exposure) if gt else 0
        pred_exposure = int(pred.exposure) if pred else 0
        exposure_err = abs(exp_exposure - pred_exposure)

        return EvaluationCaseResponse(
            evaluation_case_id=f"eval_case_{run_id}_{index:04d}",
            evaluation_run_id=run_id,
            ground_truth_case_id=gt.case_id if gt else None,
            predicted_exception_id=pred.exception_id if pred else None,
            match_status=match.match_status.value if hasattr(match.match_status, "value") else str(match.match_status),
            matched_by=match.matched_by,
            matched_identifier=match.matched_identifier,
            expected_exception_type=gt.anomaly_type if gt else None,
            predicted_exception_type=pred.exception_type if pred else None,
            expected_root_cause=gt.expected_root_cause if gt else None,
            predicted_root_cause=getattr(pred, "description", None) if pred else None,
            expected_exposure=exp_exposure,
            predicted_exposure=pred_exposure,
            exposure_error=exposure_err,
            expected_severity=None,
            predicted_severity=pred.severity if pred else None,
            expected_priority=None,
            predicted_priority=None,
            expected_resolution_class=gt.expected_resolution_class if gt else None,
            predicted_resolution_class=None,
            expected_policy_decision=None,
            predicted_policy_decision=None,
            remediation_result=None,
            verification_result=None,
            is_false_closure=getattr(match, "is_false_closure", False),
            is_legitimate_case=(exp_exposure == 0),
            error_categories=[
                ec.value if hasattr(ec, "value") else str(ec)
                for ec in match.error_categories
            ],
            details=match.details,
            created_at=gt.created_at if gt else pred.created_at if pred else None,
        )
