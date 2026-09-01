"""Unit tests for deterministic exception classifiers, exposures, and severity assignments."""
from datetime import datetime, timezone, timedelta
import pytest

from backend.models.enums import ExceptionType, ExceptionSeverity, PaymentStatus, OrderFulfillmentStatus, DisputeEventType
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.controls.control_result import ControlResult, ControlStatus
from backend.controls.settlement_sla import SLATimingStatus
from backend.exceptions.correlator import CorrelatedEntity
from backend.exceptions.classifiers import (
    classify_ghost_settlement,
    classify_refund_chargeback_double_dip,
    classify_settlement_sla_breach,
    classify_legitimate_partial_settlement,
    classify_missing_settlement,
    classify_unallocated_settlement,
    classify_legitimate_timing_exception,
)
from backend.exceptions.exposure import calculate_exception_exposure
from backend.exceptions.severity import assign_exception_severity, SeverityConfig


def test_classify_ghost_settlement():
    """Verifies that a failed payment with bank settlement credit is classified as GHOST_SETTLEMENT."""
    now = datetime.now(timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-GHOST-1",
        merchant_id="M1",
        amount=4500000,
        currency="INR",
        status=PaymentStatus.FAILED.value,
        created_at=now,
        method="CARD",
    )
    settlement = BankSettlementBatch(
        settlement_id="SET-GHOST-1",
        payment_id="PAY-GHOST-1",
        acquirer_id="A1",
        net_amount=4432500,
        interchange_fee_deducted=57203,
        tax_deducted=10297,
        clearing_timestamp=now + timedelta(hours=6),
    )
    entity = CorrelatedEntity(
        entity_key="PAY-GHOST-1",
        payment=payment,
        settlements=[settlement],
    )

    cls_res = classify_ghost_settlement(entity)
    assert cls_res is not None
    assert cls_res.exception_type == ExceptionType.GHOST_SETTLEMENT
    assert cls_res.exposure == 4432500
    assert cls_res.severity == ExceptionSeverity.CRITICAL
    assert cls_res.is_legitimate_observation is False


def test_classify_refund_chargeback_double_dip():
    """Verifies that overlapping refund and chargeback events are classified as REFUND_CHARGEBACK_DOUBLE_DIP."""
    now = datetime.now(timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-DBL-1",
        merchant_id="M1",
        amount=5000000,
        currency="INR",
        status=PaymentStatus.DISPUTED.value,
        created_at=now,
        method="CARD",
    )
    disputes = [
        DisputeRefundEvent(event_id="EVT-REF-1", payment_id="PAY-DBL-1", event_type="REFUND", amount=5000000, timestamp=now + timedelta(days=1)),
        DisputeRefundEvent(event_id="EVT-CB-1", payment_id="PAY-DBL-1", event_type="CHARGEBACK", amount=5000000, timestamp=now + timedelta(days=3)),
    ]
    entity = CorrelatedEntity(
        entity_key="PAY-DBL-1",
        payment=payment,
        disputes=disputes,
    )

    cls_res = classify_refund_chargeback_double_dip(entity)
    assert cls_res is not None
    assert cls_res.exception_type == ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP
    assert cls_res.exposure == 5000000
    assert cls_res.severity == ExceptionSeverity.CRITICAL


def test_classify_settlement_sla_breach():
    """Verifies that an SLA breach finding is classified as SETTLEMENT_SLA_BREACH."""
    now = datetime.now(timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-SLA-1",
        merchant_id="M1",
        amount=2000000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
        method="UPI",
    )
    settlement = BankSettlementBatch(
        settlement_id="SET-SLA-1",
        payment_id="PAY-SLA-1",
        acquirer_id="A1",
        net_amount=1970000,
        clearing_timestamp=now + timedelta(hours=54),
    )
    ctrl_result = ControlResult(
        control_id="CTRL-SLA-PAY-SLA-1",
        control_name="Settlement SLA Evaluation",
        status=ControlStatus.FAIL,
        affected_record_ids=["PAY-SLA-1"],
        calculated_values={"timing_status": SLATimingStatus.SLA_BREACH.value, "elapsed_raw_hours": 54.0},
    )
    entity = CorrelatedEntity(
        entity_key="PAY-SLA-1",
        payment=payment,
        settlements=[settlement],
        control_results=[ctrl_result],
    )

    cls_res = classify_settlement_sla_breach(entity)
    assert cls_res is not None
    assert cls_res.exception_type == ExceptionType.SETTLEMENT_SLA_BREACH
    assert cls_res.exposure == 2000000
    assert cls_res.severity == ExceptionSeverity.HIGH


