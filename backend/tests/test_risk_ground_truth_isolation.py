"""Unit tests proving that Risk and Exposure calculations operate with zero dependency on evaluation_ground_truth."""
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from backend.data.generator.service import generate_dataset
from backend.models.ground_truth import EvaluationGroundTruth
from backend.exceptions.service import ExceptionDetectionService
from backend.agent.service import InvestigationService
from backend.exposure.service import RiskAssessmentService
from backend.exposure.prioritization import get_prioritized_risk_queue, get_account_risk_summary


def test_risk_prioritization_ground_truth_independence(db_session: Session):
    """Verifies that risk assessment and queue prioritization function normally when evaluation_ground_truth is purged."""
    # 1. Generate full Seed 42 dataset
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

    # 3. Purge all records from evaluation_ground_truth
    db_session.execute(delete(EvaluationGroundTruth))
    db_session.commit()
    assert len(list(db_session.scalars(select(EvaluationGroundTruth)).all())) == 0

    # 4. Run Risk Assessments across all exceptions
    risk_service = RiskAssessmentService()
    assessments = risk_service.assess_all_open_exceptions(session=db_session)
    db_session.commit()

    assert len(assessments) == det_report.total_detected_count
    assert all(a.risk_score >= 0 for a in assessments)

    # 5. Prioritized queue and account summary remain fully operational
    queue, count = get_prioritized_risk_queue(session=db_session)
    assert count == det_report.total_detected_count
    assert len(queue) == count

    summary = get_account_risk_summary(session=db_session)
    assert summary.total_open_exposure > 0
    assert summary.total_exceptions_count == count
