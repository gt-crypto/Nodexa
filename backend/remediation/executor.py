"""Remediation execution engine with double-entry invariant verification and atomic rollback."""
from datetime import datetime, timezone
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import (
    RemediationStatus,
    TransitionActorType,
    PolicyDecisionType,
)
from backend.models.remediation import RemediationAction, RemediationApproval
from backend.models.financial_sources import NodalLedgerEntry
from backend.models.audit import AuditEvent
from backend.services.repositories.audit_repository import AuditRepository
from backend.controls.invariants import validate_ledger_balance_progression
from backend.policy.service import PolicyService
from backend.remediation.handlers import get_handler


class RemediationExecutor:
    """Safely executes approved remediation actions with double-entry validation and audit logging."""

    @staticmethod
    def execute(
        session: Session,
        action_id: str,
        executed_by: str = "service-executor",
    ) -> RemediationAction:
        """Executes an approved remediation action with transactional rollback and invariant validation."""
        plan = session.scalars(select(RemediationAction).where(RemediationAction.action_id == action_id)).first()
        if not plan:
            raise ValueError(f"Remediation plan '{action_id}' not found.")

        # 1. Idempotency Gate
        if plan.status in (RemediationStatus.EXECUTED.value, RemediationStatus.AWAITING_VERIFICATION.value):
            return plan

        if plan.status not in (RemediationStatus.APPROVED.value, RemediationStatus.PLANNED.value):
            raise ValueError(f"Remediation plan '{action_id}' is in '{plan.status}' state and cannot be executed.")

        now = datetime.now(timezone.utc)

        # 2. Approval Validation Gate
        if plan.approval_required:
            latest_appr = session.scalars(
                select(RemediationApproval)
                .where(RemediationApproval.action_id == action_id)
                .order_by(RemediationApproval.timestamp.desc())
            ).first()
            if not latest_appr or latest_appr.decision != "APPROVED":
                raise ValueError(f"Remediation plan '{action_id}' requires approval before execution.")
            if latest_appr.expires_at:
                exp_at = latest_appr.expires_at
                if exp_at.tzinfo is None:
                    exp_at = exp_at.replace(tzinfo=timezone.utc)
                if exp_at < now:
                    raise ValueError(f"Remediation approval for '{action_id}' has expired.")

        # 3. Policy Re-check Gate
        policy_service = PolicyService()
        policy_dec = policy_service.evaluate_policy(
            session=session,
            exception_id=plan.exception_id,
            requested_action=plan.action_type,
        )
        if policy_dec.decision == PolicyDecisionType.BLOCK.value:
            raise ValueError(f"Policy safety gate BLOCKED execution of '{plan.action_type}': {policy_dec.rationale}")

        # 4. Action Handler Lookup
        handler = get_handler(plan.action_type)
        if not handler:
            raise ValueError(f"Action '{plan.action_type}' cannot be executed directly without automated handler.")

        parameters = json.loads(plan.action_payload or "{}")

        # 5. Atomic State Transition to EXECUTING
        plan.status = RemediationStatus.EXECUTING.value
        plan.updated_at = now
        session.flush()

        # Audit Event: Started
        audit_repo = AuditRepository(session)
        audit_repo.append_audit_event(
            AuditEvent(
                audit_event_id=f"audit_{uuid.uuid4().hex[:16]}",
                exception_id=plan.exception_id,
                investigation_id=plan.investigation_id,
                event_type="REMEDIATION_STARTED",
                timestamp=now,
                actor_type=TransitionActorType.SERVICE.value if "service" in executed_by else TransitionActorType.HUMAN.value,
                actor_id=executed_by,
                event_summary=f"Started execution of remediation '{plan.action_id}' ({plan.action_type})",
                event_payload=json.dumps({"remediation_id": plan.action_id, "action": plan.action_type}),
            )
        )

        try:
            # 6. Execute Handler
            before_snapshot, after_snapshot, summary = handler.execute(
                session=session,
                plan=plan,
                parameters=parameters,
            )

            # 7. Double-Entry Invariant Validation
            all_ledger = list(session.scalars(select(NodalLedgerEntry)).all())
            ctrl_results = validate_ledger_balance_progression(all_ledger)
            for cr in ctrl_results:
                if cr.status.value == "FAIL":
                    raise ValueError(f"Double-entry ledger invariant failure in {cr.control_name}: {cr.rule}")

            # 8. Mark Awaiting Verification
            final_status = (
                RemediationStatus.AWAITING_VERIFICATION.value
                if plan.verification_required
                else RemediationStatus.EXECUTED.value
            )
            plan.status = final_status
            plan.before_snapshot = json.dumps(before_snapshot)
            plan.after_snapshot = json.dumps(after_snapshot)
            plan.result_summary = summary
            plan.executed_at = now
            plan.updated_at = now

            # Audit Event: Success
            audit_repo.append_audit_event(
                AuditEvent(
                    audit_event_id=f"audit_{uuid.uuid4().hex[:16]}",
                    exception_id=plan.exception_id,
                    investigation_id=plan.investigation_id,
                    event_type="REMEDIATION_EXECUTED",
                    timestamp=now,
                    actor_type=TransitionActorType.SERVICE.value if "service" in executed_by else TransitionActorType.HUMAN.value,
                    actor_id=executed_by,
                    event_summary=summary,
                    event_payload=json.dumps({
                        "remediation_id": plan.action_id,
                        "status": final_status,
                        "before": before_snapshot,
                        "after": after_snapshot,
                    }),
                )
            )

            if plan.verification_required:
                audit_repo.append_audit_event(
                    AuditEvent(
                        audit_event_id=f"audit_{uuid.uuid4().hex[:16]}",
                        exception_id=plan.exception_id,
                        investigation_id=plan.investigation_id,
                        event_type="REMEDIATION_AWAITING_VERIFICATION",
                        timestamp=now,
                        actor_type=TransitionActorType.SYSTEM.value,
                        actor_id="remediation_executor",
                        event_summary=f"Remediation '{plan.action_id}' moved to AWAITING_VERIFICATION",
                        event_payload=json.dumps({"remediation_id": plan.action_id}),
                    )
                )

            session.flush()
            return plan

        except Exception as e:
            session.rollback()
            # Re-fetch plan after rollback to record FAILED status
            plan_fail = session.scalars(select(RemediationAction).where(RemediationAction.action_id == action_id)).first()
            if plan_fail:
                plan_fail.status = RemediationStatus.FAILED.value
                plan_fail.error_reason = str(e)
                plan_fail.updated_at = datetime.now(timezone.utc)
                audit_repo_fail = AuditRepository(session)
                audit_repo_fail.append_audit_event(
                    AuditEvent(
                        audit_event_id=f"audit_{uuid.uuid4().hex[:16]}",
                        exception_id=plan_fail.exception_id,
                        investigation_id=plan_fail.investigation_id,
                        event_type="REMEDIATION_FAILED",
                        timestamp=datetime.now(timezone.utc),
                        actor_type=TransitionActorType.SYSTEM.value,
                        actor_id="remediation_executor",
                        event_summary=f"Remediation '{action_id}' failed: {str(e)}",
                        event_payload=json.dumps({"remediation_id": action_id, "error": str(e)}),
                    )
                )
                session.flush()
            raise e

    @staticmethod
    def dry_run(
        session: Session,
        action_id: str,
    ) -> Tuple[bool, List[str], Dict[str, Any], Dict[str, Any], str]:
        """Simulates remediation execution without committing database mutations."""
        plan = session.scalars(select(RemediationAction).where(RemediationAction.action_id == action_id)).first()
        if not plan:
            raise ValueError(f"Remediation plan '{action_id}' not found.")

        handler = get_handler(plan.action_type)
        if not handler:
            return False, [f"No handler for action '{plan.action_type}'"], {}, {}, plan.status

        parameters = json.loads(plan.action_payload or "{}")
        before_state, after_state = handler.dry_run(session=session, plan=plan, parameters=parameters)
        return True, [], before_state, after_state, plan.status
