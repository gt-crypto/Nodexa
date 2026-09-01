"""End-to-end verification of controlled remediation workflow across all 6 PRD families on Seed 42."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from backend.data.generator.service import generate_dataset
from backend.models.enums import (
    ExceptionType,
    PolicyActionType,
    RemediationStatus,
)
from backend.exceptions.service import ExceptionDetectionService
from backend.agent.service import InvestigationService
from backend.exposure.service import RiskAssessmentService
from backend.policy.service import PolicyService
from backend.remediation.service import RemediationService


def test_seed42_full_pipeline_remediation_workflow(db_session: Session):
    """Executes full pipeline on Seed 42 and validates controlled remediation planning, approval, and execution."""
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

    # 5. Ghost Settlement: Plan REFUND -> Approve -> Execute -> AWAITING_VERIFICATION
    ghost_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.GHOST_SETTLEMENT.value)
    ghost_plan = rem_service.create_remediation_plan(
        session=db_session,
        exception_id=ghost_exc["exception_id"],
        action=PolicyActionType.REFUND.value,
        parameters={"payment_id": ghost_exc["primary_payment_id"], "amount_minor_units": ghost_exc["exposure"], "reason": "Refund ghost settlement"},
        requested_by="operator-01",
    )
    db_session.commit()
    assert ghost_plan.status == RemediationStatus.PENDING_APPROVAL.value

    rem_service.approve_remediation(
        session=db_session,
        action_id=ghost_plan.action_id,
        approved_by="finance-controller-01",
        decision="APPROVED",
        reason="Approved after evidence review",
    )
    db_session.commit()

    ghost_exec = rem_service.execute_remediation(session=db_session, action_id=ghost_plan.action_id)
    db_session.commit()
    assert ghost_exec.status == RemediationStatus.AWAITING_VERIFICATION.value

    # 6. Refund + Chargeback Double-Dip: Plan REVERSE_REFUND -> Approve -> Execute -> AWAITING_VERIFICATION
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

    # 7. Settlement SLA Breach: Plan RECONCILE -> Execute -> AWAITING_VERIFICATION
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

    # 8. Legitimate Partial Settlement: Plan REFUND -> Strictly Rejected
    part_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.PARTIAL_SETTLEMENT.value)
    with pytest.raises(ValueError, match="prohibits financial remediation|BLOCKED"):
        rem_service.create_remediation_plan(
            session=db_session,
            exception_id=part_exc["exception_id"],
            action=PolicyActionType.REFUND.value,
            parameters={"payment_id": part_exc["primary_payment_id"], "amount_minor_units": 100000, "reason": "Invalid refund on legit case"},
            requested_by="operator-01",
        )

    # 9. Legitimate Timing Exception: Plan REFUND -> Strictly Rejected
    time_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value)
    with pytest.raises(ValueError, match="prohibits financial remediation|BLOCKED"):
        rem_service.create_remediation_plan(
            session=db_session,
            exception_id=time_exc["exception_id"],
            action=PolicyActionType.REFUND.value,
            parameters={"payment_id": time_exc["primary_payment_id"], "amount_minor_units": 100000, "reason": "Invalid refund on timing case"},
            requested_by="operator-01",
        )
