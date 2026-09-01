"""Unit tests for deterministic financial exposure and materiality classification."""
import pytest
from backend.models.enums import ExposureType, MaterialityLevel, ExceptionType
from backend.exposure.materiality import (
    classify_exposure_type,
    classify_materiality,
    calculate_relative_materiality_bps,
)
from backend.exposure.config import (
    EXPOSURE_LOW,
    EXPOSURE_MEDIUM,
    EXPOSURE_HIGH,
    EXPOSURE_MATERIAL,
    EXPOSURE_SEVERE,
)


def test_exposure_type_classification_all_families():
    """Verifies deterministic mapping of exception families to exposure types."""
    # 1. Ghost settlement -> FUNDS_AT_RISK
    assert classify_exposure_type(ExceptionType.GHOST_SETTLEMENT.value, exposure=5000000) == ExposureType.FUNDS_AT_RISK.value

    # 2. Refund + Chargeback -> DIRECT_FINANCIAL_LOSS
    assert classify_exposure_type(ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value, exposure=2500000) == ExposureType.DIRECT_FINANCIAL_LOSS.value

    # 3. SLA Breach -> SLA_DELAY_IMPACT
    assert classify_exposure_type(ExceptionType.SETTLEMENT_SLA_BREACH.value, exposure=1500000) == ExposureType.SLA_DELAY_IMPACT.value

    # 4. Missing settlement -> FUNDS_AT_RISK
    assert classify_exposure_type(ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value, sub_type="MISSING_SETTLEMENT", exposure=1000000) == ExposureType.FUNDS_AT_RISK.value

    # 5. Unallocated settlement -> FUNDS_AT_RISK
    assert classify_exposure_type(ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value, sub_type="UNALLOCATED_SETTLEMENT", exposure=1000000) == ExposureType.FUNDS_AT_RISK.value

    # 6. Legitimate partial settlement -> NO_FINANCIAL_EXPOSURE
    assert classify_exposure_type(ExceptionType.PARTIAL_SETTLEMENT.value, exposure=0) == ExposureType.NO_FINANCIAL_EXPOSURE.value

    # 7. Legitimate timing exception -> NO_FINANCIAL_EXPOSURE
    assert classify_exposure_type(ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value, exposure=0) == ExposureType.NO_FINANCIAL_EXPOSURE.value


def test_materiality_thresholds():
    """Verifies deterministic materiality level classification against integer thresholds."""
    # Zero exposure -> NONE
    assert classify_materiality(0) == MaterialityLevel.NONE.value
    assert classify_materiality(-100) == MaterialityLevel.NONE.value

    # Below LOW -> LOW
    assert classify_materiality(EXPOSURE_LOW - 1) == MaterialityLevel.LOW.value

    # Between LOW and MEDIUM -> MEDIUM
    assert classify_materiality(EXPOSURE_LOW) == MaterialityLevel.MEDIUM.value
    assert classify_materiality(EXPOSURE_MEDIUM - 1) == MaterialityLevel.MEDIUM.value

    # Between MEDIUM and HIGH -> HIGH
    assert classify_materiality(EXPOSURE_MEDIUM) == MaterialityLevel.HIGH.value
    assert classify_materiality(EXPOSURE_HIGH - 1) == MaterialityLevel.HIGH.value

    # Between HIGH and SEVERE -> MATERIAL
    assert classify_materiality(EXPOSURE_HIGH) == MaterialityLevel.MATERIAL.value
    assert classify_materiality(EXPOSURE_SEVERE - 1) == MaterialityLevel.MATERIAL.value

    # Above SEVERE -> SEVERE
    assert classify_materiality(EXPOSURE_SEVERE) == MaterialityLevel.SEVERE.value
    assert classify_materiality(EXPOSURE_SEVERE + 5000000) == MaterialityLevel.SEVERE.value


def test_relative_materiality_basis_points():
    """Verifies integer-safe relative materiality calculation in basis points (1 bps = 0.01%)."""
    # 1. Zero balance or zero exposure
    assert calculate_relative_materiality_bps(0, 100000000) == 0
    assert calculate_relative_materiality_bps(5000000, 0) == 0

    # 2. ₹50,000 exposure out of ₹1,000,000 balance = 5% = 500 bps
    exposure = 5000000   # 50,000 INR
    balance = 100000000  # 1,000,000 INR
    assert calculate_relative_materiality_bps(exposure, balance) == 500

    # 3. 100% or higher capped at 10,000 bps
    assert calculate_relative_materiality_bps(100000000, 50000000) == 10000
