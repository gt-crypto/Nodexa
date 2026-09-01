"""Unit tests validating the allowlisted Policy Action taxonomy and arbitrary action rejection."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from backend.models.enums import ExceptionState, ExceptionType, PolicyActionType, PolicyDecisionType
from backend.models.exceptions import ExceptionRecord
from backend.policy.config import ALLOWLISTED_ACTIONS
from backend.policy.engine import PolicyEngine


def test_all_ten_allowlisted_actions_evaluated(db_session: Session):
    """Verifies that all 10 allowlisted policy actions can be evaluated without crashing."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-ACTION-TEST",
        exception_type=ExceptionType.SETTLEMENT_SLA_BREACH.value,
        severity="MEDIUM",
        state=ExceptionState.DIAGNOSED.value,
        exposure=1500000,
        detected_at=now,
        created_at=now,
    )
    db_session.add(exc)
    db_session.commit()

    assert len(ALLOWLISTED_ACTIONS) == 10

    for action in ALLOWLISTED_ACTIONS:
        res = PolicyEngine.evaluate(session=db_session, exception=exc, requested_action=action)
        assert res["decision"] in [d.value for d in PolicyDecisionType]
        assert res["policy_version"] == "v1"
        assert len(res["rationale"]) > 0


def test_arbitrary_unallowlisted_action_rejected(db_session: Session):
    """Verifies that non-allowlisted arbitrary action strings are strictly blocked."""
    now = datetime.now(timezone.utc)
    exc = ExceptionRecord(
        exception_id="EXC-ARBITRARY-TEST",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="CRITICAL",
        state=ExceptionState.DIAGNOSED.value,
        exposure=5000000,
        detected_at=now,
        created_at=now,
    )
    db_session.add(exc)
    db_session.commit()

    res = PolicyEngine.evaluate(session=db_session, exception=exc, requested_action="EXECUTE_UNAUTHORIZED_PAYOUT")
    assert res["decision"] == PolicyDecisionType.BLOCK.value
    assert any("not in the allowlisted policy action taxonomy" in v for v in res["violated_rules"])
