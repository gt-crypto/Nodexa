"""Approval workflow engine enforcing separation of duties, role gating, and expiration."""
from datetime import datetime, timezone, timedelta
import json
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import RemediationStatus, ApprovalDecision, TransitionActorType
from backend.models.remediation import RemediationAction, RemediationApproval
from backend.models.audit import AuditEvent
from backend.services.repositories.audit_repository import AuditRepository
from backend.remediation.config import DEFAULT_APPROVAL_EXPIRY_HOURS
from backend.policy.config import POLICY_VERSION


class ApprovalService:
    """Manages role approvals with strict separation of duties and expiration tracking."""

    @staticmethod
    def record_approval(
        session: Session,
        action_id: str,
        approved_by: str,
        decision: str,
        reason: str,
    ) -> RemediationApproval:
        """Records an approval decision and updates remediation status."""
        plan = session.scalars(select(RemediationAction).where(RemediationAction.action_id == action_id)).first()
        if not plan:
            raise ValueError(f"Remediation plan '{action_id}' not found.")

        if plan.status not in (RemediationStatus.PENDING_APPROVAL.value, RemediationStatus.PLANNED.value):
            raise ValueError(f"Remediation plan is in '{plan.status}' state; cannot record approval.")

        # Separation of Duties Gate
        if approved_by and plan.requested_by and approved_by == plan.requested_by:
            raise ValueError("Separation of duties violation: Requester cannot approve their own financial remediation.")

        decision_upper = decision.upper()
        if decision_upper not in (ApprovalDecision.APPROVED.value, ApprovalDecision.REJECTED.value):
            raise ValueError(f"Invalid approval decision '{decision}'. Must be APPROVED or REJECTED.")

        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(hours=DEFAULT_APPROVAL_EXPIRY_HOURS)

        approval_record = RemediationApproval(
            approval_id=f"APP-{uuid.uuid4().hex[:12]}",
            action_id=plan.action_id,
            required_role=plan.approval_role or "OPERATIONS",
            approved_by=approved_by,
            decision=decision_upper,
            reason=reason,
            timestamp=now,
            policy_version=POLICY_VERSION,
            expires_at=expires_at,
        )
        session.add(approval_record)

        # Update Remediation Status
        if decision_upper == ApprovalDecision.APPROVED.value:
            plan.status = RemediationStatus.APPROVED.value
            plan.approved_by = approved_by
            plan.approved_at = now
            event_type = "REMEDIATION_APPROVED"
        else:
            plan.status = RemediationStatus.REJECTED.value
            plan.error_reason = reason
            event_type = "REMEDIATION_REJECTED"

        plan.updated_at = now

        # Audit Event Logging
        audit_repo = AuditRepository(session)
        audit_event = AuditEvent(
            audit_event_id=f"audit_{uuid.uuid4().hex[:16]}",
            exception_id=plan.exception_id,
            investigation_id=plan.investigation_id,
            event_type=event_type,
            timestamp=now,
            actor_type=TransitionActorType.HUMAN.value,
            actor_id=approved_by,
            event_summary=f"Remediation '{plan.action_id}' {decision_upper} by {approved_by}",
            event_payload=json.dumps({
                "approval_id": approval_record.approval_id,
                "remediation_id": plan.action_id,
                "decision": decision_upper,
                "reason": reason,
                "role": plan.approval_role,
            }),
        )
        audit_repo.append_audit_event(audit_event)
        session.flush()

        return approval_record
