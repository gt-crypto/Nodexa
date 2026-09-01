"""Deterministic Policy Engine evaluating multi-stage gates and producing policy decisions."""
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import (
    ExceptionState,
    ExceptionType,
    PolicyActionType,
    PolicyDecisionType,
    ApprovalRole,
    EscalationLevel,
)
from backend.models.exceptions import ExceptionRecord
from backend.models.investigation import InvestigationRun
from backend.models.risk import RiskAssessment
from backend.exposure.service import RiskAssessmentService
from backend.policy.config import (
    POLICY_VERSION,
    ALLOWLISTED_ACTIONS,
    FINANCIAL_MUTATION_ACTIONS,
)
from backend.policy.rules import (
    validate_action_allowlist,
    evaluate_lifecycle_gate,
    evaluate_legitimate_case_gate,
    evaluate_risk_materiality_gate,
    evaluate_confidence_gate,
    evaluate_evidence_completeness_gate,
)


class PolicyEngine:
    """Evaluates risk policy gates and outputs deterministic decisions with zero financial side-effects."""

    @staticmethod
    def evaluate(
        session: Session,
        exception: ExceptionRecord,
        requested_action: str,
    ) -> Dict[str, Any]:
        """Evaluates all policy gates for an exception and requested action."""
        rules_evaluated: List[str] = []
        violated_rules: List[str] = []
        evidence_requirements: List[str] = []

        # 1. Allowlist Validation Gate
        rules_evaluated.append("RULE_ALLOWLISTED_ACTION_CHECK")
        allow_err = validate_action_allowlist(requested_action)
        if allow_err:
            violated_rules.append(allow_err)
            return {
                "decision": PolicyDecisionType.BLOCK.value,
                "policy_version": POLICY_VERSION,
                "allowed_actions": [PolicyActionType.NO_ACTION.value],
                "prohibited_actions": [requested_action],
                "approval_required": False,
                "approval_role": None,
                "approval_reason": None,
                "escalation_required": False,
                "escalation_level": None,
                "escalation_reason": None,
                "evidence_requirements": [],
                "rules_evaluated": rules_evaluated,
                "violated_rules": violated_rules,
                "rationale": f"BLOCK: {allow_err}",
                "risk_score": 0,
                "priority": "P4",
                "materiality": "NONE",
                "exposure": exception.exposure or 0,
            }

        # 2. Load Risk Assessment and Investigation Context
        risk_service = RiskAssessmentService()
        risk_ass = risk_service.get_latest_risk_assessment(session, exception.exception_id)
        if not risk_ass:
            risk_ass = risk_service.assess_exception_risk(session, exception.exception_id)

        inv_run = session.scalars(
            select(InvestigationRun)
            .where(InvestigationRun.exception_id == exception.exception_id)
            .order_by(InvestigationRun.created_at.desc())
        ).first()

        inv_confidence = float(inv_run.confidence) if inv_run and inv_run.confidence else None
        exposure = exception.exposure or 0
        priority = risk_ass.priority if risk_ass else "P4"
        materiality = risk_ass.materiality if risk_ass else "NONE"
        risk_score = risk_ass.risk_score if risk_ass else 0

        # 3. Lifecycle State Gate
        rules_evaluated.append("RULE_LIFECYCLE_STATE_GATE")
        allowed_actions, prohibited_actions, lc_violation = evaluate_lifecycle_gate(
            state=exception.state,
            requested_action=requested_action,
        )
        if lc_violation:
            violated_rules.append(lc_violation)

        # 4. Legitimate Case Protection Gate
        rules_evaluated.append("RULE_LEGITIMATE_CASE_PROTECTION")
        is_legit, legit_violation = evaluate_legitimate_case_gate(
            exception_type=exception.exception_type,
            exposure=exposure,
            requested_action=requested_action,
        )
        if legit_violation:
            violated_rules.append(legit_violation)

        # 5. Risk & Materiality Gate
        rules_evaluated.append("RULE_RISK_MATERIALITY_GATE")
        app_req, app_role, app_reason, esc_req, esc_level, esc_reason = evaluate_risk_materiality_gate(
            priority=priority,
            materiality=materiality,
            requested_action=requested_action,
        )

        # 6. AI Confidence Gate
        rules_evaluated.append("RULE_AI_CONFIDENCE_GATE")
        conf_violation = evaluate_confidence_gate(
            confidence=inv_confidence,
            requested_action=requested_action,
        )
        if conf_violation:
            violated_rules.append(conf_violation)

        # 7. Evidence Completeness Gate
        rules_evaluated.append("RULE_EVIDENCE_COMPLETENESS_GATE")
        ev_reqs, ev_violation = evaluate_evidence_completeness_gate(
            exception=exception,
            requested_action=requested_action,
        )
        evidence_requirements.extend(ev_reqs)

        # 8. Exception Family-Specific Gating
        rules_evaluated.append("RULE_FAMILY_SPECIFIC_GATES")
        if exception.exception_type == ExceptionType.GHOST_SETTLEMENT.value:
            esc_req = True
            esc_level = EscalationLevel.EXECUTIVE.value
            esc_reason = "Ghost settlement requires immediate executive escalation."
        elif "UNALLOCATED" in (exception.exception_id or ""):
            if requested_action == PolicyActionType.ALLOCATE_SETTLEMENT.value:
                app_req = True
                app_role = ApprovalRole.FINANCE.value
                app_reason = "Unallocated settlement manual allocation requires Finance sign-off."

        # 9. Determine Policy Outcome Decision
        if violated_rules:
            decision = PolicyDecisionType.BLOCK.value
        elif is_legit:
            decision = PolicyDecisionType.ALLOW.value if requested_action == PolicyActionType.NO_ACTION.value else PolicyDecisionType.BLOCK.value
        elif conf_violation or ev_violation:
            decision = PolicyDecisionType.INSUFFICIENT_EVIDENCE.value
        elif requested_action in (
            PolicyActionType.INVESTIGATE.value,
            PolicyActionType.REQUEST_MORE_EVIDENCE.value,
            PolicyActionType.NO_ACTION.value,
        ):
            decision = PolicyDecisionType.ALLOW.value
        elif requested_action == PolicyActionType.RECONCILE.value:
            decision = PolicyDecisionType.ALLOW_WITH_CONDITIONS.value
        elif requested_action == PolicyActionType.ESCALATE.value:
            decision = PolicyDecisionType.REQUIRE_ESCALATION.value if esc_req else PolicyDecisionType.ALLOW.value
        elif requested_action == PolicyActionType.REQUEST_APPROVAL.value:
            decision = PolicyDecisionType.REQUIRE_APPROVAL.value
        elif requested_action in FINANCIAL_MUTATION_ACTIONS:
            if app_req:
                decision = PolicyDecisionType.REQUIRE_APPROVAL.value
            elif esc_req:
                decision = PolicyDecisionType.REQUIRE_ESCALATION.value
            else:
                decision = PolicyDecisionType.ALLOW_WITH_CONDITIONS.value
        elif app_req:
            decision = PolicyDecisionType.REQUIRE_APPROVAL.value
        elif esc_req:
            decision = PolicyDecisionType.REQUIRE_ESCALATION.value
        else:
            decision = PolicyDecisionType.ALLOW.value

        # 10. Generate Deterministic Rationale
        rationale_parts = [
            f"Policy evaluation '{decision}' for action '{requested_action}' under Policy Version {POLICY_VERSION}.",
            f"Exception {exception.exception_id} is in state '{exception.state}' with {priority} priority and ₹{exposure/100:,.2f} exposure.",
        ]
        if violated_rules:
            rationale_parts.append(f"Violations detected: {'; '.join(violated_rules)}.")
        if app_req:
            rationale_parts.append(f"Approval Mandate: Role '{app_role}' required ({app_reason}).")
        if esc_req:
            rationale_parts.append(f"Escalation Mandate: Level '{esc_level}' required ({esc_reason}).")
        if is_legit:
            rationale_parts.append("Observation is a confirmed legitimate operational timing/partial split.")

        rationale = " ".join(rationale_parts)

        return {
            "decision": decision,
            "policy_version": POLICY_VERSION,
            "allowed_actions": allowed_actions,
            "prohibited_actions": prohibited_actions,
            "approval_required": app_req,
            "approval_role": app_role,
            "approval_reason": app_reason,
            "escalation_required": esc_req,
            "escalation_level": esc_level,
            "escalation_reason": esc_reason,
            "evidence_requirements": list(set(evidence_requirements)),
            "rules_evaluated": rules_evaluated,
            "violated_rules": violated_rules,
            "rationale": rationale,
            "risk_score": risk_score,
            "priority": priority,
            "materiality": materiality,
            "exposure": exposure,
        }
