"""Typed parameter validation and financial amount safety checks for remediation planning."""
from typing import Any, Dict, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import ExceptionType, PolicyActionType
from backend.models.exceptions import ExceptionRecord
from backend.models.financial_sources import GatewayTransaction, BankSettlementBatch
from backend.remediation.config import ALLOWLISTED_REMEDIATION_ACTIONS, FINANCIAL_MUTATION_REMEDIATIONS
from backend.remediation.models import (
    RefundParameters,
    ReverseRefundParameters,
    AllocateSettlementParameters,
    ReconcileParameters,
    EscalateParameters,
    ResolveExceptionParameters,
)


def validate_remediation_eligibility(
    session: Session,
    exception: ExceptionRecord,
    action: str,
    parameters: Dict[str, Any],
) -> Tuple[bool, List[str]]:
    """Validates exception state, action allowlist, parameters, and financial boundaries."""
    errors: List[str] = []

    # 1. Allowlist Validation
    if action not in ALLOWLISTED_REMEDIATION_ACTIONS:
        errors.append(f"Action '{action}' is not in the allowlisted remediation action taxonomy.")
        return False, errors

    # 2. Legitimate Case Protection
    if (exception.exposure or 0) <= 0 and exception.exception_type in (
        ExceptionType.PARTIAL_SETTLEMENT.value,
        ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value,
    ):
        if action in FINANCIAL_MUTATION_REMEDIATIONS:
            errors.append(f"Legitimate zero-exposure observation ({exception.exception_type}) prohibits financial remediation '{action}'.")
            return False, errors

    # 3. Typed Parameter Validation
    try:
        if action == PolicyActionType.REFUND.value:
            parsed = RefundParameters(**parameters)
            if exception.exposure and parsed.amount_minor_units > exception.exposure:
                errors.append(
                    f"Requested refund amount ({parsed.amount_minor_units}) exceeds authoritative deterministic exposure ({exception.exposure})."
                )
            if parsed.payment_id:
                gt = session.scalars(select(GatewayTransaction).where(GatewayTransaction.payment_id == parsed.payment_id)).first()
                if not gt and not (exception.primary_payment_id == parsed.payment_id):
                    errors.append(f"Referenced payment_id '{parsed.payment_id}' not found in database records.")

        elif action == PolicyActionType.REVERSE_REFUND.value:
            parsed = ReverseRefundParameters(**parameters)
            if exception.exposure and parsed.amount_minor_units > exception.exposure:
                errors.append(
                    f"Requested reversal amount ({parsed.amount_minor_units}) exceeds authoritative deterministic exposure ({exception.exposure})."
                )

        elif action == PolicyActionType.ALLOCATE_SETTLEMENT.value:
            parsed = AllocateSettlementParameters(**parameters)
            if exception.exposure and parsed.amount_minor_units > exception.exposure:
                errors.append(
                    f"Requested allocation amount ({parsed.amount_minor_units}) exceeds authoritative deterministic exposure ({exception.exposure})."
                )

        elif action == PolicyActionType.RECONCILE.value:
            ReconcileParameters(**parameters)

        elif action == PolicyActionType.ESCALATE.value:
            EscalateParameters(**parameters)

        elif action == PolicyActionType.RESOLVE_EXCEPTION.value:
            ResolveExceptionParameters(**parameters)

    except Exception as e:
        errors.append(f"Parameter validation failed for action '{action}': {str(e)}")

    return len(errors) == 0, errors
