"""Tests verifying Ground Truth model functionality and strict isolation from operational tables."""
from datetime import datetime, timezone
import pytest

from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.financial_sources import GatewayTransaction
from backend.models.enums import ExceptionType
from backend.services.repositories import GroundTruthRepository, FinancialSourceRepository


def utc_now():
    return datetime.now(timezone.utc)


def test_ground_truth_crud_and_query(db_session):
    """Verify evaluation benchmark ground truth cases can be stored and retrieved."""
    repo = GroundTruthRepository(db_session)

    gt = EvaluationGroundTruth(
        case_id="gt_case_ghost_001",
        anomaly_type=ExceptionType.GHOST_SETTLEMENT.value,
        expected_root_cause="UNLINKED_ACQUIRER_SETTLEMENT",
        expected_exposure=750000,  # ₹7500.00
        expected_resolution_class="DISPUTE_CHARGEBACK_PACKET",
        expected_verification_state="VERIFIED_CLOSED",
        created_at=utc_now(),
    )
    repo.save_ground_truth(gt)

    fetched = repo.get_ground_truth("gt_case_ghost_001")
    assert fetched is not None
    assert fetched.case_id == "gt_case_ghost_001"
    assert fetched.anomaly_type == ExceptionType.GHOST_SETTLEMENT.value
    assert fetched.expected_exposure == 750000


def test_ground_truth_isolation_from_operational_tables(db_session):
    """Verify ground truth table is completely separate from operational source tables."""
    gt_repo = GroundTruthRepository(db_session)
    fin_repo = FinancialSourceRepository(db_session)

    # Save a ground truth case
    gt_repo.save_ground_truth(
        EvaluationGroundTruth(
            case_id="gt_isolated_case_01",
            anomaly_type=ExceptionType.PARTIAL_SETTLEMENT.value,
            expected_root_cause="SPLIT_ACQUIRER_BATCH",
            expected_exposure=120000,
            expected_resolution_class="AUTO_CLEAR_ON_SECOND_BATCH",
            expected_verification_state="VERIFIED_CLOSED",
        )
    )

    # Operational source repository must have 0 gateway transactions
    transactions = fin_repo.list_gateway_transactions()
    assert len(transactions) == 0

    # Operational tables do not share foreign key dependencies with ground truth
    assert EvaluationGroundTruth.__tablename__ == "evaluation_ground_truth"
    assert len(EvaluationGroundTruth.__table__.foreign_keys) == 0
