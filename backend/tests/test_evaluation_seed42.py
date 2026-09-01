"""Comprehensive end-to-end Benchmark Evaluation on the Seed-42 Dataset."""
import pytest
from sqlalchemy.orm import Session

from backend.data.generator.service import generate_dataset
from backend.exceptions.service import ExceptionDetectionService
from backend.agent.service import InvestigationService
from backend.exposure.service import RiskAssessmentService
from backend.policy.service import PolicyService
from backend.remediation.service import RemediationService
from backend.verification.service import VerificationService
from backend.evaluation.service import BenchmarkEvaluationService
from backend.evaluation.models import EvaluationRunRequest


def test_seed42_full_benchmark_evaluation(db_session: Session):
    """Executes the complete Seed 42 benchmark and evaluates accuracy across all pipeline stages."""
    # 1. Generate standard Seed 42 dataset (60 cases / 270 records / 14 anomalies)
    summary = generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()
    dataset_id = summary["dataset_id"]

    # 2. Run Detection
    det_service = ExceptionDetectionService()
    det_report = det_service.detect_exceptions(session=db_session)
    db_session.commit()
    assert det_report.total_detected_count == 14

    # 3. Run Investigation
    agent_service = InvestigationService()
    for exc in det_report.exceptions:
        agent_service.investigate_exception(session=db_session, exception_id=exc["exception_id"])
    db_session.commit()

    # 4. Run Exposure & Risk
    risk_service = RiskAssessmentService()
    risk_service.assess_all_open_exceptions(session=db_session)
    db_session.commit()

    # 5. Run Policy Gating
    policy_service = PolicyService()
    for exc in det_report.exceptions:
        policy_service.evaluate_policy(
            session=db_session,
            exception_id=exc["exception_id"],
            requested_action="INVESTIGATE",
        )
    db_session.commit()

    # 6. Run Remediation & Verification for Remediable Anomalies
    rem_service = RemediationService()
    ver_service = VerificationService()

    # Ghost settlements
    for exc in det_report.exceptions:
        if exc["exception_type"] == "GHOST_SETTLEMENT":
            plan = rem_service.create_remediation_plan(
                session=db_session,
                exception_id=exc["exception_id"],
                action="REFUND",
                parameters={"payment_id": exc["primary_payment_id"], "amount_minor_units": exc["exposure"], "reason": "Refund ghost settlement"},
                requested_by="operator-01",
            )
            rem_service.approve_remediation(session=db_session, action_id=plan.action_id, approved_by="finance-01", decision="APPROVED", reason="Approved ghost refund")
            rem_service.execute_remediation(session=db_session, action_id=plan.action_id)
            ver_service.verify_remediation(session=db_session, remediation_id=plan.action_id)

        elif exc["exception_type"] == "REFUND_CHARGEBACK_DOUBLE_DIP":
            plan = rem_service.create_remediation_plan(
                session=db_session,
                exception_id=exc["exception_id"],
                action="REVERSE_REFUND",
                parameters={"payment_id": exc["primary_payment_id"], "amount_minor_units": exc["exposure"], "reason": "Reverse duplicate refund"},
                requested_by="operator-01",
            )
            rem_service.approve_remediation(session=db_session, action_id=plan.action_id, approved_by="risk-01", decision="APPROVED", reason="Approved double dip reverse refund")
            rem_service.execute_remediation(session=db_session, action_id=plan.action_id)
            ver_service.verify_remediation(session=db_session, remediation_id=plan.action_id)

        elif exc["exception_type"] == "SETTLEMENT_SLA_BREACH":
            from backend.controls.state_machine import transition_exception_state, TransitionActorType
            from backend.models.enums import ExceptionState
            transition_exception_state(
                session=db_session,
                exception_id=exc["exception_id"],
                to_state=ExceptionState.FAILED_ESCALATED,
                reason="SLA breach escalated to partner operations",
                actor_type=TransitionActorType.SYSTEM,
                actor_id="sla-escalator",
            )

    db_session.commit()

    # 7. Execute Benchmark Evaluation Run
    eval_service = BenchmarkEvaluationService()
    request = EvaluationRunRequest(dataset_id=dataset_id, force_rerun=True)
    report = eval_service.run_benchmark(session=db_session, request=request)

    # 7. Validate Benchmark Outcomes
    assert report.run.status == "COMPLETED"
    assert report.run.total_ground_truth_cases == 14
    assert report.run.total_predictions == 14
    assert report.run.true_positives == 14
    assert report.run.false_positives == 0
    assert report.run.false_negatives == 0

    # Detection metrics must be 100% (10000 bps)
    assert report.run.precision == 1.0
    assert report.run.precision_bps == 10000
    assert report.run.recall == 1.0
    assert report.run.recall_bps == 10000
    assert report.run.f1_score == 1.0
    assert report.run.f1_score_bps == 10000

    # Financial Exposure Accuracy
    exp_acc = report.exposure_accuracy
    assert exp_acc.exact_matches >= 12
    assert exp_acc.exact_match_rate >= 0.85
    assert exp_acc.zero_exposure_cases_verified == 4  # 2 partial + 2 timing

    # Legitimate Case Protection
    legit = report.legitimate_cases_summary
    assert legit["total_legitimate_cases"] == 4
    assert legit["legitimate_correct_count"] == 4
    assert legit["legitimate_false_positive_count"] == 0
    assert legit["all_zero_exposure_verified"] is True

    # Normal Transaction Testing
    normal = report.normal_cases_summary
    assert normal["normal_false_positive_count"] == 0
    assert normal["zero_normal_false_positives_verified"] is True

    # Safety Gating
    print("\nSAFETY FAILURE REASONS:", report.run.safety_failure_reasons)
    print("CRITICAL VIOLATIONS:", report.critical_safety_violations)
    assert report.run.safety_status == "PASSED"
    assert report.run.critical_safety_failure is False
    assert len(report.critical_safety_violations) == 0

    # Overall Score
    assert report.run.overall_score >= 80
    assert report.run.scores.detection == 25
    assert report.run.scores.policy == 10
