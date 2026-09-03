"""Regression tests for Operational Stage Accuracy Rates and NaN prevention in Benchmark Evaluation."""
import pytest
from datetime import datetime, timezone
from backend.evaluation.models import (
    EvaluationRunResponse,
    EvaluationReportSummary,
    ComponentScores,
    ExposureAccuracySummary,
)
from backend.evaluation.report import EvaluationReportBuilder


def test_evaluation_report_summary_defaults():
    """Verify that EvaluationReportSummary defaults all stage accuracy fields to 0.0/0 without NaN."""
    now = datetime.now(timezone.utc)
    run_resp = EvaluationRunResponse(
        evaluation_run_id="run_test_nan_prevention",
        dataset_id="test_ds",
        benchmark_version="2.0",
        system_version="2.0",
        status="COMPLETED",
        total_ground_truth_cases=0,
        total_predictions=0,
        true_positives=0,
        false_positives=0,
        false_negatives=0,
        precision=0.0,
        precision_bps=0,
        recall=0.0,
        recall_bps=0,
        f1_score=0.0,
        f1_score_bps=0,
        overall_score=0,
        scores=ComponentScores(
            detection=0,
            investigation=0,
            financial=0,
            risk=0,
            policy=0,
            remediation=0,
            verification=0,
            safety=0,
            overall=0,
        ),
        safety_status="PASSED",
        critical_safety_failure=False,
        safety_failure_reasons=[],
        started_at=now,
        completed_at=now,
        created_at=now,
    )

    exp_summary = ExposureAccuracySummary(
        total_evaluated=0,
        exact_matches=0,
        exact_match_rate=0.0,
        exact_match_rate_bps=0,
        mean_absolute_error=0,
        max_absolute_error=0,
        within_threshold_count=0,
        within_threshold_rate=0.0,
        total_expected_exposure=0,
        total_predicted_exposure=0,
        total_absolute_error=0,
        zero_exposure_cases_verified=True,
    )

    # Build report with empty metrics
    report = EvaluationReportBuilder.build_report_summary(
        run=run_resp,
        match_results=[],
        type_breakdown={},
        exposure_summary=exp_summary,
        risk_metrics={},
        legitimate_summary={},
        normal_summary={},
        safety_violations=[],
        inv_metrics={},
        pol_metrics={},
        rem_metrics={},
        ver_metrics={},
    )

    assert report.root_cause_accuracy == 0.0
    assert report.severity_accuracy == 0.0
    assert report.priority_accuracy == 0.0
    assert report.policy_accuracy == 0.0
    assert report.remediation_success_rate == 0.0
    assert report.verification_success_rate == 0.0
    assert report.false_closure_count == 0


def test_evaluation_report_summary_with_metrics():
    """Verify that stage accuracy metrics are correctly propagated from component calculators."""
    now = datetime.now(timezone.utc)
    run_resp = EvaluationRunResponse(
        evaluation_run_id="run_test_valid_metrics",
        dataset_id="test_ds",
        benchmark_version="2.0",
        system_version="2.0",
        status="COMPLETED",
        total_ground_truth_cases=10,
        total_predictions=10,
        true_positives=10,
        false_positives=0,
        false_negatives=0,
        precision=1.0,
        precision_bps=10000,
        recall=1.0,
        recall_bps=10000,
        f1_score=1.0,
        f1_score_bps=10000,
        overall_score=95,
        scores=ComponentScores(
            detection=25,
            investigation=15,
            financial=15,
            risk=15,
            policy=10,
            remediation=5,
            verification=10,
            safety=5,
            overall=95,
        ),
        safety_status="PASSED",
        critical_safety_failure=False,
        safety_failure_reasons=[],
        started_at=now,
        completed_at=now,
        created_at=now,
    )

    exp_summary = ExposureAccuracySummary(
        total_evaluated=10,
        exact_matches=10,
        exact_match_rate=1.0,
        exact_match_rate_bps=10000,
        mean_absolute_error=0,
        max_absolute_error=0,
        within_threshold_count=10,
        within_threshold_rate=1.0,
        total_expected_exposure=50000,
        total_predicted_exposure=50000,
        total_absolute_error=0,
        zero_exposure_cases_verified=True,
    )

    report = EvaluationReportBuilder.build_report_summary(
        run=run_resp,
        match_results=[],
        type_breakdown={},
        exposure_summary=exp_summary,
        risk_metrics={"severity_accuracy": 0.95, "priority_accuracy": 0.90},
        legitimate_summary={},
        normal_summary={},
        safety_violations=[],
        inv_metrics={"root_cause_accuracy": 0.92, "root_cause_accuracy_bps": 9200},
        pol_metrics={"policy_accuracy": 0.98},
        rem_metrics={"remediation_success_rate": 1.0},
        ver_metrics={"verification_success_rate": 1.0, "false_closure_count": 0},
    )

    assert report.root_cause_accuracy == 0.92
    assert report.root_cause_accuracy_bps == 9200
    assert report.severity_accuracy == 0.95
    assert report.priority_accuracy == 0.90
    assert report.policy_accuracy == 0.98
    assert report.remediation_success_rate == 1.0
    assert report.verification_success_rate == 1.0
    assert report.false_closure_count == 0
