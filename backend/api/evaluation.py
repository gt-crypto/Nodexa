"""REST API Router for Benchmark Evaluation, Precision/Recall, and System Accuracy."""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.services.repositories.evaluation_repository import EvaluationRepository
from backend.evaluation.service import BenchmarkEvaluationService
from backend.evaluation.models import (
    EvaluationRunRequest,
    EvaluationRunResponse,
    EvaluationCaseResponse,
    EvaluationReportSummary,
    ComponentScores,
)

evaluation_router = APIRouter(prefix="/evaluation", tags=["Evaluation & Benchmarking"])


@evaluation_router.post(
    "/run",
    response_model=EvaluationReportSummary,
    status_code=status.HTTP_200_OK,
    summary="Execute Benchmark Evaluation",
    description="Runs deterministic benchmark evaluation against isolated synthetic ground truth.",
)
def run_evaluation(
    request: EvaluationRunRequest,
    db: Session = Depends(get_db),
) -> EvaluationReportSummary:
    """Executes a benchmark evaluation run against a synthetic dataset."""
    service = BenchmarkEvaluationService()
    try:
        return service.run_benchmark(session=db, request=request)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Evaluation failed: {str(e)}",
        )


@evaluation_router.get(
    "/runs",
    response_model=List[EvaluationRunResponse],
    summary="List Evaluation Runs",
    description="Retrieves a list of historical benchmark evaluation runs.",
)
def list_evaluation_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
) -> List[EvaluationRunResponse]:
    """Retrieves all past benchmark evaluation runs."""
    repo = EvaluationRepository(db)
    runs = repo.list_evaluation_runs(limit=limit, offset=offset)
    results = []
    for r in runs:
        safety_reasons = []
        if r.safety_failure_reasons:
            try:
                safety_reasons = json.loads(r.safety_failure_reasons)
            except Exception:
                safety_reasons = [r.safety_failure_reasons]

        results.append(
            EvaluationRunResponse(
                evaluation_run_id=r.evaluation_run_id,
                dataset_id=r.dataset_id,
                benchmark_version=r.benchmark_version,
                system_version=r.system_version,
                status=r.status,
                total_ground_truth_cases=r.total_ground_truth_cases,
                total_predictions=r.total_predictions,
                true_positives=r.true_positives,
                false_positives=r.false_positives,
                false_negatives=r.false_negatives,
                precision=r.precision / 10000.0,
                precision_bps=r.precision,
                recall=r.recall / 10000.0,
                recall_bps=r.recall,
                f1_score=r.f1_score / 10000.0,
                f1_score_bps=r.f1_score,
                overall_score=r.overall_score,
                scores=ComponentScores(
                    detection=r.detection_score,
                    investigation=r.investigation_score,
                    financial=r.financial_score,
                    risk=r.risk_score,
                    policy=r.policy_score,
                    remediation=r.remediation_score,
                    verification=r.verification_score,
                    safety=r.safety_score,
                    overall=r.overall_score,
                ),
                safety_status=r.safety_status,
                critical_safety_failure=r.critical_safety_failure,
                safety_failure_reasons=safety_reasons,
                started_at=r.started_at,
                completed_at=r.completed_at,
                created_at=r.created_at,
            )
        )
    return results


@evaluation_router.get(
    "/runs/{evaluation_run_id}",
    response_model=EvaluationReportSummary,
    summary="Get Evaluation Run Report",
    description="Retrieves the complete report for an evaluation run.",
)
def get_evaluation_run(
    evaluation_run_id: str,
    db: Session = Depends(get_db),
) -> EvaluationReportSummary:
    """Retrieves an evaluation run by ID and parses its summary report."""
    repo = EvaluationRepository(db)
    run = repo.get_evaluation_run(evaluation_run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run {evaluation_run_id} not found",
        )
    if not run.summary_report:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Evaluation run summary report is empty",
        )
    report_dict = json.loads(run.summary_report)
    return EvaluationReportSummary(**report_dict)


