"""Unit test proving that AI investigation remains operationally functional without access to evaluation_ground_truth."""
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from backend.data.generator.service import generate_dataset
from backend.models.ground_truth import EvaluationGroundTruth
from backend.exceptions.service import ExceptionDetectionService
from backend.agent.service import InvestigationService
from backend.models.enums import ExceptionState


def test_ai_investigation_operates_with_zero_ground_truth_dependency(db_session: Session):
    """Verifies that AI investigation functions with ground-truth independence when evaluation_ground_truth is purged."""
    # 1. Generate standard Seed 42 dataset
    generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()

    # 2. Run deterministic detection
    det_service = ExceptionDetectionService()
    det_report = det_service.detect_exceptions(session=db_session)
    db_session.commit()
    assert det_report.total_detected_count == 14

    # 3. Purge all records from evaluation_ground_truth
    db_session.execute(delete(EvaluationGroundTruth))
    db_session.commit()
    assert len(list(db_session.scalars(select(EvaluationGroundTruth)).all())) == 0

    # 4. Run AI investigation on all detected exceptions
    inv_service = InvestigationService()
    for exc_summary in det_report.exceptions:
        exc_id = exc_summary["exception_id"]
        res = inv_service.investigate_exception(session=db_session, exception_id=exc_id)
        assert res["status"] == "COMPLETED"
        assert res["structured_output"] is not None
        assert res["structured_output"]["investigation_status"] == "SUCCESS"
