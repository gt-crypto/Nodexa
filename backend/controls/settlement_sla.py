"""Deterministic Settlement SLA evaluation and processing window calendar logic."""
from dataclasses import dataclass, field
from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Set

from backend.controls.control_result import ControlResult, ControlStatus, EvidenceItem
from backend.models.financial_sources import GatewayTransaction, BankSettlementBatch
from backend.models.enums import PaymentStatus


class SLATimingStatus(str, Enum):
    """Timing classification for settlement clearance."""
    WITHIN_SLA = "WITHIN_SLA"
    LATE_BUT_VALID = "LATE_BUT_VALID"
    SLA_BREACH = "SLA_BREACH"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    MISSING = "MISSING"


@dataclass
class SettlementSLAConfig:
    """Configurable parameters for synthetic settlement SLA evaluation."""
    sla_hours: int = 24
    cutoff_hour: int = 18  # 18:00 UTC daily processing cutoff
    window_start_hour: int = 9  # 09:00 UTC window start
    window_end_hour: int = 18  # 18:00 UTC window end
    weekend_days: Set[int] = field(default_factory=lambda: {5, 6})  # 5=Saturday, 6=Sunday


def is_in_processing_window(dt: datetime, config: Optional[SettlementSLAConfig] = None) -> bool:
    """Returns True if the timestamp falls within active daily processing window on a business day."""
    cfg = config or SettlementSLAConfig()
    # Normalize to UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    if dt.weekday() in cfg.weekend_days:
        return False
    
    cutoff_time = time(cfg.window_end_hour, 0, 0)
    start_time = time(cfg.window_start_hour, 0, 0)
    return start_time <= dt.time() < cutoff_time


def get_next_valid_processing_window_start(dt: datetime, config: Optional[SettlementSLAConfig] = None) -> datetime:
    """Calculates the start timestamp of the next valid processing window.
    
    - If dt is inside a valid window, returns dt itself.
    - If dt is on a weekday before window_start_hour, returns same day at window_start_hour.
    - If dt is on a weekday at or after cutoff_hour (18:00):
      - Friday -> Monday 09:00 UTC
      - Mon-Thu -> Next day 09:00 UTC
    - If dt is on Saturday -> Next Monday 09:00 UTC
    - If dt is on Sunday -> Next Monday 09:00 UTC
    """
    cfg = config or SettlementSLAConfig()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    weekday = dt.weekday()

    # Weekend check
    if weekday == 5:  # Saturday -> Monday
        days_ahead = 2
        return (dt + timedelta(days=days_ahead)).replace(
            hour=cfg.window_start_hour, minute=0, second=0, microsecond=0
        )
    elif weekday == 6:  # Sunday -> Monday
        days_ahead = 1
        return (dt + timedelta(days=days_ahead)).replace(
            hour=cfg.window_start_hour, minute=0, second=0, microsecond=0
        )

    # Weekday checks (0 = Mon .. 4 = Fri)
    current_time = dt.time()
    start_time = time(cfg.window_start_hour, 0, 0)
    end_time = time(cfg.window_end_hour, 0, 0)

    if current_time < start_time:
        return dt.replace(hour=cfg.window_start_hour, minute=0, second=0, microsecond=0)
    elif start_time <= current_time < end_time:
        return dt
    else:
        # After cutoff
        if weekday == 4:  # Friday evening -> Monday 09:00
            days_ahead = 3
        else:
            days_ahead = 1
        return (dt + timedelta(days=days_ahead)).replace(
            hour=cfg.window_start_hour, minute=0, second=0, microsecond=0
        )


def calculate_expected_settlement_deadline(
    payment_time: datetime,
    config: Optional[SettlementSLAConfig] = None,
) -> datetime:
    """Calculates the deterministic expected settlement deadline considering processing windows."""
    cfg = config or SettlementSLAConfig()
    effective_start = get_next_valid_processing_window_start(payment_time, cfg)
    return effective_start + timedelta(hours=cfg.sla_hours)