@evaluation_router.get(
    "/runs/{evaluation_run_id}/cases",
    response_model=List[EvaluationCaseResponse],
    summary="List Cases for Evaluation Run",
    description="Retrieves case-level ground truth vs predicted evaluation records.",
)
def list_run_cases(
    evaluation_run_id: str,
    match_status: Optional[str] = None,
    db: Session = Depends(get_db),
) -> List[EvaluationCaseResponse]:
    """Retrieves all case-level comparisons for an evaluation run."""
    repo = EvaluationRepository(db)
    cases = repo.get_cases_for_run(evaluation_run_id, match_status=match_status)
    results = []
    for c in cases:
        error_cats = []
        if c.error_categories:
            try:
                error_cats = json.loads(c.error_categories)
            except Exception:
                error_cats = [c.error_categories]

        details_dict = {}
        if c.details:
            try:
                details_dict = json.loads(c.details)
            except Exception:
                details_dict = {}

        results.append(
            EvaluationCaseResponse(
                evaluation_case_id=c.evaluation_case_id,
                evaluation_run_id=c.evaluation_run_id,
                ground_truth_case_id=c.ground_truth_case_id,
                predicted_exception_id=c.predicted_exception_id,
                match_status=c.match_status,
                matched_by=c.matched_by,
                matched_identifier=c.matched_identifier,
                expected_exception_type=c.expected_exception_type,
                predicted_exception_type=c.predicted_exception_type,
                expected_root_cause=c.expected_root_cause,
                predicted_root_cause=c.predicted_root_cause,
                expected_exposure=c.expected_exposure,
                predicted_exposure=c.predicted_exposure,
                exposure_error=c.exposure_error,
                expected_severity=c.expected_severity,
                predicted_severity=c.predicted_severity,
                expected_priority=c.expected_priority,
                predicted_priority=c.predicted_priority,
                expected_resolution_class=c.expected_resolution_class,
                predicted_resolution_class=c.predicted_resolution_class,
                expected_policy_decision=c.expected_policy_decision,
                predicted_policy_decision=c.predicted_policy_decision,
                remediation_result=c.remediation_result,
                verification_result=c.verification_result,
                is_false_closure=c.is_false_closure,
                is_legitimate_case=c.is_legitimate_case,
                error_categories=error_cats,
                details=details_dict,
                created_at=c.created_at,
            )
        )
    return results


@evaluation_router.get(
    "/runs/{evaluation_run_id}/metrics",
    summary="Get Component Metrics",
    description="Returns detailed component metrics for an evaluation run.",
)
def get_run_metrics(
    evaluation_run_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieves component metrics breakdown for an evaluation run."""
    repo = EvaluationRepository(db)
    run = repo.get_evaluation_run(evaluation_run_id)
    if not run or not run.summary_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run {evaluation_run_id} not found",
        )
    report = json.loads(run.summary_report)
    return {
        "scores": report.get("run", {}).get("scores", {}),
        "detection_by_type": report.get("detection_by_type", {}),
        "exposure_accuracy": report.get("exposure_accuracy", {}),
        "legitimate_cases": report.get("legitimate_cases_summary", {}),
        "normal_cases": report.get("normal_cases_summary", {}),
    }


@evaluation_router.get(
    "/runs/{evaluation_run_id}/errors",
    summary="Get Error Breakdown",
    description="Returns false positives, false negatives, and misclassifications.",
)
def get_run_errors(
    evaluation_run_id: str,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieves error breakdown for an evaluation run."""
    repo = EvaluationRepository(db)
    run = repo.get_evaluation_run(evaluation_run_id)
    if not run or not run.summary_report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run {evaluation_run_id} not found",
        )
    report = json.loads(run.summary_report)
    return {
        "false_positives": report.get("false_positives", []),
        "false_negatives": report.get("false_negatives", []),
        "misclassifications": report.get("misclassifications", []),
        "critical_safety_violations": report.get("critical_safety_violations", []),
    }


@evaluation_router.get(
    "/benchmark",
    response_model=Optional[EvaluationReportSummary],
    summary="Get Latest Benchmark Summary",
    description="Returns the most recent system benchmark summary.",
)
def get_latest_benchmark(
    db: Session = Depends(get_db),
) -> Optional[EvaluationReportSummary]:
    """Retrieves the latest completed benchmark evaluation report."""
    repo = EvaluationRepository(db)
    run = repo.get_latest_benchmark_run()
    if not run or not run.summary_report:
        return None
    report_dict = json.loads(run.summary_report)
    return EvaluationReportSummary(**report_dict)
