"""End-to-end benchmark test running AI investigation across representative cases for all 6 PRD families."""
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.data.generator.service import generate_dataset
from backend.models.enums import ExceptionType, ExceptionState
from backend.models.exceptions import ExceptionRecord
from backend.exceptions.service import ExceptionDetectionService
from backend.agent.service import InvestigationService
from backend.agent.provider import RootCauseCategory


def test_investigate_all_six_prd_scenario_families_on_seed42(db_session: Session):
    """Executes AI investigations on representative cases across all six PRD exception families on Seed 42."""
    # 1. Generate full Seed 42 dataset
    generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()

    # 2. Run detection to establish deterministic exceptions
    det_service = ExceptionDetectionService()
    det_report = det_service.detect_exceptions(session=db_session)
    db_session.commit()

    inv_service = InvestigationService()

    # 3. Test Ghost Settlement Investigation
    ghost_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.GHOST_SETTLEMENT.value)
    ghost_res = inv_service.investigate_exception(session=db_session, exception_id=ghost_exc["exception_id"])
    assert ghost_res["status"] == "COMPLETED"
    ghost_out = ghost_res["structured_output"]
    assert ghost_out["root_cause_category"] == RootCauseCategory.PAYMENT_STATE_CONTRADICTION.value
    assert ghost_out["exposure_assessment"] == ghost_exc["exposure"]
    assert ghost_out["confidence"] == "HIGH"
    assert len(ghost_out["evidence"]) >= 2

    # 4. Test Refund + Chargeback Double-Dip Investigation
    dd_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value)
    dd_res = inv_service.investigate_exception(session=db_session, exception_id=dd_exc["exception_id"])
    assert dd_res["status"] == "COMPLETED"
    dd_out = dd_res["structured_output"]
    assert dd_out["root_cause_category"] == RootCauseCategory.REFUND_CHARGEBACK_OVERLAP.value
    assert dd_out["exposure_assessment"] == dd_exc["exposure"]
    assert dd_out["confidence"] == "HIGH"

    # 5. Test Settlement SLA Breach Investigation
    sla_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.SETTLEMENT_SLA_BREACH.value)
    sla_res = inv_service.investigate_exception(session=db_session, exception_id=sla_exc["exception_id"])
    assert sla_res["status"] == "COMPLETED"
    sla_out = sla_res["structured_output"]
    assert sla_out["root_cause_category"] == RootCauseCategory.SETTLEMENT_TIMING.value
    assert sla_out["exposure_assessment"] == sla_exc["exposure"]

    # 6. Test Legitimate Partial Settlement Investigation
    part_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.PARTIAL_SETTLEMENT.value)
    part_res = inv_service.investigate_exception(session=db_session, exception_id=part_exc["exception_id"])
    assert part_res["status"] == "COMPLETED"
    part_out = part_res["structured_output"]
    assert part_out["exposure_assessment"] == 0
    assert "legitimate" in part_out["root_cause"].lower()

    # 7. Test Missing & Unallocated Settlement Investigation
    miss_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value and e["sub_type"] == "MISSING_SETTLEMENT")
    miss_res = inv_service.investigate_exception(session=db_session, exception_id=miss_exc["exception_id"])
    assert miss_res["status"] == "COMPLETED"
    miss_out = miss_res["structured_output"]
    assert miss_out["root_cause_category"] == RootCauseCategory.SETTLEMENT_PROCESSING_FAILURE.value
    assert miss_out["exposure_assessment"] == miss_exc["exposure"]

    unalloc_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value and e["sub_type"] == "UNALLOCATED_SETTLEMENT")
    unalloc_res = inv_service.investigate_exception(session=db_session, exception_id=unalloc_exc["exception_id"])
    assert unalloc_res["status"] == "COMPLETED"
    unalloc_out = unalloc_res["structured_output"]
    assert unalloc_out["root_cause_category"] == RootCauseCategory.UNALLOCATED_FUNDS.value
    assert unalloc_out["exposure_assessment"] == unalloc_exc["exposure"]
    assert unalloc_out["confidence"] == "MEDIUM"  # Ambiguity preserved

    # 8. Test Legitimate Timing Exception Investigation
    time_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value)
    time_res = inv_service.investigate_exception(session=db_session, exception_id=time_exc["exception_id"])
    assert time_res["status"] == "COMPLETED"
    time_out = time_res["structured_output"]
    assert time_out["exposure_assessment"] == 0
    assert "legitimate" in time_out["root_cause"].lower()

    investigated_ids = [
        ghost_exc["exception_id"],
        dd_exc["exception_id"],
        sla_exc["exception_id"],
        part_exc["exception_id"],
        miss_exc["exception_id"],
        unalloc_exc["exception_id"],
        time_exc["exception_id"],
    ]

    # Verify investigated exceptions are in DIAGNOSED state
    for exc_id in investigated_ids:
        rec = db_session.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == exc_id)).first()
        assert rec.state == ExceptionState.DIAGNOSED.value

    # Investigate remaining exceptions to verify complete batch convergence
    for exc_summary in det_report.exceptions:
        if exc_summary["exception_id"] not in investigated_ids:
            inv_service.investigate_exception(session=db_session, exception_id=exc_summary["exception_id"])

    all_exc_records = list(db_session.scalars(select(ExceptionRecord)).all())
    assert len(all_exc_records) == 14
    assert all(r.state == ExceptionState.DIAGNOSED.value for r in all_exc_records)
