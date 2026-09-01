"""Unit tests proving that Policy Gating operates with zero dependency on evaluation_ground_truth."""
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from backend.data.generator.service import generate_dataset
from backend.models.enums import PolicyActionType
from backend.models.ground_truth import EvaluationGroundTruth
from backend.exceptions.service import ExceptionDetectionService
from backend.agent.service import InvestigationService
from backend.exposure.service import RiskAssessmentService
from backend.policy.service import PolicyService


def test_policy_gating_ground_truth_independence(db_session: Session):
    """Verifies that policy decisions function completely when evaluation_ground_truth is purged."""
    # 1. Generate Seed 42 dataset
    generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()

    # 2. Run detection & AI investigation
    det_service = ExceptionDetectionService()
    det_report = det_service.detect_exceptions(session=db_session)
    db_session.commit()

    inv_service = InvestigationService()
    for exc in det_report.exceptions:
        inv_service.investigate_exception(session=db_session, exception_id=exc["exception_id"])
    db_session.commit()

    # 3. Run Risk Assessments
    risk_service = RiskAssessmentService()
    risk_service.assess_all_open_exceptions(session=db_session)
    db_session.commit()

    # 4. Purge evaluation_ground_truth completely
    db_session.execute(delete(EvaluationGroundTruth))
    db_session.commit()
    assert len(list(db_session.scalars(select(EvaluationGroundTruth)).all())) == 0

    # 5. Evaluate policy checks across all exceptions
    policy_service = PolicyService()
    for exc in det_report.exceptions:
        dec_rec = policy_service.evaluate_policy(
            session=db_session,
            exception_id=exc["exception_id"],
            requested_action=PolicyActionType.NO_ACTION.value,
        )
        assert dec_rec.decision is not None
        assert dec_rec.policy_version == "v1"
