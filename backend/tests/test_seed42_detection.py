"""Comprehensive end-to-end detection benchmark verification on Seed 42 synthetic dataset (60 cases / 270 operational records)."""
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.data.generator.service import generate_dataset
from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.enums import ExceptionType
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.exceptions.service import ExceptionDetectionService


def test_seed42_end_to_end_detection_and_ground_truth_alignment(db_session: Session):
    """Executes deterministic exception detection on the full standard Seed 42 dataset and validates all scenario families."""
    # 1. Generate full standard Seed 42 dataset (60 cases)
    summary = generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()

    assert summary["dataset_id"] is not None
    assert summary["seed"] == 42
    assert summary["total_financial_records"] == 270

    # Verify counts in database match the 270 operational records exactly
    gw_count = len(list(db_session.scalars(select(GatewayTransaction)).all()))
    ord_count = len(list(db_session.scalars(select(MerchantOrder)).all()))
    set_count = len(list(db_session.scalars(select(BankSettlementBatch)).all()))
    disp_count = len(list(db_session.scalars(select(DisputeRefundEvent)).all()))
    led_count = len(list(db_session.scalars(select(NodalLedgerEntry)).all()))

    assert gw_count == 60
    assert ord_count == 60
    assert set_count == 62
    assert disp_count == 13
    assert led_count == 75
    assert gw_count + ord_count + set_count + disp_count + led_count == 270

    # 2. Run deterministic detection service
    service = ExceptionDetectionService()
    report = service.detect_exceptions(session=db_session)

    # 3. Assert detection metrics & category separation
    assert report.total_detected_count == 14
    assert report.new_exception_count == 14
    assert report.legitimate_case_count == 4  # 2 partial settlements + 2 timing exceptions

    # Separation: Actionable Financial Exceptions vs Legitimate Observations
    actionable_exceptions = [e for e in report.exceptions if not e["is_legitimate_observation"]]
    legitimate_observations = [e for e in report.exceptions if e["is_legitimate_observation"]]

    assert len(actionable_exceptions) == 10  # 2 Ghost + 2 DoubleDip + 2 SLABreach + 2 Missing + 2 Unallocated
    assert len(legitimate_observations) == 4  # 2 Partial + 2 Timing

    # 4. Check breakdown per MVP exception family
    breakdown = report.exception_type_breakdown
    assert breakdown.get(ExceptionType.GHOST_SETTLEMENT.value) == 2
    assert breakdown.get(ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value) == 2
    assert breakdown.get(ExceptionType.SETTLEMENT_SLA_BREACH.value) == 2
    assert breakdown.get(ExceptionType.PARTIAL_SETTLEMENT.value) == 2
    assert breakdown.get(ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value) == 4
    assert breakdown.get(ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value) == 2

    # 5. Check exposure: Strict integer minor units
    assert isinstance(report.total_exposure, int)
    assert report.total_exposure > 0
    assert all(isinstance(e["exposure"], int) for e in report.exceptions)
    assert all(e["exposure"] == 0 for e in legitimate_observations)
    assert all(e["exposure"] > 0 for e in actionable_exceptions)

    # 6. Post-detection evaluation step: Compare detected cases with evaluation ground truth
    ground_truth = list(db_session.scalars(select(EvaluationGroundTruth)).all())
    assert len(ground_truth) == 14  # Ground truth records generated

    # Map detected exception types
    detected_types = {e["exception_type"] for e in report.exceptions}
    gt_types = {gt.anomaly_type for gt in ground_truth}
    assert detected_types == gt_types
