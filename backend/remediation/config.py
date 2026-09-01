"""Configuration, versioning, and limits for the Remediation Workflow Engine."""
from backend.models.enums import PolicyActionType

# Active Version
REMEDIATION_VERSION: str = "v1"

# Supported Allowlisted Remediation Actions
ALLOWLISTED_REMEDIATION_ACTIONS = [
    PolicyActionType.RECONCILE.value,
    PolicyActionType.ALLOCATE_SETTLEMENT.value,
    PolicyActionType.REFUND.value,
    PolicyActionType.REVERSE_REFUND.value,
    PolicyActionType.ESCALATE.value,
    PolicyActionType.RESOLVE_EXCEPTION.value,
]

# Actions that perform financial mutations on transactions or ledger
FINANCIAL_MUTATION_REMEDIATIONS = [
    PolicyActionType.REFUND.value,
    PolicyActionType.REVERSE_REFUND.value,
    PolicyActionType.ALLOCATE_SETTLEMENT.value,
    PolicyActionType.RECONCILE.value,
]

# Approval expiration window (hours)
DEFAULT_APPROVAL_EXPIRY_HOURS: int = 24
