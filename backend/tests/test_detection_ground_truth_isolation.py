"""Unit test proving that exception detection remains operationally functional without access to evaluation_ground_truth, proving ground-truth independence."""
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from backend.data.generator.service import generate_dataset
from backend.models.ground_truth import EvaluationGroundTruth
from backend.exceptions.service import ExceptionDetectionService
from backend.models.enums import ExceptionType


def test_detection_operates_with_zero_ground_truth_dependency(db_session: Session):
    """Verifies that exception detection remains operationally functional without access to evaluation_ground_truth, proving ground-truth independence."""
    # 1. Generate standard Seed 42 dataset
    generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()

    # 2. Verify ground truth was initially populated by generator
    initial_gt = list(db_session.scalars(select(EvaluationGroundTruth)).all())
    assert len(initial_gt) > 0

    # 3. Purge all records from evaluation_ground_truth
    db_session.execute(delete(EvaluationGroundTruth))
    db_session.commit()

    # Confirm ground truth is now 100% empty
    assert len(list(db_session.scalars(select(EvaluationGroundTruth)).all())) == 0

    # 4. Run operational exception detection
    service = ExceptionDetectionService()
    report = service.detect_exceptions(session=db_session)

    # 5. Assert detection discovered all 14 expected anomaly/edge cases without ground truth
    assert report.total_detected_count == 14
    assert report.exception_type_breakdown.get(ExceptionType.GHOST_SETTLEMENT.value) == 2
    assert report.exception_type_breakdown.get(ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value) == 2
    assert report.exception_type_breakdown.get(ExceptionType.SETTLEMENT_SLA_BREACH.value) == 2
    assert report.exception_type_breakdown.get(ExceptionType.PARTIAL_SETTLEMENT.value) == 2
    assert report.exception_type_breakdown.get(ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value) == 4
    assert report.exception_type_breakdown.get(ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value) == 2
