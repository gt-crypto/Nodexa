"""Remediation planning engine transforming approved policy decisions into executable plans."""
from datetime import datetime, timezone
import json
import uuid
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import (
    ExceptionState,
    PolicyDecisionType,
    RemediationStatus,
    TransitionActorType,
)
from backend.models.exceptions import ExceptionRecord
from backend.models.investigation import InvestigationRun
from backend.models.risk import RiskAssessment
from backend.models.policy import PolicyDecisionRecord
from backend.models.remediation import RemediationAction
from backend.models.audit import AuditEvent
from backend.services.repositories.audit_repository import AuditRepository
from backend.exposure.service import RiskAssessmentService
from backend.policy.service import PolicyService
from backend.policy.config import POLICY_VERSION
from backend.remediation.config import REMEDIATION_VERSION
from backend.remediation.registry import get_capability
from backend.remediation.validators import validate_remediation_eligibility


class RemediationPlanner:
    """Creates structured, policy-compliant remediation plans without executing financial mutations."""

    @staticmethod
    def create_plan(
        session: Session,
        exception_id: str,
        action: str,
        parameters: Dict[str, Any],
        requested_by: str = "system-operator",
    ) -> RemediationAction:
        """Evaluates prerequisites and generates a validated RemediationAction plan."""
        # 1. Exception Existence and State Gate
        exc = session.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)).first()
        if not exc:
            raise ValueError(f"Exception '{exception_id}' not found.")

        if exc.state not in (ExceptionState.DIAGNOSED.value, ExceptionState.FAILED_ESCALATED.value):
            raise ValueError(f"Remediation requires exception to be DIAGNOSED. Current state: '{exc.state}'.")

        # 2. Investigation Context Gate
        inv_run = session.scalars(
            select(InvestigationRun)
            .where(InvestigationRun.exception_id == exception_id)
            .order_by(InvestigationRun.created_at.desc())
        ).first()
        if not inv_run and exc.state != ExceptionState.FAILED_ESCALATED.value:
            raise ValueError(f"No completed AI investigation found for exception '{exception_id}'.")

        # 3. Risk Assessment
        risk_service = RiskAssessmentService()
        risk_ass = risk_service.get_latest_risk_assessment(session, exception_id)
        if not risk_ass:
            risk_ass = risk_service.assess_exception_risk(session, exception_id)

        # 4. Policy Decision Gate
        policy_service = PolicyService()
        policy_dec = policy_service.evaluate_policy(session=session, exception_id=exception_id, requested_action=action)

        if policy_dec.decision == PolicyDecisionType.BLOCK.value:
            raise ValueError(f"Policy BLOCKED action '{action}': {policy_dec.rationale}")

        # 5. Financial & Parameter Validation
        valid, errors = validate_remediation_eligibility(
            session=session,
            exception=exc,
            action=action,
            parameters=parameters,
        )
        if not valid:
            raise ValueError(f"Remediation parameter validation failed: {'; '.join(errors)}")

        capability = get_capability(action)
        if not capability:
            raise ValueError(f"No capability registered for action '{action}'.")

        # 6. Determine Approval Requirement and Initial Status
        approval_required = policy_dec.approval_required or bool(capability.approval_role)
        approval_role = policy_dec.approval_role or capability.approval_role

        if approval_required:
            initial_status = RemediationStatus.PENDING_APPROVAL.value
        else:
            initial_status = RemediationStatus.APPROVED.value

        now = datetime.now(timezone.utc)
        action_id = f"REM-{exc.exception_id}-{action}-{uuid.uuid4().hex[:8]}"

        plan = RemediationAction(
            action_id=action_id,
            exception_id=exc.exception_id,
            action_type=action,
            status=initial_status,
            action_payload=json.dumps(parameters),
            policy_decision_id=policy_dec.decision_id,
            risk_assessment_id=risk_ass.assessment_id if risk_ass else None,
            investigation_id=inv_run.investigation_id if inv_run else None,
            deterministic_exposure=exc.exposure or 0,
            requested_by=requested_by,
            approval_required=approval_required,
            approval_role=approval_role,
            verification_required=capability.verification_required,
            policy_version=POLICY_VERSION,
            remediation_version=REMEDIATION_VERSION,
            requested_at=now,
            created_at=now,
            updated_at=now,
        )
        session.add(plan)

        # Audit Event Logging
        audit_repo = AuditRepository(session)
        audit_event = AuditEvent(
            audit_event_id=f"audit_{uuid.uuid4().hex[:16]}",
            exception_id=exc.exception_id,
            investigation_id=inv_run.investigation_id if inv_run else None,
            event_type="REMEDIATION_PLANNED",
            timestamp=now,
            actor_type=TransitionActorType.SYSTEM.value if "system" in requested_by else TransitionActorType.HUMAN.value,
            actor_id=requested_by,
            event_summary=f"Remediation plan '{action}' created ({initial_status})",
            event_payload=json.dumps({
                "remediation_id": action_id,
                "action": action,
                "status": initial_status,
                "approval_required": approval_required,
                "approval_role": approval_role,
                "parameters": parameters,
            }),
        )
        audit_repo.append_audit_event(audit_event)
        session.flush()

        return plan