def test_classify_legitimate_partial_settlement_zero_exposure():
    """Verifies that a legitimate multi-tranche partial settlement has zero exposure and LOW severity."""
    now = datetime.now(timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-PART-1",
        merchant_id="M1",
        amount=1000000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
        method="CARD",
    )
    settlements = [
        BankSettlementBatch(settlement_id="S1", payment_id="PAY-PART-1", acquirer_id="A1", net_amount=394000, interchange_fee_deducted=5085, tax_deducted=915, clearing_timestamp=now),
        BankSettlementBatch(settlement_id="S2", payment_id="PAY-PART-1", acquirer_id="A1", net_amount=295500, interchange_fee_deducted=3814, tax_deducted=686, clearing_timestamp=now),
        BankSettlementBatch(settlement_id="S3", payment_id="PAY-PART-1", acquirer_id="A1", net_amount=295500, interchange_fee_deducted=3814, tax_deducted=686, clearing_timestamp=now),
    ]
    entity = CorrelatedEntity(
        entity_key="PAY-PART-1",
        payment=payment,
        settlements=settlements,
    )

    cls_res = classify_legitimate_partial_settlement(entity)
    assert cls_res is not None
    assert cls_res.exception_type == ExceptionType.PARTIAL_SETTLEMENT
    assert cls_res.exposure == 0
    assert cls_res.severity == ExceptionSeverity.LOW
    assert cls_res.is_legitimate_observation is True


def test_classify_missing_and_unallocated_settlements():
    """Verifies classifications for missing and unallocated settlements."""
    now = datetime.now(timezone.utc)

    # 1. Missing Settlement
    pmt_missing = GatewayTransaction(
        payment_id="PAY-MISS-1",
        merchant_id="M1",
        amount=3000000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
        method="UPI",
    )
    entity_missing = CorrelatedEntity(entity_key="PAY-MISS-1", payment=pmt_missing, settlements=[])
    cls_missing = classify_missing_settlement(entity_missing)
    assert cls_missing is not None
    assert cls_missing.exception_type == ExceptionType.MISSING_UNALLOCATED_SETTLEMENT
    assert cls_missing.sub_type == "MISSING_SETTLEMENT"
    assert cls_missing.exposure == 3000000

    # 2. Unallocated Settlement
    settle_unallocated = BankSettlementBatch(
        settlement_id="SET-ORPHAN-1",
        utr_number="UTR-ORPHAN-1",
        acquirer_id="A1",
        payment_id=None,
        net_amount=2500000,
        clearing_timestamp=now,
    )
    entity_unallocated = CorrelatedEntity(entity_key="settlement_SET-ORPHAN-1", payment=None, settlements=[settle_unallocated])
    cls_unallocated = classify_unallocated_settlement(entity_unallocated)
    assert cls_unallocated is not None
    assert cls_unallocated.exception_type == ExceptionType.MISSING_UNALLOCATED_SETTLEMENT
    assert cls_unallocated.sub_type == "UNALLOCATED_SETTLEMENT"
    assert cls_unallocated.exposure == 2500000


def test_classify_legitimate_timing_exception_zero_exposure():
    """Verifies that a legitimate timing exception (LATE_BUT_VALID) has zero exposure."""
    now = datetime.now(timezone.utc)
    payment = GatewayTransaction(
        payment_id="PAY-TIME-1",
        merchant_id="M1",
        amount=1500000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
        method="CARD",
    )
    ctrl_result = ControlResult(
        control_id="CTRL-SLA-PAY-TIME-1",
        control_name="Settlement SLA Evaluation",
        status=ControlStatus.PASS,
        affected_record_ids=["PAY-TIME-1"],
        calculated_values={"timing_status": SLATimingStatus.LATE_BUT_VALID.value},
    )
    entity = CorrelatedEntity(
        entity_key="PAY-TIME-1",
        payment=payment,
        control_results=[ctrl_result],
    )

    cls_res = classify_legitimate_timing_exception(entity)
    assert cls_res is not None
    assert cls_res.exception_type == ExceptionType.LEGITIMATE_TIMING_EXCEPTION
    assert cls_res.exposure == 0
    assert cls_res.severity == ExceptionSeverity.LOW
    assert cls_res.is_legitimate_observation is True
