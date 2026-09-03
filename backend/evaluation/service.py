"""Benchmark Evaluation Service orchestrator.

Coordinates zero-mutation benchmark evaluations against isolated synthetic ground truth,
persisting EvaluationRun and EvaluationCase records and emitting immutable audit events.
"""
import uuid
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.evaluation.config import DEFAULT_EVALUATION_CONFIG, EvaluationConfig
from backend.evaluation.ground_truth import GroundTruthReader
from backend.evaluation.matcher import DeterministicMatcher, CaseMatchResult
from backend.evaluation.detection_metrics import DetectionMetricsCalculator
from backend.evaluation.investigation_metrics import InvestigationMetricsCalculator
from backend.evaluation.exposure_metrics import ExposureMetricsCalculator
from backend.evaluation.risk_metrics import RiskMetricsCalculator
from backend.evaluation.policy_metrics import PolicyMetricsCalculator
from backend.evaluation.remediation_metrics import RemediationMetricsCalculator
from backend.evaluation.verification_metrics import VerificationMetricsCalculator
from backend.evaluation.scorer import BenchmarkScorer
from backend.evaluation.report import EvaluationReportBuilder
from backend.evaluation.models import (
    EvaluationRunRequest,
    EvaluationRunResponse,
    EvaluationReportSummary,
    ComponentScores,
)

from backend.models.evaluation import EvaluationRun, EvaluationCase
from backend.models.exceptions import ExceptionRecord
from backend.models.investigation import InvestigationRun
from backend.models.risk import RiskAssessment
from backend.models.policy import PolicyDecisionRecord
from backend.models.remediation import RemediationAction
from backend.models.verification import VerificationRecord
from backend.models.financial_sources import GatewayTransaction
from backend.models.audit import AuditEvent
from backend.models.enums import EvaluationStatus

from backend.services.repositories.evaluation_repository import EvaluationRepository
from backend.services.repositories.audit_repository import AuditRepository


