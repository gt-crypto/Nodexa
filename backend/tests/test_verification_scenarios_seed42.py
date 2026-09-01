"""End-to-end post-remediation verification and closure pipeline on Seed 42 across all PRD anomaly families."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from backend.data.generator.service import generate_dataset
from backend.models.enums import (
    ExceptionType,
    PolicyActionType,
    RemediationStatus,
    ExceptionState,
    VerificationStatus,
)
from backend.exceptions.service import ExceptionDetectionService
from backend.agent.service import InvestigationService
from backend.exposure.service import RiskAssessmentService
from backend.policy.service import PolicyService
from backend.remediation.service import RemediationService
from backend.verification.service import VerificationService
from backend.services.repositories import ExceptionRepository


def test_seed42_full_pipeline_verification_workflow(db_session: Session):
    """Executes full end-to-end pipeline on Seed 42: Detection -> Investigation -> Risk -> Policy -> Remediation -> Verification & Closure."""
    # 1. Dataset generation
    generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()

    # 2. Exception detection
    det_service = ExceptionDetectionService()
    det_report = det_service.detect_exceptions(session=db_session)
    db_session.commit()

    # 3. AI Investigation
    inv_service = InvestigationService()
    for exc in det_report.exceptions:
        inv_service.investigate_exception(session=db_session, exception_id=exc["exception_id"])
    db_session.commit()

    # 4. Risk Assessment
    risk_service = RiskAssessmentService()
    risk_service.assess_all_open_exceptions(session=db_session)
    db_session.commit()

    rem_service = RemediationService()
    ver_service = VerificationService()
    exc_repo = ExceptionRepository(db_session)

    # 5. GHOST SETTLEMENT: Plan -> Approve -> Execute -> Verify -> VERIFIED_CLOSED
    ghost_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.GHOST_SETTLEMENT.value)
    ghost_plan = rem_service.create_remediation_plan(
        session=db_session,
        exception_id=ghost_exc["exception_id"],
        action=PolicyActionType.REFUND.value,
        parameters={"payment_id": ghost_exc["primary_payment_id"], "amount_minor_units": ghost_exc["exposure"], "reason": "Refund ghost settlement"},
        requested_by="operator-01",
    )
    db_session.commit()

    rem_service.approve_remediation(
        session=db_session,
        action_id=ghost_plan.action_id,
        approved_by="finance-controller-01",
        decision="APPROVED",
        reason="Approved ghost refund",
    )
    db_session.commit()

    ghost_exec = rem_service.execute_remediation(session=db_session, action_id=ghost_plan.action_id)
    db_session.commit()
    assert ghost_exec.status == RemediationStatus.AWAITING_VERIFICATION.value

    ghost_ver = ver_service.verify_remediation(session=db_session, remediation_id=ghost_plan.action_id)
    db_session.commit()

    assert ghost_ver.verification_status == VerificationStatus.VERIFIED.value
    assert ghost_ver.remaining_exposure == 0
    assert ghost_ver.exposure_reduction == ghost_exc["exposure"]
    assert ghost_ver.exposure_reduction_bps == 10000

    updated_ghost_exc = exc_repo.get_exception(ghost_exc["exception_id"])
    assert updated_ghost_exc.state == ExceptionState.VERIFIED_CLOSED.value

    # 6. REFUND + CHARGEBACK DOUBLE-DIP: Plan -> Approve -> Execute -> Verify -> VERIFIED_CLOSED
    dd_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value)
    dd_plan = rem_service.create_remediation_plan(
        session=db_session,
        exception_id=dd_exc["exception_id"],
        action=PolicyActionType.REVERSE_REFUND.value,
        parameters={"payment_id": dd_exc["primary_payment_id"], "amount_minor_units": dd_exc["exposure"], "reason": "Reverse duplicate refund"},
        requested_by="operator-01",
    )
    db_session.commit()

    rem_service.approve_remediation(
        session=db_session,
        action_id=dd_plan.action_id,
        approved_by="finance-controller-01",
        decision="APPROVED",
        reason="Approved duplicate reversal",
    )
    db_session.commit()

    dd_exec = rem_service.execute_remediation(session=db_session, action_id=dd_plan.action_id)
    db_session.commit()
    assert dd_exec.status == RemediationStatus.AWAITING_VERIFICATION.value

    dd_ver = ver_service.verify_remediation(session=db_session, remediation_id=dd_plan.action_id)
    db_session.commit()

    assert dd_ver.verification_status == VerificationStatus.VERIFIED.value
    assert dd_ver.remaining_exposure == 0
    assert dd_ver.exposure_reduction == dd_exc["exposure"]
    assert dd_ver.exposure_reduction_bps == 10000

    updated_dd_exc = exc_repo.get_exception(dd_exc["exception_id"])
    assert updated_dd_exc.state == ExceptionState.VERIFIED_CLOSED.value

    # 7. SETTLEMENT SLA BREACH: Plan -> Execute -> Verify -> VERIFIED_CLOSED
    sla_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.SETTLEMENT_SLA_BREACH.value)
    sla_plan = rem_service.create_remediation_plan(
        session=db_session,
        exception_id=sla_exc["exception_id"],
        action=PolicyActionType.RECONCILE.value,
        parameters={"payment_id": sla_exc["primary_payment_id"], "reason": "Reconcile delayed settlement"},
        requested_by="operator-01",
    )
    db_session.commit()

    sla_exec = rem_service.execute_remediation(session=db_session, action_id=sla_plan.action_id)
    db_session.commit()
    assert sla_exec.status == RemediationStatus.AWAITING_VERIFICATION.value

    sla_ver = ver_service.verify_remediation(session=db_session, remediation_id=sla_plan.action_id)
    db_session.commit()

    assert sla_ver.verification_status == VerificationStatus.VERIFIED.value
    assert sla_ver.remaining_exposure == 0
    assert sla_ver.exposure_reduction_bps == 10000

    updated_sla_exc = exc_repo.get_exception(sla_exc["exception_id"])
    assert updated_sla_exc.state == ExceptionState.VERIFIED_CLOSED.value

    # 8. LEGITIMATE CASES: Must retain DIAGNOSED state, no artificial financial closure
    part_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.PARTIAL_SETTLEMENT.value)
    updated_part_exc = exc_repo.get_exception(part_exc["exception_id"])
    assert updated_part_exc.state == ExceptionState.DIAGNOSED.value

    time_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value)
    updated_time_exc = exc_repo.get_exception(time_exc["exception_id"])
    assert updated_time_exc.state == ExceptionState.DIAGNOSED.value