def evaluate_settlement_sla(
    payment: GatewayTransaction,
    settlements: List[BankSettlementBatch],
    current_time: Optional[datetime] = None,
    config: Optional[SettlementSLAConfig] = None,
) -> ControlResult:
    """Deterministically evaluates settlement timing and SLA compliance for a payment."""
    cfg = config or SettlementSLAConfig()
    payment_id = payment.payment_id
    
    # SLA only applies to captured payments
    if payment.status != PaymentStatus.CAPTURED.value:
        return ControlResult(
            control_id=f"CTRL-SLA-{payment_id}",
            control_name="Settlement SLA Evaluation",
            status=ControlStatus.NOT_APPLICABLE,
            affected_record_ids=[payment_id],
            rule="SLA evaluation only applies to CAPTURED payments.",
            calculated_values={"timing_status": SLATimingStatus.NOT_APPLICABLE.value},
        )

    payment_time = payment.created_at
    if payment_time.tzinfo is None:
        payment_time = payment_time.replace(tzinfo=timezone.utc)

    effective_start = get_next_valid_processing_window_start(payment_time, cfg)
    expected_deadline = calculate_expected_settlement_deadline(payment_time, cfg)

    # Filter settlements for this payment
    payment_settlements = [
        s for s in settlements if s.payment_id == payment_id or (s.raw_payment_reference and payment_id in s.raw_payment_reference)
    ]

    # No settlements found
    if not payment_settlements:
        now = current_time or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        is_past_deadline = now > expected_deadline
        timing_status = SLATimingStatus.MISSING if is_past_deadline else SLATimingStatus.WITHIN_SLA

        if is_past_deadline:
            return ControlResult(
                control_id=f"CTRL-SLA-{payment_id}",
                control_name="Settlement SLA Evaluation",
                status=ControlStatus.FAIL,
                severity="HIGH",
                affected_record_ids=[payment_id],
                rule=f"Payment must settle within {cfg.sla_hours} hours of next valid processing window.",
                calculated_values={
                    "timing_status": timing_status.value,
                    "payment_created_at": payment_time.isoformat(),
                    "effective_window_start": effective_start.isoformat(),
                    "expected_deadline": expected_deadline.isoformat(),
                    "as_of_time": now.isoformat(),
                },
                expected_values={"settlement_present": True, "deadline": expected_deadline.isoformat()},
                actual_values={"settlement_present": False, "clearing_timestamp": None},
                evidence=[
                    EvidenceItem(
                        source="gateway_transactions",
                        record_id=payment_id,
                        field="status",
                        value=payment.status,
                        comparison="Payment CAPTURED without settlement records",
                    ),
                ],
            )
        else:
            return ControlResult(
                control_id=f"CTRL-SLA-{payment_id}",
                control_name="Settlement SLA Evaluation",
                status=ControlStatus.PASS,
                affected_record_ids=[payment_id],
                rule=f"Payment pending within {cfg.sla_hours}h SLA window.",
                calculated_values={
                    "timing_status": timing_status.value,
                    "payment_created_at": payment_time.isoformat(),
                    "expected_deadline": expected_deadline.isoformat(),
                },
            )

    # Has settlements -> evaluate clearing timestamp
    latest_clearing_time = max(
        s.clearing_timestamp if s.clearing_timestamp.tzinfo else s.clearing_timestamp.replace(tzinfo=timezone.utc)
        for s in payment_settlements
    )

    elapsed_raw_hours = (latest_clearing_time - payment_time).total_seconds() / 3600.0
    elapsed_window_hours = (latest_clearing_time - effective_start).total_seconds() / 3600.0

    if elapsed_raw_hours <= cfg.sla_hours:
        # Standard within SLA
        timing_status = SLATimingStatus.WITHIN_SLA
        control_status = ControlStatus.PASS
        severity = None
    elif latest_clearing_time <= expected_deadline:
        # Late by raw elapsed time, but valid under processing calendar / window
        timing_status = SLATimingStatus.LATE_BUT_VALID
        control_status = ControlStatus.PASS
        severity = None
    else:
        # Genuine SLA breach
        timing_status = SLATimingStatus.SLA_BREACH
        control_status = ControlStatus.FAIL
        severity = "HIGH"

    evidence = [
        EvidenceItem(
            source="gateway_transactions",
            record_id=payment_id,
            field="created_at",
            value=payment_time.isoformat(),
        ),
        EvidenceItem(
            source="bank_settlement_batches",
            record_id=payment_settlements[0].settlement_id,
            field="clearing_timestamp",
            value=latest_clearing_time.isoformat(),
            comparison=f"Cleared in {elapsed_raw_hours:.2f}h raw ({elapsed_window_hours:.2f}h from window start) vs {cfg.sla_hours}h SLA",
        ),
    ]

    return ControlResult(
        control_id=f"CTRL-SLA-{payment_id}",
        control_name="Settlement SLA Evaluation",
        status=control_status,
        severity=severity,
        affected_record_ids=[payment_id] + [s.settlement_id for s in payment_settlements],
        rule=f"Captured payment must clear settlement within {cfg.sla_hours} hours of next valid processing window.",
        calculated_values={
            "timing_status": timing_status.value,
            "elapsed_raw_hours": round(elapsed_raw_hours, 2),
            "elapsed_window_hours": round(elapsed_window_hours, 2),
            "effective_window_start": effective_start.isoformat(),
            "expected_deadline": expected_deadline.isoformat(),
            "latest_clearing_timestamp": latest_clearing_time.isoformat(),
        },
        expected_values={"expected_deadline": expected_deadline.isoformat()},
        actual_values={"clearing_timestamp": latest_clearing_time.isoformat(), "timing_status": timing_status.value},
        evidence=evidence,
    )
