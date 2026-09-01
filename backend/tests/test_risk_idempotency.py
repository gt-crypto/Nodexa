"""Unit tests for RiskAssessment idempotency and historical audit preservation."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.exceptions import ExceptionRecord
from backend.models.risk import RiskAssessment
from backend.exposure.service import RiskAssessmentService


def test_risk_assessment_idempotency(db_session: Session):
    """Verifies that evaluating risk multiple times with unchanged inputs is strictly idempotent."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-IDEMP-1",
        exception_type="GHOST_SETTLEMENT",
        severity="CRITICAL",
        exposure=4500000,
        detected_at=now,
        created_at=now,
    )
    db_session.add(exc)
    db_session.commit()

    service = RiskAssessmentService()

    # 1. First assessment
    ra1 = service.assess_exception_risk(session=db_session, exception_id="EXC-IDEMP-1")
    db_session.commit()
    id1 = ra1.assessment_id
    score1 = ra1.risk_score

    # 2. Second assessment with unchanged inputs
    ra2 = service.assess_exception_risk(session=db_session, exception_id="EXC-IDEMP-1")
    db_session.commit()
    id2 = ra2.assessment_id
    score2 = ra2.risk_score

    assert id1 == id2
    assert score1 == score2

    # Verify only 1 record in DB
    all_runs = list(db_session.scalars(select(RiskAssessment).where(RiskAssessment.exception_id == "EXC-IDEMP-1")).all())
    assert len(all_runs) == 1


def test_force_recalculate_preserves_historical_records(db_session: Session):
    """Verifies that forced recalculation creates a new version while preserving historical assessments."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-HIST-1",
        exception_type="REFUND_CHARGEBACK_DOUBLE_DIP",
        severity="HIGH",
        exposure=3000000,
        detected_at=now,
        created_at=now,
    )
    db_session.add(exc)
    db_session.commit()

    service = RiskAssessmentService()

    # First run
    ra1 = service.assess_exception_risk(session=db_session, exception_id="EXC-HIST-1")
    db_session.commit()

    # Forced second run
    ra2 = service.assess_exception_risk(session=db_session, exception_id="EXC-HIST-1", force_recalculate=True)
    db_session.commit()

    assert ra1.assessment_id != ra2.assessment_id
    all_runs = list(db_session.scalars(select(RiskAssessment).where(RiskAssessment.exception_id == "EXC-HIST-1")).all())
    assert len(all_runs) == 2
