"""Modular policy gating rules evaluating lifecycle, risk, evidence, and action safety."""
from typing import List, Optional, Set, Tuple

from backend.models.enums import (
    ExceptionState,
    ExceptionType,
    PolicyActionType,
    PolicyDecisionType,
    ApprovalRole,
    EscalationLevel,
)
from backend.models.exceptions import ExceptionRecord
from backend.policy.config import (
    ALLOWLISTED_ACTIONS,
    FINANCIAL_MUTATION_ACTIONS,
    IRREVERSIBLE_ACTIONS,
    MIN_INVESTIGATION_CONFIDENCE_FOR_ACTIONS,
    REMEDIATION_CAPABILITY_ACTIVE,
)


def validate_action_allowlist(requested_action: str) -> Optional[str]:
    """Validates that requested action belongs to the allowlisted taxonomy."""
    if requested_action not in ALLOWLISTED_ACTIONS:
        return f"Requested action '{requested_action}' is not in the allowlisted policy action taxonomy."
    return None


def evaluate_lifecycle_gate(state: str, requested_action: str) -> Tuple[List[str], List[str], Optional[str]]:
    """Evaluates lifecycle stage gates governing permitted actions."""
    if state == ExceptionState.DETECTED.value:
        allowed = [
            PolicyActionType.INVESTIGATE.value,
            PolicyActionType.REQUEST_MORE_EVIDENCE.value,
            PolicyActionType.NO_ACTION.value,
        ]
        prohibited = [
            PolicyActionType.REFUND.value,
            PolicyActionType.REVERSE_REFUND.value,
            PolicyActionType.ALLOCATE_SETTLEMENT.value,
            PolicyActionType.RESOLVE_EXCEPTION.value,
            PolicyActionType.RECONCILE.value,
        ]
        if requested_action in prohibited:
            return allowed, prohibited, f"Action '{requested_action}' is prohibited in DETECTED state before AI investigation completes."
        return allowed, prohibited, None

    elif state == ExceptionState.INVESTIGATING.value:
        allowed = [
            PolicyActionType.INVESTIGATE.value,
            PolicyActionType.REQUEST_MORE_EVIDENCE.value,
            PolicyActionType.NO_ACTION.value,
        ]
        prohibited = [
            PolicyActionType.REFUND.value,
            PolicyActionType.REVERSE_REFUND.value,
            PolicyActionType.ALLOCATE_SETTLEMENT.value,
            PolicyActionType.RESOLVE_EXCEPTION.value,
        ]
        if requested_action in prohibited:
            return allowed, prohibited, f"Action '{requested_action}' is prohibited while investigation is actively RUNNING."
        return allowed, prohibited, None

    elif state == ExceptionState.DIAGNOSED.value:
        allowed = [
            PolicyActionType.RECONCILE.value,
            PolicyActionType.ALLOCATE_SETTLEMENT.value,
            PolicyActionType.REFUND.value,
            PolicyActionType.REVERSE_REFUND.value,
            PolicyActionType.ESCALATE.value,
            PolicyActionType.REQUEST_APPROVAL.value,
            PolicyActionType.REQUEST_MORE_EVIDENCE.value,
            PolicyActionType.INVESTIGATE.value,
            PolicyActionType.NO_ACTION.value,
        ]
        prohibited = [
            PolicyActionType.RESOLVE_EXCEPTION.value,  # Prohibited until remediation/verification executed
        ]
        if requested_action == PolicyActionType.RESOLVE_EXCEPTION.value:
            return allowed, prohibited, "RESOLVE_EXCEPTION is prohibited in DIAGNOSED state without executed remediation and verification."
        return allowed, prohibited, None

    elif state == ExceptionState.FAILED_ESCALATED.value:
        allowed = [
            PolicyActionType.ESCALATE.value,
            PolicyActionType.REQUEST_MORE_EVIDENCE.value,
            PolicyActionType.INVESTIGATE.value,
            PolicyActionType.NO_ACTION.value,
        ]
        prohibited = [
            PolicyActionType.REFUND.value,
            PolicyActionType.REVERSE_REFUND.value,
            PolicyActionType.ALLOCATE_SETTLEMENT.value,
            PolicyActionType.RESOLVE_EXCEPTION.value,
            PolicyActionType.RECONCILE.value,
        ]
        if requested_action in prohibited:
            return allowed, prohibited, f"Action '{requested_action}' is prohibited for FAILED_ESCALATED exception without successful re-investigation."
        return allowed, prohibited, None

    # For other states, provide standard default
    return [PolicyActionType.NO_ACTION.value], [], None


