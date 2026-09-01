"""Handler for ESCALATE operational remediation action."""
from datetime import datetime, timezone
from typing import Any, Dict, Tuple
from sqlalchemy.orm import Session

from backend.models.remediation import RemediationAction
from backend.remediation.handlers.base import BaseActionHandler


class EscalateHandler(BaseActionHandler):
    """Executes formal escalation logging and stakeholder assignment."""

    def execute(
        self,
        session: Session,
        plan: RemediationAction,
        parameters: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        level = parameters.get("escalation_level", "EXECUTIVE")
        reason = parameters.get("reason", "Manual remediation escalation")

        before_snapshot = {"escalated": False}
        after_snapshot = {
            "escalated": True,
            "escalation_level": level,
            "reason": reason,
            "escalated_at": datetime.now(timezone.utc).isoformat(),
        }

        summary = f"Escalated exception {plan.exception_id} to {level} review: {reason}"
        return before_snapshot, after_snapshot, summary

    def dry_run(
        self,
        session: Session,
        plan: RemediationAction,
        parameters: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        level = parameters.get("escalation_level", "EXECUTIVE")
        return ({"escalated": False}, {"projected_escalation_level": level})
