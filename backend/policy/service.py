"""High-level service managing policy checks, simulation mode, and decision history."""
from datetime import datetime, timezone
import json
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import TransitionActorType
from backend.models.exceptions import ExceptionRecord
from backend.models.policy import PolicyDecisionRecord
from backend.models.audit import AuditEvent
from backend.services.repositories.audit_repository import AuditRepository
from backend.policy.config import (
    POLICY_VERSION,
    ALLOWLISTED_ACTIONS,
    FINANCIAL_MUTATION_ACTIONS,
    P1_REQUIRES_APPROVAL,
    P1_REQUIRES_ESCALATION,
    MIN_INVESTIGATION_CONFIDENCE_FOR_ACTIONS,
    REMEDIATION_CAPABILITY_ACTIVE,
)
from backend.policy.engine import PolicyEngine


class PolicyService:
    """Orchestrates policy gating evaluation, simulation, and decision persistence."""

    def evaluate_policy(
        self,
        session: Session,
        exception_id: str,
        requested_action: str,
        simulation: bool = False,
    ) -> PolicyDecisionRecord:
        """Evaluates policy for an exception and requested action, with optional simulation."""
        exc = session.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)).first()
        if not exc:
            raise ValueError(f"Exception '{exception_id}' not found.")

        result = PolicyEngine.evaluate(session=session, exception=exc, requested_action=requested_action)
        now = datetime.now(timezone.utc)

        # Simulation mode: do not persist to database
        if simulation:
            clean_exc_id = exc.exception_id.replace("EXC-", "")
            return PolicyDecisionRecord(
                decision_id=f"SIM-{clean_exc_id[:28]}-{uuid.uuid4().hex[:8]}",
                exception_id=exc.exception_id,
                requested_action=requested_action,
                decision=result["decision"],
                policy_version=result["policy_version"],
                allowed_actions=json.dumps(result["allowed_actions"]),
                prohibited_actions=json.dumps(result["prohibited_actions"]),
                approval_required=result["approval_required"],
                approval_role=result["approval_role"],
                approval_reason=result["approval_reason"],
                escalation_required=result["escalation_required"],
                escalation_level=result["escalation_level"],
                escalation_reason=result["escalation_reason"],
                evidence_requirements=json.dumps(result["evidence_requirements"]),
                rules_evaluated=json.dumps(result["rules_evaluated"]),
                violated_rules=json.dumps(result["violated_rules"]),
                rationale=result["rationale"],
                risk_score=result["risk_score"],
                priority=result["priority"],
                materiality=result["materiality"],
                exposure=result["exposure"],
                evaluated_at=now,
                created_at=now,
            )

        # Idempotency check: check if identical decision already exists
        existing_stmt = (
            select(PolicyDecisionRecord)
            .where(
                PolicyDecisionRecord.exception_id == exception_id,
                PolicyDecisionRecord.requested_action == requested_action,
                PolicyDecisionRecord.policy_version == POLICY_VERSION,
                PolicyDecisionRecord.decision == result["decision"],
            )
            .order_by(PolicyDecisionRecord.evaluated_at.desc())
        )
        existing = session.scalars(existing_stmt).first()
        if existing:
            return existing

        clean_exc_id = exc.exception_id.replace("EXC-", "")
        decision_id = f"PD-{clean_exc_id[:24]}-{requested_action[:12]}-{uuid.uuid4().hex[:8]}"
        record = PolicyDecisionRecord(
            decision_id=decision_id,
            exception_id=exc.exception_id,
            requested_action=requested_action,
            decision=result["decision"],
            policy_version=result["policy_version"],
            allowed_actions=json.dumps(result["allowed_actions"]),
            prohibited_actions=json.dumps(result["prohibited_actions"]),
            approval_required=result["approval_required"],
            approval_role=result["approval_role"],
            approval_reason=result["approval_reason"],
            escalation_required=result["escalation_required"],
            escalation_level=result["escalation_level"],
            escalation_reason=result["escalation_reason"],
            evidence_requirements=json.dumps(result["evidence_requirements"]),
            rules_evaluated=json.dumps(result["rules_evaluated"]),
            violated_rules=json.dumps(result["violated_rules"]),
            rationale=result["rationale"],
            risk_score=result["risk_score"],
            priority=result["priority"],
            materiality=result["materiality"],
            exposure=result["exposure"],
            evaluated_at=now,
            created_at=now,
        )
        session.add(record)

        # Audit Event Logging
        audit_repo = AuditRepository(session)
        audit_event = AuditEvent(
            audit_event_id=f"audit_{uuid.uuid4().hex[:16]}",
            exception_id=exc.exception_id,
            event_type="POLICY_DECISION_RECORDED",
            timestamp=now,
            actor_type=TransitionActorType.SYSTEM.value,
            actor_id="policy_gating_engine_v1",
            event_summary=f"Policy Decision '{result['decision']}' for action '{requested_action}'",
            event_payload=json.dumps({
                "decision_id": decision_id,
                "decision": result["decision"],
                "requested_action": requested_action,
                "approval_required": result["approval_required"],
                "escalation_required": result["escalation_required"],
            }),
        )
        audit_repo.append_audit_event(audit_event)
        session.flush()

        return record

    def list_decisions_for_exception(
        self,
        session: Session,
        exception_id: str,
    ) -> List[PolicyDecisionRecord]:
        """Retrieves all policy decisions recorded for an exception."""
        stmt = (
            select(PolicyDecisionRecord)
            .where(PolicyDecisionRecord.exception_id == exception_id)
            .order_by(PolicyDecisionRecord.evaluated_at.desc())
        )
        return list(session.scalars(stmt).all())

    def get_decision(
        self,
        session: Session,
        decision_id: str,
    ) -> Optional[PolicyDecisionRecord]:
        """Retrieves a single policy decision by ID."""
        stmt = select(PolicyDecisionRecord).where(PolicyDecisionRecord.decision_id == decision_id)
        return session.scalars(stmt).first()

    def get_policy_config(self) -> Dict[str, Any]:
        """Returns active policy configuration parameters."""
        return {
            "policy_version": POLICY_VERSION,
            "allowlisted_actions": ALLOWLISTED_ACTIONS,
            "financial_mutation_actions": FINANCIAL_MUTATION_ACTIONS,
            "p1_requires_approval": P1_REQUIRES_APPROVAL,
            "p1_requires_escalation": P1_REQUIRES_ESCALATION,
            "min_investigation_confidence": MIN_INVESTIGATION_CONFIDENCE_FOR_ACTIONS,
            "remediation_capability_active": REMEDIATION_CAPABILITY_ACTIVE,
        }
