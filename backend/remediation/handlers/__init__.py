"""Action handlers registry for remediation execution."""
from typing import Dict, Optional
from backend.models.enums import PolicyActionType
from backend.remediation.handlers.base import BaseActionHandler
from backend.remediation.handlers.refund import RefundHandler
from backend.remediation.handlers.reverse_refund import ReverseRefundHandler
from backend.remediation.handlers.allocate import AllocateSettlementHandler
from backend.remediation.handlers.reconcile import ReconcileHandler
from backend.remediation.handlers.escalate import EscalateHandler

HANDLERS: Dict[str, BaseActionHandler] = {
    PolicyActionType.REFUND.value: RefundHandler(),
    PolicyActionType.REVERSE_REFUND.value: ReverseRefundHandler(),
    PolicyActionType.ALLOCATE_SETTLEMENT.value: AllocateSettlementHandler(),
    PolicyActionType.RECONCILE.value: ReconcileHandler(),
    PolicyActionType.ESCALATE.value: EscalateHandler(),
}


def get_handler(action: str) -> Optional[BaseActionHandler]:
    """Retrieves action execution handler for an allowlisted remediation action."""
    return HANDLERS.get(action)