class BenchmarkEvaluationService:
    """Orchestrates comprehensive benchmark evaluations with ground-truth isolation."""

    def __init__(self, config: EvaluationConfig = DEFAULT_EVALUATION_CONFIG):
        self.config = config
        self.scorer = BenchmarkScorer(config)

    def run_benchmark(
        self,
        session: Session,
        request: EvaluationRunRequest,
    ) -> EvaluationReportSummary:
        """Executes a benchmark evaluation run against a synthetic dataset.
        
        Guaranteed to be read-only with respect to operational financial sources and exceptions.
        """
        eval_repo = EvaluationRepository(session)
        audit_repo = AuditRepository(session)
        now = datetime.now(timezone.utc)

        # 1. Check Idempotency / Cache
        if not request.force_rerun:
            cached_run = eval_repo.get_latest_run_for_dataset(
                request.dataset_id,
                self.config.benchmark_version,
            )
            if cached_run and cached_run.summary_report:
                report_dict = json.loads(cached_run.summary_report)
                return EvaluationReportSummary(**report_dict)

        eval_run_id = f"eval_run_{uuid.uuid4().hex[:12]}"

        # Audit: EVALUATION_STARTED
        audit_repo.append_audit_event(
            AuditEvent(
                audit_event_id=f"audit_{uuid.uuid4().hex[:12]}",
                event_type="EVALUATION_STARTED",
                actor_type=request.actor_type,
                actor_id=request.actor_id,
                exception_id=None,
                investigation_id=None,
                event_summary=f"Benchmark evaluation started for dataset {request.dataset_id}",
                event_payload=json.dumps({
                    "evaluation_run_id": eval_run_id,
                    "dataset_id": request.dataset_id,
                    "benchmark_version": self.config.benchmark_version,
                }),
                timestamp=now,
            )
        )
        session.flush()

        try:
            # 2. Read Ground Truth (Isolated access)
            gt_cases = GroundTruthReader.list_ground_truth_cases(session)

            # 3. Read Operational State (Read-only queries, strictly excluding live-injected cases)
            exceptions = list(session.scalars(select(ExceptionRecord).where(ExceptionRecord.source_flag != "live-injected")).all())
            inv_runs = {i.exception_id: i for i in session.scalars(select(InvestigationRun)).all()}
            risk_assessments = {r.exception_id: r for r in session.scalars(select(RiskAssessment)).all()}
            policy_decisions = {p.exception_id: p for p in session.scalars(select(PolicyDecisionRecord)).all()}
            remediations = {rem.exception_id: rem for rem in session.scalars(select(RemediationAction)).all()}
            verifications = {v.remediation_id: v for v in session.scalars(select(VerificationRecord)).all()}
            total_gateway_txs = len(list(session.scalars(select(GatewayTransaction).where(~GatewayTransaction.payment_id.like("PAY-INJ%"))).all()))

            # 4. Deterministic Hierarchical Matching
            match_results = DeterministicMatcher.match_all(gt_cases, exceptions)

            # 5. Compute Component Metrics
            det_metrics = DetectionMetricsCalculator.compute_overall_metrics(match_results)
            type_breakdown = DetectionMetricsCalculator.compute_type_breakdown(match_results)
            legit_metrics = DetectionMetricsCalculator.compute_legitimate_case_metrics(match_results)
            normal_metrics = DetectionMetricsCalculator.compute_normal_case_metrics(total_gateway_txs, match_results)

            inv_metrics = InvestigationMetricsCalculator.evaluate_root_causes(match_results, inv_runs)
            exp_metrics = ExposureMetricsCalculator.compute_exposure_metrics(match_results)
            risk_metrics = RiskMetricsCalculator.evaluate_severity_and_priority(match_results, risk_assessments)
            pol_metrics = PolicyMetricsCalculator.evaluate_policy_decisions(match_results, policy_decisions)
            rem_metrics = RemediationMetricsCalculator.evaluate_remediation_outcomes(match_results, remediations)
            ver_metrics = VerificationMetricsCalculator.evaluate_verification(match_results, verifications)

            # 6. Scoring & Safety Overrides
            scores, safety_failed, failure_reasons = self.scorer.calculate_scores(
                detection_metrics=det_metrics,
                investigation_metrics=inv_metrics,
                exposure_metrics=exp_metrics,
                risk_metrics=risk_metrics,
                policy_metrics=pol_metrics,
                remediation_metrics=rem_metrics,
                verification_metrics=ver_metrics,
                legitimate_metrics=legit_metrics,
            )

            safety_status = "FAILED" if safety_failed else "PASSED"
            completed_at = datetime.now(timezone.utc)

            # 7. Create EvaluationRun response DTO
            run_response = EvaluationRunResponse(
                evaluation_run_id=eval_run_id,
                dataset_id=request.dataset_id,
                benchmark_version=self.config.benchmark_version,
                system_version=self.config.evaluation_version,
                status=EvaluationStatus.COMPLETED.value,
                total_ground_truth_cases=len(gt_cases),
                total_predictions=len(exceptions),
                true_positives=det_metrics["true_positives"],
                false_positives=det_metrics["false_positives"],
                false_negatives=det_metrics["false_negatives"],
                precision=det_metrics["precision"],
                precision_bps=det_metrics["precision_bps"],
                recall=det_metrics["recall"],
                recall_bps=det_metrics["recall_bps"],
                f1_score=det_metrics["f1_score"],
                f1_score_bps=det_metrics["f1_score_bps"],
                overall_score=scores.overall,
                scores=scores,
                safety_status=safety_status,
                critical_safety_failure=safety_failed,
                safety_failure_reasons=failure_reasons,
                started_at=now,
                completed_at=completed_at,
                created_at=now,
            )

            # Build Full Report Summary
            report = EvaluationReportBuilder.build_report_summary(
                run=run_response,
                match_results=match_results,
                type_breakdown=type_breakdown,
                exposure_summary=exp_metrics,
                risk_metrics=risk_metrics,
                legitimate_summary=legit_metrics,
                normal_summary=normal_metrics,
                safety_violations=failure_reasons,
                inv_metrics=inv_metrics,
                pol_metrics=pol_metrics,
                rem_metrics=rem_metrics,
                ver_metrics=ver_metrics,
            )

            # 8. Persist EvaluationRun and Cases in Database
            db_run = EvaluationRun(
                evaluation_run_id=eval_run_id,
                dataset_id=request.dataset_id,
                benchmark_version=self.config.benchmark_version,
                system_version=self.config.evaluation_version,
                status=EvaluationStatus.COMPLETED.value,
                total_ground_truth_cases=len(gt_cases),
                total_predictions=len(exceptions),
                true_positives=det_metrics["true_positives"],
                false_positives=det_metrics["false_positives"],
                false_negatives=det_metrics["false_negatives"],
                precision=det_metrics["precision_bps"],
                recall=det_metrics["recall_bps"],
                f1_score=det_metrics["f1_score_bps"],
                overall_score=scores.overall,
                detection_score=scores.detection,
                investigation_score=scores.investigation,
                financial_score=scores.financial,
                risk_score=scores.risk,
                policy_score=scores.policy,
                remediation_score=scores.remediation,
                verification_score=scores.verification,
                safety_score=scores.safety,
                safety_status=safety_status,
                critical_safety_failure=safety_failed,
                safety_failure_reasons=json.dumps(failure_reasons),
                summary_report=json.dumps(report.model_dump(), default=str),
                started_at=now,
                completed_at=completed_at,
                created_at=now,
            )
            eval_repo.create_evaluation_run(db_run)

            # Persist Cases (deduplicated by evaluation_case_id)
            seen_case_ids = set()
            db_cases = []
            for c in (report.false_positives + report.false_negatives + report.misclassifications):
                if c.evaluation_case_id in seen_case_ids:
                    continue
                seen_case_ids.add(c.evaluation_case_id)
                db_cases.append(
                    EvaluationCase(
                        evaluation_case_id=c.evaluation_case_id,
                        evaluation_run_id=eval_run_id,
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
                        error_categories=json.dumps(c.error_categories),
                        details=json.dumps(c.details),
                        created_at=now,
                    )
                )
            eval_repo.save_cases(db_cases)

            # Audit: EVALUATION_COMPLETED
            audit_repo.append_audit_event(
                AuditEvent(
                    audit_event_id=f"audit_{uuid.uuid4().hex[:12]}",
                    event_type="EVALUATION_COMPLETED",
                    actor_type=request.actor_type,
                    actor_id=request.actor_id,
                    exception_id=None,
                    investigation_id=None,
                    event_summary=f"Benchmark evaluation completed for dataset {request.dataset_id}",
                    event_payload=json.dumps({
                        "evaluation_run_id": eval_run_id,
                        "overall_score": scores.overall,
                        "f1_bps": det_metrics["f1_score_bps"],
                        "safety_status": safety_status,
                    }),
                    timestamp=completed_at,
                )
            )
            session.commit()

            return report

        except Exception as e:
            session.rollback()
            # Audit: EVALUATION_FAILED
            audit_repo.append_audit_event(
                AuditEvent(
                    audit_event_id=f"audit_{uuid.uuid4().hex[:12]}",
                    event_type="EVALUATION_FAILED",
                    actor_type=request.actor_type,
                    actor_id=request.actor_id,
                    exception_id=None,
                    investigation_id=None,
                    event_summary=f"Benchmark evaluation failed for dataset {request.dataset_id}",
                    event_payload=json.dumps({
                        "evaluation_run_id": eval_run_id,
                        "error": str(e),
                    }),
                    timestamp=datetime.now(timezone.utc),
                )
            )
            session.commit()
            raise
