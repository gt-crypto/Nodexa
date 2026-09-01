"""Deterministic integer minor-unit financial exposure calculations for detected exceptions."""
from typing import Optional, List
from backend.models.enums import ExceptionType
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    DisputeRefundEvent,
)


def calculate_exception_exposure(
    exception_type: ExceptionType | str,
    payment: Optional[GatewayTransaction] = None,
    settlements: Optional[List[BankSettlementBatch]] = None,
    disputes: Optional[List[DisputeRefundEvent]] = None,
    sub_type: Optional[str] = None,
) -> int:
    """Calculates deterministic financial exposure in integer minor units directly from operational records.
    
    Rules:
    - GHOST_SETTLEMENT: Sum of net settlement amounts cleared for the failed transaction.
    - REFUND_CHARGEBACK_DOUBLE_DIP: Amount of the overlapping chargeback event.
    - SETTLEMENT_SLA_BREACH: Payment amount pending clearance beyond SLA.
    - MISSING_UNALLOCATED_SETTLEMENT:
        - If sub_type == 'MISSING_SETTLEMENT': Payment amount missing downstream settlement.
        - If sub_type == 'UNALLOCATED_SETTLEMENT': Net amount of unallocated bank settlement inflow.
    - PARTIAL_SETTLEMENT (legitimate): 0 minor units.
    - LEGITIMATE_TIMING_EXCEPTION: 0 minor units.
    """
    exc_type_val = exception_type.value if isinstance(exception_type, ExceptionType) else str(exception_type)
    settlements = settlements or []
    disputes = disputes or []

    if exc_type_val == ExceptionType.GHOST_SETTLEMENT.value:
        if settlements:
            return sum(s.net_amount for s in settlements)
        if payment:
            return payment.amount
        return 0

    elif exc_type_val == ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value:
        # Overlapping chargeback amount
        cb_events = [d for d in disputes if d.event_type == "CHARGEBACK"]
        if cb_events:
            return sum(cb.amount for cb in cb_events)
        if payment:
            return payment.amount
        return 0

    elif exc_type_val == ExceptionType.SETTLEMENT_SLA_BREACH.value:
        if payment:
            return payment.amount
        return 0

    elif exc_type_val == ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value:
        if sub_type == "UNALLOCATED_SETTLEMENT" or (not payment and settlements):
            return sum(s.net_amount for s in settlements)
        elif payment:
            return payment.amount
        return 0

    elif exc_type_val in (ExceptionType.PARTIAL_SETTLEMENT.value, ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value):
        # Legitimate operational observations have zero financial exposure
        return 0

    return 0
