"""End-to-end verification of policy decisions across all 6 PRD families on Seed 42."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from backend.data.generator.service import generate_dataset
from backend.models.enums import (
    ExceptionType,
    PolicyActionType,
    PolicyDecisionType,
    ApprovalRole,
    EscalationLevel,
)
from backend.exceptions.service import ExceptionDetectionService
from backend.agent.service import InvestigationService
from backend.exposure.service import RiskAssessmentService
from backend.policy.service import PolicyService


def test_seed42_full_pipeline_policy_gating(db_session: Session):
    """Executes full pipeline on Seed 42 and validates policy decisions across all anomaly families."""
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

    policy_service = PolicyService()

    # 5. Ghost Settlement: Request REFUND -> REQUIRE_APPROVAL (FINANCE) & REQUIRE_ESCALATION (EXECUTIVE)
    ghost_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.GHOST_SETTLEMENT.value)
    ghost_dec = policy_service.evaluate_policy(
        session=db_session,
        exception_id=ghost_exc["exception_id"],
        requested_action=PolicyActionType.REFUND.value,
    )
    assert ghost_dec.decision == PolicyDecisionType.REQUIRE_APPROVAL.value
    assert ghost_dec.approval_required is True
    assert ghost_dec.approval_role == ApprovalRole.FINANCE.value
    assert ghost_dec.escalation_required is True
    assert ghost_dec.escalation_level == EscalationLevel.EXECUTIVE.value

    # 6. Refund + Chargeback Double-Dip: Request REVERSE_REFUND -> REQUIRE_APPROVAL (FINANCE)
    dd_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value)
    dd_dec = policy_service.evaluate_policy(
        session=db_session,
        exception_id=dd_exc["exception_id"],
        requested_action=PolicyActionType.REVERSE_REFUND.value,
    )
    assert dd_dec.decision == PolicyDecisionType.REQUIRE_APPROVAL.value
    assert dd_dec.approval_required is True
    assert dd_dec.approval_role == ApprovalRole.FINANCE.value

    # 7. Settlement SLA Breach: Request RECONCILE -> ALLOW_WITH_CONDITIONS
    sla_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.SETTLEMENT_SLA_BREACH.value)
    sla_dec = policy_service.evaluate_policy(
        session=db_session,
        exception_id=sla_exc["exception_id"],
        requested_action=PolicyActionType.RECONCILE.value,
    )
    assert sla_dec.decision in (PolicyDecisionType.ALLOW.value, PolicyDecisionType.ALLOW_WITH_CONDITIONS.value)

    # 8. Unallocated Settlement: Request ALLOCATE_SETTLEMENT -> REQUIRE_APPROVAL (FINANCE)
    unalloc_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value and e["sub_type"] == "UNALLOCATED_SETTLEMENT")
    unalloc_dec = policy_service.evaluate_policy(
        session=db_session,
        exception_id=unalloc_exc["exception_id"],
        requested_action=PolicyActionType.ALLOCATE_SETTLEMENT.value,
    )
    assert unalloc_dec.decision == PolicyDecisionType.REQUIRE_APPROVAL.value
    assert unalloc_dec.approval_role == ApprovalRole.FINANCE.value

    # 9. Legitimate Partial Settlement: NO_ACTION -> ALLOW, REFUND -> BLOCK
    part_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.PARTIAL_SETTLEMENT.value)
    part_allow = policy_service.evaluate_policy(
        session=db_session,
        exception_id=part_exc["exception_id"],
        requested_action=PolicyActionType.NO_ACTION.value,
    )
    assert part_allow.decision == PolicyDecisionType.ALLOW.value
    assert part_allow.approval_required is False
    assert part_allow.escalation_required is False

    part_block = policy_service.evaluate_policy(
        session=db_session,
        exception_id=part_exc["exception_id"],
        requested_action=PolicyActionType.REFUND.value,
    )
    assert part_block.decision == PolicyDecisionType.BLOCK.value

    # 10. Legitimate Timing Exception: NO_ACTION -> ALLOW, REFUND -> BLOCK
    time_exc = next(e for e in det_report.exceptions if e["exception_type"] == ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value)
    time_allow = policy_service.evaluate_policy(
        session=db_session,
        exception_id=time_exc["exception_id"],
        requested_action=PolicyActionType.NO_ACTION.value,
    )
    assert time_allow.decision == PolicyDecisionType.ALLOW.value

    time_block = policy_service.evaluate_policy(
        session=db_session,
        exception_id=time_exc["exception_id"],
        requested_action=PolicyActionType.REFUND.value,
    )
    assert time_block.decision == PolicyDecisionType.BLOCK.value