def evaluate_legitimate_case_gate(
    exception_type: str,
    exposure: int,
    requested_action: str,
) -> Tuple[bool, Optional[str]]:
    """Protects legitimate zero-exposure observations from financial remediation or escalation."""
    if exposure <= 0 and exception_type in (
        ExceptionType.PARTIAL_SETTLEMENT.value,
        ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value,
    ):
        if requested_action in (
            PolicyActionType.REFUND.value,
            PolicyActionType.REVERSE_REFUND.value,
            PolicyActionType.ALLOCATE_SETTLEMENT.value,
            PolicyActionType.ESCALATE.value,
        ):
            return True, f"Legitimate zero-exposure observation ({exception_type}) strictly prohibits financial correction or escalation."
        return True, None
    return False, None


def evaluate_risk_materiality_gate(
    priority: str,
    materiality: str,
    requested_action: str,
) -> Tuple[bool, Optional[str], Optional[str], bool, Optional[str], Optional[str]]:
    """Evaluates risk and materiality thresholds to determine approval and escalation mandates."""
    approval_req = False
    approval_role = None
    approval_reason = None

    esc_req = False
    esc_level = None
    esc_reason = None

    is_mutation = requested_action in FINANCIAL_MUTATION_ACTIONS

    if priority == "P1" or materiality in ("MATERIAL", "SEVERE"):
        if is_mutation:
            approval_req = True
            approval_role = ApprovalRole.FINANCE.value
            approval_reason = "P1 / Material financial mutation requires explicit Finance Controller approval."

        esc_req = True
        esc_level = EscalationLevel.EXECUTIVE.value
        esc_reason = "P1 / Material risk exception requires executive and finance escalation."

    elif priority == "P2" or materiality == "HIGH":
        if is_mutation:
            approval_req = True
            approval_role = ApprovalRole.FINANCE.value
            approval_reason = "P2 High-materiality financial mutation requires Finance approval."

        esc_req = True
        esc_level = EscalationLevel.FINANCE.value
        esc_reason = "P2 High-priority exception requires Finance review."

    elif priority == "P3":
        if is_mutation:
            approval_req = True
            approval_role = ApprovalRole.OPERATIONS.value
            approval_reason = "P3 Moderate financial action requires Operations review."

    return approval_req, approval_role, approval_reason, esc_req, esc_level, esc_reason


def evaluate_confidence_gate(confidence: Optional[float], requested_action: str) -> Optional[str]:
    """Gates irreversible actions if AI investigation confidence is insufficient."""
    if requested_action in FINANCIAL_MUTATION_ACTIONS:
        if confidence is not None and confidence < MIN_INVESTIGATION_CONFIDENCE_FOR_ACTIONS:
            return f"Low AI investigation confidence ({confidence:.2f} < {MIN_INVESTIGATION_CONFIDENCE_FOR_ACTIONS:.2f}) blocks irreversible financial mutation."
    return None


def evaluate_evidence_completeness_gate(exception: ExceptionRecord, requested_action: str) -> Tuple[List[str], Optional[str]]:
    """Verifies that all mandatory operational identifiers exist for the requested action."""
    reqs: List[str] = []
    violation = None

    if requested_action in (PolicyActionType.REFUND.value, PolicyActionType.REVERSE_REFUND.value):
        reqs.append("primary_payment_id")
        reqs.append("gateway_transaction_record")
        has_pay = bool(exception.primary_payment_id) or ("PAY-" in (exception.exception_id or ""))
        if not has_pay:
            violation = "Action 'REFUND' lacks primary payment identifier linkage."

    elif requested_action == PolicyActionType.ALLOCATE_SETTLEMENT.value:
        reqs.append("bank_settlement_batch_id")
        reqs.append("utr_number")
        if "UNALLOCATED" in (exception.exception_id or "") and not exception.affected_records:
            violation = "Action 'ALLOCATE_SETTLEMENT' requires matching bank settlement batch evidence."

    elif requested_action == PolicyActionType.RESOLVE_EXCEPTION.value:
        reqs.append("remediation_execution_record")
        reqs.append("verification_result_passed")
        if not REMEDIATION_CAPABILITY_ACTIVE:
            violation = "RESOLVE_EXCEPTION is blocked because post-action verification has not been executed."

    return reqs, violation
