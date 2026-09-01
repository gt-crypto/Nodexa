"""Deterministic materiality and financial exposure type classification."""
from typing import Optional

from backend.models.enums import ExposureType, MaterialityLevel, ExceptionType
from backend.exposure.config import (
    EXPOSURE_NONE,
    EXPOSURE_LOW,
    EXPOSURE_MEDIUM,
    EXPOSURE_HIGH,
    EXPOSURE_MATERIAL,
    EXPOSURE_SEVERE,
)


def classify_exposure_type(
    exception_type: str,
    sub_type: Optional[str] = None,
    exposure: int = 0,
) -> str:
    """Classifies the financial exposure type deterministically from the exception taxonomy."""
    # Legitimate observations with zero exposure have no financial risk
    if exposure <= 0:
        return ExposureType.NO_FINANCIAL_EXPOSURE.value

    if exception_type == ExceptionType.GHOST_SETTLEMENT.value:
        return ExposureType.FUNDS_AT_RISK.value
    elif exception_type == ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value:
        return ExposureType.DIRECT_FINANCIAL_LOSS.value
    elif exception_type == ExceptionType.SETTLEMENT_SLA_BREACH.value:
        return ExposureType.SLA_DELAY_IMPACT.value
    elif exception_type == ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value:
        if sub_type == "UNALLOCATED_SETTLEMENT":
            return ExposureType.FUNDS_AT_RISK.value
        return ExposureType.FUNDS_AT_RISK.value
    elif exception_type == ExceptionType.PARTIAL_SETTLEMENT.value:
        return ExposureType.NO_FINANCIAL_EXPOSURE.value
    elif exception_type == ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value:
        return ExposureType.NO_FINANCIAL_EXPOSURE.value

    return ExposureType.OPERATIONAL_RISK.value


def classify_materiality(exposure: int) -> str:
    """Deterministically classifies financial materiality level based on configured integer thresholds."""
    if exposure <= EXPOSURE_NONE:
        return MaterialityLevel.NONE.value
    elif exposure < EXPOSURE_LOW:
        return MaterialityLevel.LOW.value
    elif exposure < EXPOSURE_MEDIUM:
        return MaterialityLevel.MEDIUM.value
    elif exposure < EXPOSURE_HIGH:
        return MaterialityLevel.HIGH.value
    elif exposure < EXPOSURE_SEVERE:
        return MaterialityLevel.MATERIAL.value
    else:
        return MaterialityLevel.SEVERE.value


def calculate_relative_materiality_bps(exposure: int, account_balance: Optional[int] = None) -> int:
    """Calculates relative materiality as integer basis points (0-10000 bps) of account balance."""
    if not account_balance or account_balance <= 0 or exposure <= 0:
        return 0
    bps = (exposure * 10000) // account_balance
    return min(10000, max(0, bps))
