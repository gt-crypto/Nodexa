"""Unit tests for deterministic risk scoring formula, priority boundaries, and queue ordering."""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session

from backend.models.enums import PriorityLevel, EscalationRecommendation, ExceptionSeverity
from backend.models.exceptions import ExceptionRecord
from backend.exposure.models import RiskFactors
from backend.exposure.scoring import (
    calculate_risk_score,
    determine_priority,
    determine_escalation,
    generate_risk_explanation,
)
from backend.exposure.service import RiskAssessmentService
from backend.exposure.prioritization import get_prioritized_risk_queue


def test_risk_score_calculation_reproducibility():
    """Verifies that 0-100 risk score and breakdown are exactly reproducible from factors."""
    factors = RiskFactors(
        exposure_amount=5000000,
        severity_level="CRITICAL",
        control_failure_count=2,
        investigation_confidence="HIGH",
        affected_record_count=2,
        sla_breached=False,
        ledger_contradiction=True,
        is_unallocated=False,
        is_double_dip=False,
        age_minutes=30,
    )

    score, breakdown = calculate_risk_score(factors)
    # Expected:
    # exposure (25) + severity (20) + controls (14) + confidence (10) + complexity (3) + sla (0) + ledger (5) + alloc (0) = 77
    assert score == 77
    assert breakdown["financial_exposure_score"] == 25
    assert breakdown["severity_score"] == 20
    assert breakdown["control_failure_score"] == 14
    assert breakdown["confidence_score"] == 10
    assert breakdown["complexity_score"] == 3
    assert breakdown["ledger_risk_score"] == 5
    assert breakdown["total"] == 77


def test_legitimate_zero_exposure_case_risk_score_and_priority():
    """Verifies that legitimate observations with zero exposure evaluate strictly to 0 score and P4."""
    factors = RiskFactors(
        exposure_amount=0,
        severity_level="LOW",
        control_failure_count=0,
        investigation_confidence="HIGH",
        affected_record_count=2,
        sla_breached=False,
        ledger_contradiction=False,
        is_unallocated=False,
        is_double_dip=False,
        age_minutes=5,
    )

    score, breakdown = calculate_risk_score(factors)
    assert score == 0
    assert breakdown["total"] == 0

    priority = determine_priority(risk_score=score, exposure=0)
    assert priority == PriorityLevel.P4.value

    escalation = determine_escalation(
        exception_type="PARTIAL_SETTLEMENT",
        severity="LOW",
        priority=priority,
        exposure=0,
        root_cause_category="OTHER",
    )
    assert escalation == EscalationRecommendation.NO_ESCALATION.value


def test_priority_score_boundaries():
    """Verifies priority level mapping across configured score thresholds."""
    assert determine_priority(100, exposure=1000) == PriorityLevel.P1.value
    assert determine_priority(75, exposure=1000) == PriorityLevel.P1.value
    assert determine_priority(74, exposure=1000) == PriorityLevel.P2.value
    assert determine_priority(50, exposure=1000) == PriorityLevel.P2.value
    assert determine_priority(49, exposure=1000) == PriorityLevel.P3.value
    assert determine_priority(25, exposure=1000) == PriorityLevel.P3.value
    assert determine_priority(24, exposure=1000) == PriorityLevel.P4.value
    assert determine_priority(0, exposure=1000) == PriorityLevel.P4.value


def test_deterministic_explanation_generation():
    """Verifies natural-language risk explanation generation without LLM reliance."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-TEST-EXP-1",
        exception_type="GHOST_SETTLEMENT",
        severity="CRITICAL",
        exposure=5000000,
        detected_at=now,
        created_at=now,
    )
    breakdown = {"financial_exposure_score": 25, "severity_score": 20, "ledger_risk_score": 5}
    exp = generate_risk_explanation(
        exception=exc,
        materiality="MATERIAL",
        priority="P1",
        score=77,
        breakdown=breakdown,
        escalation="IMMEDIATE_ESCALATION",
        root_cause_category="PAYMENT_STATE_CONTRADICTION",
    )
    assert "Priority P1" in exp
    assert "77/100" in exp
    assert "₹50,000.00" in exp
    assert "CRITICAL" in exp
    assert "PAYMENT_STATE_CONTRADICTION" in exp
    assert "IMMEDIATE_ESCALATION" in exp


def test_prioritized_queue_deterministic_tie_breaking(db_session: Session):
    """Verifies that the queue sorts deterministically using priority, score, exposure, severity, and detected_at."""
    now = datetime.now(timezone.utc)
    
    # 1. Item with P1 (Higher priority)
    exc1 = ExceptionRecord(
        exception_id="EXC-P1-HIGH",
        exception_type="GHOST_SETTLEMENT",
        severity="CRITICAL",
        exposure=5000000,
        detected_at=now - timedelta(hours=2),
        created_at=now,
    )
    # 2. Item with P2, higher score
    exc2 = ExceptionRecord(
        exception_id="EXC-P2-HIGH-SCORE",
        exception_type="REFUND_CHARGEBACK_DOUBLE_DIP",
        severity="HIGH",
        exposure=3000000,
        detected_at=now - timedelta(hours=3),
        created_at=now,
    )
    # 3. Item with P4, zero exposure
    exc3 = ExceptionRecord(
        exception_id="EXC-P4-LEGIT",
        exception_type="PARTIAL_SETTLEMENT",
        severity="LOW",
        exposure=0,
        detected_at=now - timedelta(hours=4),
        created_at=now,
    )

    db_session.add_all([exc1, exc2, exc3])
    db_session.commit()

    service = RiskAssessmentService()
    service.assess_all_open_exceptions(db_session)
    db_session.commit()

    queue, count = get_prioritized_risk_queue(db_session)
    assert count == 3
    # First item must be P1
    assert queue[0].exception_id == "EXC-P1-HIGH"
    assert queue[0].priority == "P1"

    # Second item must be P2
    assert queue[1].exception_id == "EXC-P2-HIGH-SCORE"
    assert queue[1].priority == "P2"

    # Third item must be P4
    assert queue[2].exception_id == "EXC-P4-LEGIT"
    assert queue[2].priority == "P4"
