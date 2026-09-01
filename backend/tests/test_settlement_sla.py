"""Unit tests for deterministic Settlement SLA evaluation and processing window calendar logic."""
from datetime import datetime, time, timedelta, timezone
import pytest

from backend.controls.settlement_sla import (
    SettlementSLAConfig,
    SLATimingStatus,
    is_in_processing_window,
    get_next_valid_processing_window_start,
    calculate_expected_settlement_deadline,
    evaluate_settlement_sla,
)
from backend.controls.control_result import ControlStatus
from backend.models.financial_sources import GatewayTransaction, BankSettlementBatch
from backend.models.enums import PaymentStatus


def test_processing_window_calendar_rules():
    """Verifies processing window detection across weekdays, cutoffs, and weekends."""
    config = SettlementSLAConfig(cutoff_hour=18, window_start_hour=9, window_end_hour=18)

    # Monday 10:00 UTC -> inside window
    mon_day = datetime(2026, 8, 3, 10, 0, 0, tzinfo=timezone.utc)
    assert is_in_processing_window(mon_day, config) is True

    # Monday 19:00 UTC (after 18:00 cutoff) -> outside window
    mon_night = datetime(2026, 8, 3, 19, 0, 0, tzinfo=timezone.utc)
    assert is_in_processing_window(mon_night, config) is False

    # Saturday 12:00 UTC -> weekend
    sat = datetime(2026, 8, 8, 12, 0, 0, tzinfo=timezone.utc)
    assert is_in_processing_window(sat, config) is False


def test_next_valid_processing_window_start_calculations():
    """Verifies exact deterministic calculation of the next valid processing window start."""
    config = SettlementSLAConfig()

    # 1. Friday 19:30 UTC -> Next Monday 09:00 UTC
    fri_evening = datetime(2026, 8, 7, 19, 30, 0, tzinfo=timezone.utc)  # Friday
    assert fri_evening.weekday() == 4
    next_start = get_next_valid_processing_window_start(fri_evening, config)
    assert next_start == datetime(2026, 8, 10, 9, 0, 0, tzinfo=timezone.utc)
    assert next_start.weekday() == 0  # Monday

    # 2. Saturday 14:00 UTC -> Next Monday 09:00 UTC
    sat_afternoon = datetime(2026, 8, 8, 14, 0, 0, tzinfo=timezone.utc)
    next_start_sat = get_next_valid_processing_window_start(sat_afternoon, config)
    assert next_start_sat == datetime(2026, 8, 10, 9, 0, 0, tzinfo=timezone.utc)

    # 3. Tuesday 20:00 UTC (post-cutoff) -> Wednesday 09:00 UTC
    tue_night = datetime(2026, 8, 4, 20, 0, 0, tzinfo=timezone.utc)
    next_start_tue = get_next_valid_processing_window_start(tue_night, config)
    assert next_start_tue == datetime(2026, 8, 5, 9, 0, 0, tzinfo=timezone.utc)

    # 4. Wednesday 11:00 UTC (during window) -> Returns same timestamp
    wed_midday = datetime(2026, 8, 5, 11, 0, 0, tzinfo=timezone.utc)
    assert get_next_valid_processing_window_start(wed_midday, config) == wed_midday


def test_settlement_within_sla():
    """Verifies that a payment settled within 24 hours raw elapsed time passes as WITHIN_SLA."""
    t_pay = datetime(2026, 8, 4, 10, 0, 0, tzinfo=timezone.utc)
    t_settle = t_pay + timedelta(hours=8)

    payment = GatewayTransaction(
        payment_id="PAY-SLA-1",
        merchant_id="M1",
        amount=100000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=t_pay,
        method="UPI",
    )
    settlement = BankSettlementBatch(
        settlement_id="SET-SLA-1",
        payment_id="PAY-SLA-1",
        acquirer_id="ACQ-1",
        net_amount=98500,
        interchange_fee_deducted=1200,
        tax_deducted=300,
        clearing_timestamp=t_settle,
    )

    result = evaluate_settlement_sla(payment, [settlement])
    assert result.status == ControlStatus.PASS
    assert result.calculated_values["timing_status"] == SLATimingStatus.WITHIN_SLA.value


def test_settlement_late_but_valid_timing_scenario():
    """Verifies that a Friday evening transaction settled Monday morning is recognized as LATE_BUT_VALID."""
    # Friday 19:35 UTC (after 18:00 cutoff)
    t_pay = datetime(2026, 8, 7, 19, 35, 0, tzinfo=timezone.utc)
    # Clears Monday 09:35 UTC (62 hours raw elapsed, but 35 mins from Monday 09:00 start)
    t_settle = t_pay + timedelta(hours=62)

    payment = GatewayTransaction(
        payment_id="PAY-TIMING-1",
        merchant_id="M1",
        amount=1000000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=t_pay,
        method="CARD",
    )
    settlement = BankSettlementBatch(
        settlement_id="SET-TIMING-1",
        payment_id="PAY-TIMING-1",
        acquirer_id="ACQ-HDFC",
        net_amount=985000,
        interchange_fee_deducted=12711,
        tax_deducted=2289,
        clearing_timestamp=t_settle,
    )

    result = evaluate_settlement_sla(payment, [settlement])
    assert result.status == ControlStatus.PASS  # Legitimate timing must NOT fail!
    assert result.calculated_values["timing_status"] == SLATimingStatus.LATE_BUT_VALID.value


def test_settlement_genuine_sla_breach():
    """Verifies that a payment clearing beyond SLA deadline triggers a FAIL / SLA_BREACH."""
    # Tuesday 10:00 UTC -> SLA deadline is Wednesday 10:00 UTC
    t_pay = datetime(2026, 8, 4, 10, 0, 0, tzinfo=timezone.utc)
    # Clears 54 hours later on Thursday 16:00 UTC
    t_settle = t_pay + timedelta(hours=54)

    payment = GatewayTransaction(
        payment_id="PAY-BREACH-1",
        merchant_id="M1",
        amount=2000000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=t_pay,
        method="UPI",
    )
    settlement = BankSettlementBatch(
        settlement_id="SET-BREACH-1",
        payment_id="PAY-BREACH-1",
        acquirer_id="ACQ-ICICI",
        net_amount=1970000,
        interchange_fee_deducted=25423,
        tax_deducted=4577,
        clearing_timestamp=t_settle,
    )

    result = evaluate_settlement_sla(payment, [settlement])
    assert result.status == ControlStatus.FAIL
    assert result.severity == "HIGH"
    assert result.calculated_values["timing_status"] == SLATimingStatus.SLA_BREACH.value


def test_settlement_sla_not_applicable_for_failed_payment():
    """Verifies that FAILED payments receive NOT_APPLICABLE status."""
    now = datetime.now(timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-FAILED-1",
        merchant_id="M1",
        amount=500000,
        currency="INR",
        status=PaymentStatus.FAILED.value,
        created_at=now,
        method="CARD",
    )

    result = evaluate_settlement_sla(payment, [])
    assert result.status == ControlStatus.NOT_APPLICABLE
    assert result.calculated_values["timing_status"] == SLATimingStatus.NOT_APPLICABLE.value
