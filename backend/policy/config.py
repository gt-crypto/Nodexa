"""Configurable policy rules, allowlists, and versioning for Risk Policy Gating engine."""
from backend.models.enums import PolicyActionType

# Active Policy Version
POLICY_VERSION = "v1"

# Supported Allowlisted Policy Actions
ALLOWLISTED_ACTIONS = [action.value for action in PolicyActionType]

# Actions that represent irreversible financial balance changes
FINANCIAL_MUTATION_ACTIONS = [
    PolicyActionType.REFUND.value,
    PolicyActionType.REVERSE_REFUND.value,
    PolicyActionType.ALLOCATE_SETTLEMENT.value,
    PolicyActionType.RESOLVE_EXCEPTION.value,
]

# Irreversible high-risk actions requiring strict policy gating
IRREVERSIBLE_ACTIONS = [
    PolicyActionType.REFUND.value,
    PolicyActionType.REVERSE_REFUND.value,
    PolicyActionType.ALLOCATE_SETTLEMENT.value,
    PolicyActionType.RESOLVE_EXCEPTION.value,
]

# Risk and Materiality Policy Gating Thresholds
P1_REQUIRES_APPROVAL: bool = True
P1_REQUIRES_ESCALATION: bool = True
P2_REQUIRES_APPROVAL: bool = True

MIN_INVESTIGATION_CONFIDENCE_FOR_ACTIONS: float = 0.60

# Safety lock: Until Prompt 8 (Remediation) and Prompt 9 (Verification) are built,
# autonomous execution of mutations remains BLOCKED / GATED.
REMEDIATION_CAPABILITY_ACTIVE: bool = False
