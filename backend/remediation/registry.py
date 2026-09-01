"""Single source of truth capability registry for remediation execution safety."""
from dataclasses import dataclass
from typing import Dict, List, Optional

from backend.models.enums import (
    ExceptionState,
    PolicyActionType,
    PolicyDecisionType,
    ApprovalRole,
)


@dataclass(frozen=True)
class RemediationCapability:
    action_name: str
    is_financial_mutation: bool
    required_state: str
    required_policy_decisions: List[str]
    approval_role: Optional[str]
    verification_required: bool


CAPABILITY_REGISTRY: Dict[str, RemediationCapability] = {
    PolicyActionType.REFUND.value: RemediationCapability(
        action_name=PolicyActionType.REFUND.value,
        is_financial_mutation=True,
        required_state=ExceptionState.DIAGNOSED.value,
        required_policy_decisions=[
            PolicyDecisionType.ALLOW.value,
            PolicyDecisionType.ALLOW_WITH_CONDITIONS.value,
            PolicyDecisionType.REQUIRE_APPROVAL.value,
        ],
        approval_role=ApprovalRole.FINANCE.value,
        verification_required=True,
    ),
    PolicyActionType.REVERSE_REFUND.value: RemediationCapability(
        action_name=PolicyActionType.REVERSE_REFUND.value,
        is_financial_mutation=True,
        required_state=ExceptionState.DIAGNOSED.value,
        required_policy_decisions=[
            PolicyDecisionType.ALLOW.value,
            PolicyDecisionType.ALLOW_WITH_CONDITIONS.value,
            PolicyDecisionType.REQUIRE_APPROVAL.value,
        ],
        approval_role=ApprovalRole.FINANCE.value,
        verification_required=True,
    ),
    PolicyActionType.ALLOCATE_SETTLEMENT.value: RemediationCapability(
        action_name=PolicyActionType.ALLOCATE_SETTLEMENT.value,
        is_financial_mutation=True,
        required_state=ExceptionState.DIAGNOSED.value,
        required_policy_decisions=[
            PolicyDecisionType.ALLOW.value,
            PolicyDecisionType.ALLOW_WITH_CONDITIONS.value,
            PolicyDecisionType.REQUIRE_APPROVAL.value,
        ],
        approval_role=ApprovalRole.FINANCE.value,
        verification_required=True,
    ),
    PolicyActionType.RECONCILE.value: RemediationCapability(
        action_name=PolicyActionType.RECONCILE.value,
        is_financial_mutation=True,
        required_state=ExceptionState.DIAGNOSED.value,
        required_policy_decisions=[
            PolicyDecisionType.ALLOW.value,
            PolicyDecisionType.ALLOW_WITH_CONDITIONS.value,
        ],
        approval_role=None,
        verification_required=True,
    ),
    PolicyActionType.ESCALATE.value: RemediationCapability(
        action_name=PolicyActionType.ESCALATE.value,
        is_financial_mutation=False,
        required_state=ExceptionState.DIAGNOSED.value,
        required_policy_decisions=[
            PolicyDecisionType.ALLOW.value,
            PolicyDecisionType.ALLOW_WITH_CONDITIONS.value,
            PolicyDecisionType.REQUIRE_ESCALATION.value,
        ],
        approval_role=None,
        verification_required=False,
    ),
    PolicyActionType.RESOLVE_EXCEPTION.value: RemediationCapability(
        action_name=PolicyActionType.RESOLVE_EXCEPTION.value,
        is_financial_mutation=False,
        required_state=ExceptionState.DIAGNOSED.value,
        required_policy_decisions=[
            PolicyDecisionType.ALLOW.value,
        ],
        approval_role=ApprovalRole.ADMIN.value,
        verification_required=True,
    ),
}


def get_capability(action_name: str) -> Optional[RemediationCapability]:
    """Retrieves safety capability configuration for a remediation action."""
    return CAPABILITY_REGISTRY.get(action_name)
