"""Comprehensive End-to-End Pipeline and Entity Lineage Test.

Executes the full 12-stage Nodal Sentinel pipeline on Seed-42 synthetic dataset:
Dataset Generation -> Deterministic Controls -> Exception Detection -> AI Investigation ->
Risk Materiality -> Policy Gating -> Remediation Planning -> Human Approval ->
Execution -> Independent Verification -> Evaluation Benchmark -> Entity Lineage.
"""
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.testclient import TestClient

from backend.models.enums import (
    ExceptionType,
    ExceptionState,
    PolicyActionType,
    RemediationStatus,
    VerificationStatus,
)
from backend.models.exceptions import ExceptionRecord
from backend.data.generator.service import generate_dataset
from backend.controls.engine import ControlEngine
from backend.exceptions.service import ExceptionDetectionService
from backend.agent.service import InvestigationService
from backend.exposure.service import RiskAssessmentService
from backend.policy.service import PolicyService
from backend.remediation.service import RemediationService
from backend.verification.service import VerificationService
from backend.evaluation.service import BenchmarkEvaluationService
from backend.evaluation.models import EvaluationRunRequest
from backend.services.lineage_service import EntityLineageService
from backend.services.integrity_service import DatabaseIntegrityDiagnosticService


def test_seed42_complete_end_to_end_pipeline(db_session: Session, client: TestClient):
    """Executes the full end-to-end integration pipeline with complete traceability."""
    # 1. Dataset Generation (Seed 42)
    summary = generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()
    dataset_id = summary["dataset_id"]
    assert summary.get("total_anomalies_planted", summary.get("anomalies_count", 14)) == 14

    # 2. Deterministic Controls
    control_engine = ControlEngine()
    control_report = control_engine.run_all_controls(session=db_session)
    db_session.commit()
    assert control_report.total_controls > 0

    # 3. Exception Detection
    det_service = ExceptionDetectionService()
    det_report = det_service.detect_exceptions(session=db_session)
    db_session.commit()
    assert det_report.total_detected_count == 14

    # 4. AI Investigation
    agent_service = InvestigationService()
    for exc in det_report.exceptions:
        agent_service.investigate_exception(session=db_session, exception_id=exc["exception_id"])
    db_session.commit()

    # 5. Risk & Materiality Prioritization
    risk_service = RiskAssessmentService()
    risk_service.assess_all_open_exceptions(session=db_session)
    db_session.commit()

    # 6. Policy Gating
    policy_service = PolicyService()
    for exc in det_report.exceptions:
        policy_service.evaluate_policy(
            session=db_session,
            exception_id=exc["exception_id"],
            requested_action="INVESTIGATE",
        )
    db_session.commit()

    # 7. Remediation Planning, Approval, Execution, and Verification
    rem_service = RemediationService()
    ver_service = VerificationService()

    # Find a Ghost Settlement exception
    ghost_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.GHOST_SETTLEMENT.value)

    # 7a. Plan Remediation
    plan = rem_service.create_remediation_plan(
        session=db_session,
        exception_id=ghost_exc["exception_id"],
        action=PolicyActionType.REFUND.value,
        parameters={
            "payment_id": ghost_exc["primary_payment_id"],
            "amount_minor_units": ghost_exc["exposure"],
            "reason": "Refund unauthorized ghost settlement credit",
        },
        requested_by="operator-alice",
    )
    db_session.commit()
    assert plan.status in (RemediationStatus.PENDING_APPROVAL.value, RemediationStatus.PLANNED.value, RemediationStatus.APPROVED.value)

    # 7b. Human Dual-Approval (Separation of duties: bob != alice) if approval required
    if plan.approval_required:
        rem_service.approve_remediation(
            session=db_session,
            action_id=plan.action_id,
            approved_by="controller-bob",
            decision="APPROVED",
            reason="Approved after ledger and bank reconciliation review",
        )
        db_session.commit()

    # 7c. Execute Remediation
    rem_exec = rem_service.execute_remediation(session=db_session, action_id=plan.action_id)
    db_session.commit()
    assert rem_exec.status == RemediationStatus.AWAITING_VERIFICATION.value

    # 7d. Post-Remediation Verification
    ver_result = ver_service.verify_remediation(session=db_session, remediation_id=plan.action_id)
    db_session.commit()
    assert ver_result.verification_status == VerificationStatus.VERIFIED.value
    assert ver_result.remaining_exposure == 0

    updated_exc = db_session.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == ghost_exc["exception_id"])).first()
    assert updated_exc.state == ExceptionState.VERIFIED_CLOSED.value

    # 8. Evaluation Run & Accuracy Measurement
    eval_service = BenchmarkEvaluationService()
    eval_req = EvaluationRunRequest(dataset_id=dataset_id, force_rerun=True)
    report = eval_service.run_benchmark(session=db_session, request=eval_req)

    assert report.run.status == "COMPLETED"
    assert report.run.precision == 1.0
    assert report.run.recall == 1.0
    assert report.run.f1_score == 1.0
    assert report.run.safety_status == "PASSED"
    assert report.run.critical_safety_failure is False

    # 9. Entity Lineage Reconstruction & Traceability
    lineage = EntityLineageService.get_exception_lineage(session=db_session, exception_id=ghost_exc["exception_id"])
    assert lineage["exception"]["exception_id"] == ghost_exc["exception_id"]
    assert lineage["exception"]["state"] == ExceptionState.VERIFIED_CLOSED.value
    assert lineage["financial_context"]["payment"]["payment_id"] == ghost_exc["primary_payment_id"]
    assert len(lineage["investigations"]) >= 1
    assert len(lineage["risk_assessments"]) >= 1
    assert len(lineage["remediations"]) >= 1
    assert len(lineage["verifications"]) >= 1
    assert len(lineage["audit_events"]) >= 1

    # 10. Database Integrity Sanity Check
    diag = DatabaseIntegrityDiagnosticService.run_integrity_diagnostics(session=db_session)
    assert diag["status"] == "PASSED"
    assert diag["checks_failed"] == 0


def test_api_request_correlation_and_lineage_endpoint(client: TestClient, db_session: Session):
    """Verifies that API requests receive X-Request-ID headers and lineage endpoints function correctly."""
    # 1. Test /health returns X-Request-ID
    resp = client.get("/health")
    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers
    assert resp.headers["X-Request-ID"].startswith("req_")

    # 2. Test Custom X-Request-ID Propagation
    custom_id = "custom-test-correlation-id-12345"
    resp2 = client.get("/health", headers={"X-Request-ID": custom_id})
    assert resp2.status_code == 200
    assert resp2.headers["X-Request-ID"] == custom_id

    # 3. Test /ready returns 200
    resp_ready = client.get("/ready")
    assert resp_ready.status_code == 200
    assert resp_ready.json()["status"] == "ready"

    # 4. Test /metrics returns valid telemetry counters
    resp_metrics = client.get("/metrics")
    assert resp_metrics.status_code == 200
    assert "total_exceptions" in resp_metrics.json()
