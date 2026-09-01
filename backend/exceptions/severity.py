"""Deterministic severity classification based on exception category and financial exposure."""
from dataclasses import dataclass
from backend.models.enums import ExceptionType, ExceptionSeverity


@dataclass
class SeverityConfig:
    """Configurable thresholds for deterministic severity assignment."""
    critical_exposure_threshold: int = 5_000_000   # ₹50,000.00
    high_exposure_threshold: int = 2_000_000       # ₹20,000.00
    medium_exposure_threshold: int = 500_000       # ₹5,000.00


def assign_exception_severity(
    exception_type: ExceptionType | str,
    exposure: int,
    config: SeverityConfig | None = None,
) -> ExceptionSeverity:
    """Deterministically assigns severity (LOW, MEDIUM, HIGH, CRITICAL)."""
    cfg = config or SeverityConfig()
    exc_type_val = exception_type.value if isinstance(exception_type, ExceptionType) else str(exception_type)

    # Legitimate / cleared observations
    if exc_type_val in (ExceptionType.PARTIAL_SETTLEMENT.value, ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value):
        return ExceptionSeverity.LOW

    # High severity / Critical baseline for severe financial anomalies
    if exposure >= cfg.critical_exposure_threshold:
        return ExceptionSeverity.CRITICAL

    if exc_type_val == ExceptionType.GHOST_SETTLEMENT.value:
        return ExceptionSeverity.CRITICAL if exposure >= 3_000_000 else ExceptionSeverity.HIGH

    if exc_type_val == ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value:
        return ExceptionSeverity.CRITICAL if exposure >= 3_000_000 else ExceptionSeverity.HIGH

    if exc_type_val == ExceptionType.SETTLEMENT_SLA_BREACH.value:
        return ExceptionSeverity.HIGH if exposure >= cfg.high_exposure_threshold else ExceptionSeverity.MEDIUM

    if exc_type_val == ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value:
        return ExceptionSeverity.HIGH if exposure >= cfg.high_exposure_threshold else ExceptionSeverity.MEDIUM

    if exposure >= cfg.high_exposure_threshold:
        return ExceptionSeverity.HIGH
    elif exposure >= cfg.medium_exposure_threshold:
        return ExceptionSeverity.MEDIUM
    else:
        return ExceptionSeverity.LOW
