"""End-to-end verification of risk scoring and materiality across all 6 PRD families on Seed 42."""
import json
import pytest
from sqlalchemy.orm import Session

from backend.data.generator.service import generate_dataset
from backend.models.enums import ExceptionType, PriorityLevel, EscalationRecommendation, MaterialityLevel, ExposureType
from backend.exceptions.service import ExceptionDetectionService
from backend.agent.service import InvestigationService
from backend.exposure.service import RiskAssessmentService


def test_seed42_full_pipeline_risk_assessments(db_session: Session):
    """Executes full pipeline on Seed 42 and validates risk & exposure assessment across all anomaly families."""
    # 1. Generate Prompt 2 dataset
    generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()

    # 2. Run Prompt 4 exception detection
    det_service = ExceptionDetectionService()
    det_report = det_service.detect_exceptions(session=db_session)
    db_session.commit()

    # 3. Run Prompt 5 AI investigations
    inv_service = InvestigationService()
    for exc_summary in det_report.exceptions:
        inv_service.investigate_exception(session=db_session, exception_id=exc_summary["exception_id"])
    db_session.commit()

    # 4. Run Prompt 6 Risk Assessment
    risk_service = RiskAssessmentService()
    assessments = risk_service.assess_all_open_exceptions(session=db_session)
    db_session.commit()

    ass_map = {a.exception_id: a for a in assessments}

    # 5. Verify Ghost Settlement
    ghost_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.GHOST_SETTLEMENT.value)
    ghost_ra = ass_map[ghost_exc["exception_id"]]
    assert ghost_ra.deterministic_exposure == ghost_exc["exposure"]
    assert ghost_ra.exposure_type == ExposureType.FUNDS_AT_RISK.value
    assert ghost_ra.materiality == MaterialityLevel.MATERIAL.value
    assert ghost_ra.priority == PriorityLevel.P1.value
    assert ghost_ra.escalation == EscalationRecommendation.IMMEDIATE_ESCALATION.value
    assert ghost_ra.risk_score >= 75

    # 6. Verify Refund + Chargeback Double-Dip
    dd_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value)
    dd_ra = ass_map[dd_exc["exception_id"]]
    assert dd_ra.deterministic_exposure == dd_exc["exposure"]
    assert dd_ra.exposure_type == ExposureType.DIRECT_FINANCIAL_LOSS.value
    assert dd_ra.materiality == MaterialityLevel.MATERIAL.value
    assert dd_ra.priority in (PriorityLevel.P1.value, PriorityLevel.P2.value)
    assert dd_ra.escalation == EscalationRecommendation.RISK_REVIEW.value

    # 7. Verify Settlement SLA Breach
    sla_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.SETTLEMENT_SLA_BREACH.value)
    sla_ra = ass_map[sla_exc["exception_id"]]
    assert sla_ra.deterministic_exposure == sla_exc["exposure"]
    assert sla_ra.exposure_type == ExposureType.SLA_DELAY_IMPACT.value
    assert sla_ra.materiality == MaterialityLevel.HIGH.value
    sla_bd = json.loads(sla_ra.score_breakdown or "{}")
    assert sla_bd["sla_score"] == 10

    # 8. Verify Missing Settlement
    miss_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value and e["sub_type"] == "MISSING_SETTLEMENT")
    miss_ra = ass_map[miss_exc["exception_id"]]
    assert miss_ra.deterministic_exposure == miss_exc["exposure"]
    assert miss_ra.exposure_type == ExposureType.FUNDS_AT_RISK.value
    assert miss_ra.materiality == MaterialityLevel.HIGH.value

    # 9. Verify Unallocated Settlement
    unalloc_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value and e["sub_type"] == "UNALLOCATED_SETTLEMENT")
    unalloc_ra = ass_map[unalloc_exc["exception_id"]]
    assert unalloc_ra.deterministic_exposure == unalloc_exc["exposure"]
    assert unalloc_ra.exposure_type == ExposureType.FUNDS_AT_RISK.value
    assert unalloc_ra.escalation == EscalationRecommendation.FINANCE_REVIEW.value
    unalloc_bd = json.loads(unalloc_ra.score_breakdown or "{}")
    assert unalloc_bd["allocation_risk_score"] == 5

    # 10. Verify Legitimate Partial Settlement (MUST BE ZERO RISK)
    part_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.PARTIAL_SETTLEMENT.value)
    part_ra = ass_map[part_exc["exception_id"]]
    assert part_ra.deterministic_exposure == 0
    assert part_ra.exposure_type == ExposureType.NO_FINANCIAL_EXPOSURE.value
    assert part_ra.materiality == MaterialityLevel.NONE.value
    assert part_ra.risk_score == 0
    assert part_ra.priority == PriorityLevel.P4.value
    assert part_ra.escalation == EscalationRecommendation.NO_ESCALATION.value

    # 11. Verify Legitimate Timing Exception (MUST BE ZERO RISK)
    time_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value)
    time_ra = ass_map[time_exc["exception_id"]]
    assert time_ra.deterministic_exposure == 0
    assert time_ra.exposure_type == ExposureType.NO_FINANCIAL_EXPOSURE.value
    assert time_ra.materiality == MaterialityLevel.NONE.value
    assert time_ra.risk_score == 0
    assert time_ra.priority == PriorityLevel.P4.value
    assert time_ra.escalation == EscalationRecommendation.NO_ESCALATION.value
