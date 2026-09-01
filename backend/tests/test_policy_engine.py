"""Unit tests for multi-stage Risk Policy Gates and Decision Engine."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from backend.models.enums import (
    ExceptionState,
    ExceptionType,
    PolicyActionType,
    PolicyDecisionType,
    ApprovalRole,
    EscalationLevel,
)
from backend.models.exceptions import ExceptionRecord
from backend.exposure.service import RiskAssessmentService
from backend.policy.engine import PolicyEngine


def test_lifecycle_state_gates(db_session: Session):
    """Verifies that exception lifecycle states strictly gate permissible actions."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-LIFECYCLE-TEST-PAY-000001",
        primary_payment_id="PAY-000001",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="CRITICAL",
        state=ExceptionState.DETECTED.value,
        exposure=5000000,
        detected_at=now,
        created_at=now,
    )
    db_session.add(exc)
    db_session.commit()

    # 1. In DETECTED state: INVESTIGATE is allowed
    res_inv = PolicyEngine.evaluate(session=db_session, exception=exc, requested_action=PolicyActionType.INVESTIGATE.value)
    assert res_inv["decision"] == PolicyDecisionType.ALLOW.value

    # 2. In DETECTED state: REFUND is blocked before investigation completes
    res_ref = PolicyEngine.evaluate(session=db_session, exception=exc, requested_action=PolicyActionType.REFUND.value)
    assert res_ref["decision"] == PolicyDecisionType.BLOCK.value
    assert any("prohibited in DETECTED state" in v for v in res_ref["violated_rules"])

    # 3. Transition to DIAGNOSED: REFUND requires approval
    exc.state = ExceptionState.DIAGNOSED.value
    db_session.commit()
    res_diag_ref = PolicyEngine.evaluate(session=db_session, exception=exc, requested_action=PolicyActionType.REFUND.value)
    assert res_diag_ref["decision"] == PolicyDecisionType.REQUIRE_APPROVAL.value
    assert res_diag_ref["approval_required"] is True
    assert res_diag_ref["approval_role"] == ApprovalRole.FINANCE.value

    # 4. In DIAGNOSED: RESOLVE_EXCEPTION is blocked because verification engine is not yet executed
    res_diag_res = PolicyEngine.evaluate(session=db_session, exception=exc, requested_action=PolicyActionType.RESOLVE_EXCEPTION.value)
    assert res_diag_res["decision"] == PolicyDecisionType.BLOCK.value


def test_legitimate_case_protection_gate(db_session: Session):
    """Verifies that legitimate observations with zero exposure strictly prohibit financial remediation or escalation."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-LEGIT-GATE-TEST-PAY-000002",
        primary_payment_id="PAY-000002",
        exception_type=ExceptionType.PARTIAL_SETTLEMENT.value,
        severity="LOW",
        state=ExceptionState.DIAGNOSED.value,
        exposure=0,
        detected_at=now,
        created_at=now,
    )
    db_session.add(exc)
    db_session.commit()

    # 1. NO_ACTION is allowed
    res_no = PolicyEngine.evaluate(session=db_session, exception=exc, requested_action=PolicyActionType.NO_ACTION.value)
    assert res_no["decision"] == PolicyDecisionType.ALLOW.value
    assert res_no["approval_required"] is False
    assert res_no["escalation_required"] is False

    # 2. REFUND or ESCALATE is strictly blocked
    res_ref = PolicyEngine.evaluate(session=db_session, exception=exc, requested_action=PolicyActionType.REFUND.value)
    assert res_ref["decision"] == PolicyDecisionType.BLOCK.value
    assert any("strictly prohibits financial correction" in v for v in res_ref["violated_rules"])


def test_risk_materiality_gate_p1_mandates(db_session: Session):
    """Verifies that P1/Material exceptions mandate Finance approval and Executive escalation."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-P1-GATE-TEST-PAY-000003",
        primary_payment_id="PAY-000003",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="CRITICAL",
        state=ExceptionState.DIAGNOSED.value,
        exposure=10000000,
        detected_at=now,
        created_at=now,
    )
    db_session.add(exc)
    db_session.commit()

    res = PolicyEngine.evaluate(session=db_session, exception=exc, requested_action=PolicyActionType.REFUND.value)
    assert res["decision"] == PolicyDecisionType.REQUIRE_APPROVAL.value
    assert res["approval_required"] is True
    assert res["approval_role"] == ApprovalRole.FINANCE.value
    assert res["escalation_required"] is True
    assert res["escalation_level"] == EscalationLevel.EXECUTIVE.value
