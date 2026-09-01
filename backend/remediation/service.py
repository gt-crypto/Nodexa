"""High-level service coordinating remediation planning, approval, execution, and history."""
from datetime import datetime, timezone
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import RemediationStatus, TransitionActorType
from backend.models.remediation import RemediationAction, RemediationApproval
from backend.models.audit import AuditEvent
from backend.services.repositories.audit_repository import AuditRepository
from backend.remediation.planner import RemediationPlanner
from backend.remediation.approval import ApprovalService
from backend.remediation.executor import RemediationExecutor


class RemediationService:
    """Coordinates the full controlled remediation lifecycle: Plan -> Approve -> Execute -> Await Verification."""

    def create_remediation_plan(
        self,
        session: Session,
        exception_id: str,
        action: str,
        parameters: Dict[str, Any],
        requested_by: str = "system-operator",
    ) -> RemediationAction:
        """Plans a structured remediation action after validating policy and prerequisites."""
        return RemediationPlanner.create_plan(
            session=session,
            exception_id=exception_id,
            action=action,
            parameters=parameters,
            requested_by=requested_by,
        )

    def approve_remediation(
        self,
        session: Session,
        action_id: str,
        approved_by: str,
        decision: str,
        reason: str,
    ) -> RemediationApproval:
        """Records an approval decision with role verification and separation of duties."""
        return ApprovalService.record_approval(
            session=session,
            action_id=action_id,
            approved_by=approved_by,
            decision=decision,
            reason=reason,
        )

    def execute_remediation(
        self,
        session: Session,
        action_id: str,
        executed_by: str = "service-executor",
    ) -> RemediationAction:
        """Transactionally executes an approved remediation plan with double-entry validation."""
        return RemediationExecutor.execute(
            session=session,
            action_id=action_id,
            executed_by=executed_by,
        )

    def cancel_remediation(
        self,
        session: Session,
        action_id: str,
        reason: str = "Cancelled by operator",
    ) -> RemediationAction:
        """Cancels a pending or approved remediation plan."""
        plan = session.scalars(select(RemediationAction).where(RemediationAction.action_id == action_id)).first()
        if not plan:
            raise ValueError(f"Remediation plan '{action_id}' not found.")

        if plan.status in (
            RemediationStatus.EXECUTING.value,
            RemediationStatus.EXECUTED.value,
            RemediationStatus.AWAITING_VERIFICATION.value,
        ):
            raise ValueError(f"Cannot cancel remediation plan in '{plan.status}' state.")

        now = datetime.now(timezone.utc)
        plan.status = RemediationStatus.CANCELLED.value
        plan.error_reason = reason
        plan.updated_at = now

        audit_repo = AuditRepository(session)
        audit_repo.append_audit_event(
            AuditEvent(
                audit_event_id=f"audit_{uuid.uuid4().hex[:16]}",
                exception_id=plan.exception_id,
                investigation_id=plan.investigation_id,
                event_type="REMEDIATION_CANCELLED",
                timestamp=now,
                actor_type=TransitionActorType.HUMAN.value,
                actor_id="operator",
                event_summary=f"Cancelled remediation '{plan.action_id}': {reason}",
                event_payload=json.dumps({"remediation_id": plan.action_id, "reason": reason}),
            )
        )
        session.flush()
        return plan

    def dry_run_remediation(
        self,
        session: Session,
        action_id: str,
    ) -> Tuple[bool, List[str], Dict[str, Any], Dict[str, Any], str]:
        """Simulates remediation without committing database mutations."""
        return RemediationExecutor.dry_run(session=session, action_id=action_id)

    def get_remediation(
        self,
        session: Session,
        action_id: str,
    ) -> Optional[RemediationAction]:
        """Retrieves a single remediation plan by action_id."""
        stmt = select(RemediationAction).where(RemediationAction.action_id == action_id)
        return session.scalars(stmt).first()

    def list_remediations_for_exception(
        self,
        session: Session,
        exception_id: str,
    ) -> List[RemediationAction]:
        """Retrieves all remediation plans for an exception."""
        stmt = select(RemediationAction).where(RemediationAction.exception_id == exception_id).order_by(RemediationAction.requested_at.desc())
        return list(session.scalars(stmt).all())
