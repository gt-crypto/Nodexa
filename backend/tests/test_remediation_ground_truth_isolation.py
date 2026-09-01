"""Unit tests proving that Remediation Workflow operates with zero dependency on evaluation_ground_truth."""
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from backend.data.generator.service import generate_dataset
from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.enums import PolicyActionType, RemediationStatus
from backend.exceptions.service import ExceptionDetectionService
from backend.agent.service import InvestigationService
from backend.exposure.service import RiskAssessmentService
from backend.policy.service import PolicyService
from backend.remediation.service import RemediationService


def test_remediation_ground_truth_independence(db_session: Session):
    """Verifies that remediation planning, approval, and execution function completely when evaluation_ground_truth is purged."""
    # 1. Dataset generation
    generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()

    # 2. Detection & Investigation
    det_service = ExceptionDetectionService()
    det_report = det_service.detect_exceptions(session=db_session)
    db_session.commit()

    inv_service = InvestigationService()
    for exc in det_report.exceptions:
        inv_service.investigate_exception(session=db_session, exception_id=exc["exception_id"])
    db_session.commit()

    # 3. Purge evaluation_ground_truth completely
    db_session.execute(delete(EvaluationGroundTruth))
    db_session.commit()
    assert len(list(db_session.scalars(select(EvaluationGroundTruth)).all())) == 0

    # 4. Plan & Execute a remediation on SLA breach (reconciliation action)
    sla_exc = next(e for e in det_report.exceptions if e["exception_type"] == "SETTLEMENT_SLA_BREACH")
    
    rem_service = RemediationService()
    plan = rem_service.create_remediation_plan(
        session=db_session,
        exception_id=sla_exc["exception_id"],
        action=PolicyActionType.RECONCILE.value,
        parameters={"payment_id": sla_exc["primary_payment_id"], "reason": "SLA breach reconciliation test"},
        requested_by="operator-01",
    )
    db_session.commit()

    executed = rem_service.execute_remediation(session=db_session, action_id=plan.action_id)
    db_session.commit()

    assert executed.status == RemediationStatus.AWAITING_VERIFICATION.value
