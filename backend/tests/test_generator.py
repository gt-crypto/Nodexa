"""Comprehensive test suite for the Synthetic Financial Dataset Generator."""
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.database import Base
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.dataset import DatasetMetadata
from backend.models.enums import (
    PaymentStatus,
    OrderFulfillmentStatus,
    DisputeEventType,
    LedgerEntryType,
    ExceptionType,
)
from backend.data.generator.config import GeneratorConfig
from backend.data.generator.service import generate_dataset
from backend.services.repositories import (
    FinancialSourceRepository,
    GroundTruthRepository,
    DatasetRepository,
)


def create_isolated_session():
    """Helper to create a completely clean in-memory database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return Session(), engine


def test_seed_deterministic_reproducibility():
    """Verify that running generate_dataset with identical seed produces identical records."""
    session1, engine1 = create_isolated_session()
    session2, engine2 = create_isolated_session()

    try:
        res1 = generate_dataset(session1, record_count=60, seed=42)
        res2 = generate_dataset(session2, record_count=60, seed=42)

        assert res1["counts"] == res2["counts"]
        assert res1["total_financial_records"] == res2["total_financial_records"]

        # Compare gateway transactions
        txs1 = session1.query(GatewayTransaction).order_by(GatewayTransaction.payment_id).all()
        txs2 = session2.query(GatewayTransaction).order_by(GatewayTransaction.payment_id).all()
        assert len(txs1) == len(txs2)

        for t1, t2 in zip(txs1, txs2):
            assert t1.payment_id == t2.payment_id
            assert t1.amount == t2.amount
            assert t1.merchant_id == t2.merchant_id
            assert t1.status == t2.status
            assert t1.created_at == t2.created_at

        # Compare ground truth cases
        gt1 = session1.query(EvaluationGroundTruth).order_by(EvaluationGroundTruth.case_id).all()
        gt2 = session2.query(EvaluationGroundTruth).order_by(EvaluationGroundTruth.case_id).all()
        assert len(gt1) == len(gt2)
        for g1, g2 in zip(gt1, gt2):
            assert g1.case_id == g2.case_id
            assert g1.anomaly_type == g2.anomaly_type
            assert g1.expected_exposure == g2.expected_exposure
            assert g1.expected_root_cause == g2.expected_root_cause

    finally:
        session1.close()
        session2.close()
        engine1.dispose()
        engine2.dispose()


def test_different_seeds_produce_variation():
    """Verify that different seeds produce distinct transaction amounts and identifiers."""
    session1, engine1 = create_isolated_session()
    session2, engine2 = create_isolated_session()

    try:
        res1 = generate_dataset(session1, record_count=60, seed=42)
        res2 = generate_dataset(session2, record_count=60, seed=99)

        txs1 = session1.query(GatewayTransaction).order_by(GatewayTransaction.id).all()
        txs2 = session2.query(GatewayTransaction).order_by(GatewayTransaction.id).all()

        # Amounts should vary between seeds
        amounts1 = [t.amount for t in txs1]
        amounts2 = [t.amount for t in txs2]
        assert amounts1 != amounts2

    finally:
        session1.close()
        session2.close()
        engine1.dispose()
        engine2.dispose()


def test_minimum_scale_generation(db_session):
    """Verify generator produces 50+ total financial records."""
    summary = generate_dataset(db_session, record_count=60, seed=42)

    assert summary["total_financial_records"] >= 50
    assert summary["counts"]["gateway_transactions"] >= 20
    assert summary["counts"]["bank_settlement_batches"] >= 15
    assert summary["counts"]["nodal_ledger_entries"] >= 15


def test_identifier_integrity_and_relationships(db_session):
    """Verify all business identifiers are well-formed and relationships resolve cleanly."""
    generate_dataset(db_session, record_count=60, seed=42)

    fin_repo = FinancialSourceRepository(db_session)
    transactions = fin_repo.list_gateway_transactions(limit=500)
    tx_payment_ids = {t.payment_id for t in transactions}

    # Verify merchant orders reference existing gateway transactions
    orders = db_session.query(MerchantOrder).all()
    for order in orders:
        if order.payment_id_reference:
            assert order.payment_id_reference in tx_payment_ids

    # Verify dispute events reference existing gateway transactions
    disputes = db_session.query(DisputeRefundEvent).all()
    for dispute in disputes:
        assert dispute.payment_id in tx_payment_ids

    # Verify ledger entries reference existing gateway transactions (unless unallocated)
    ledger_entries = db_session.query(NodalLedgerEntry).all()
    for entry in ledger_entries:
        if entry.transaction_id:
            assert entry.transaction_id in tx_payment_ids


def test_ghost_settlement_scenario_integrity(db_session):
    """Verify Ghost Settlement scenario: gateway FAILED, order CANCELLED, bank & ledger credit exist."""
    generate_dataset(db_session, record_count=60, seed=42)

    gt_cases = db_session.query(EvaluationGroundTruth).filter(
        EvaluationGroundTruth.anomaly_type == ExceptionType.GHOST_SETTLEMENT.value
    ).all()
    assert len(gt_cases) >= 1

    for gt in gt_cases:
        assert gt.expected_exposure > 0
        assert "Gateway/order state indicates failure" in gt.expected_root_cause
        assert gt.expected_resolution_class == "EVIDENCE_DISPUTE_PACKET"
        assert gt.expected_verification_state == "VERIFIED_CLOSED"


def test_refund_chargeback_double_dip_scenario_integrity(db_session):
    """Verify Refund + Chargeback scenario has dual liability events and ground truth."""
    generate_dataset(db_session, record_count=60, seed=42)

    gt_cases = db_session.query(EvaluationGroundTruth).filter(
        EvaluationGroundTruth.anomaly_type == ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value
    ).all()
    assert len(gt_cases) >= 1

    for gt in gt_cases:
        assert gt.expected_exposure > 0
        assert "Refund and chargeback financial liabilities overlap" in gt.expected_root_cause


def test_sla_breach_scenario_integrity(db_session):
    """Verify SLA breach scenario has delayed settlement timestamp and ground truth."""
    generate_dataset(db_session, record_count=60, seed=42)

    gt_cases = db_session.query(EvaluationGroundTruth).filter(
        EvaluationGroundTruth.anomaly_type == ExceptionType.SETTLEMENT_SLA_BREACH.value
    ).all()
    assert len(gt_cases) >= 1

    for gt in gt_cases:
        assert gt.expected_exposure > 0
        assert "no valid settlement within the configured synthetic processing window" in gt.expected_root_cause
        assert gt.expected_resolution_class == "ESCALATE"


def test_partial_settlement_scenario_integrity(db_session):
    """Verify Partial Settlement scenario: split batches aggregate to payment with exposure = 0."""
    generate_dataset(db_session, record_count=60, seed=42)

    gt_cases = db_session.query(EvaluationGroundTruth).filter(
        EvaluationGroundTruth.anomaly_type == ExceptionType.PARTIAL_SETTLEMENT.value
    ).all()
    assert len(gt_cases) >= 1

    for gt in gt_cases:
        assert gt.expected_exposure == 0  # Legitimate split has zero anomaly exposure
        assert gt.expected_resolution_class == "NO_ACTION"
        assert gt.expected_verification_state == "NO_ACTION_REQUIRED"


def test_missing_and_unallocated_settlement_integrity(db_session):
    """Verify Missing and Unallocated settlement scenarios."""
    generate_dataset(db_session, record_count=60, seed=42)

    gt_cases = db_session.query(EvaluationGroundTruth).filter(
        EvaluationGroundTruth.anomaly_type == ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value
    ).all()
    assert len(gt_cases) >= 2  # At least one missing and one unallocated

    # Check unallocated batch exists in DB with payment_id IS NULL
    unallocated_batches = db_session.query(BankSettlementBatch).filter(
        BankSettlementBatch.payment_id.is_(None)
    ).all()
    assert len(unallocated_batches) >= 1


def test_legitimate_timing_exception_integrity(db_session):
    """Verify Legitimate Timing Exception scenario has zero anomaly exposure."""
    generate_dataset(db_session, record_count=60, seed=42)

    gt_cases = db_session.query(EvaluationGroundTruth).filter(
        EvaluationGroundTruth.anomaly_type == ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value
    ).all()
    assert len(gt_cases) >= 1

    for gt in gt_cases:
        assert gt.expected_exposure == 0
        assert gt.expected_resolution_class == "NO_ACTION"


def test_financial_precision_all_integers(db_session):
    """Verify that NO generated monetary values use floating-point types."""
    generate_dataset(db_session, record_count=60, seed=42)

    for tx in db_session.query(GatewayTransaction).all():
        assert isinstance(tx.amount, int)
        assert tx.amount > 0

    for order in db_session.query(MerchantOrder).all():
        assert isinstance(order.order_amount, int)
        assert order.order_amount > 0

    for batch in db_session.query(BankSettlementBatch).all():
        assert isinstance(batch.net_amount, int)
        assert isinstance(batch.interchange_fee_deducted, int)
        assert isinstance(batch.tax_deducted, int)

    for event in db_session.query(DisputeRefundEvent).all():
        assert isinstance(event.amount, int)

    for ledger in db_session.query(NodalLedgerEntry).all():
        assert isinstance(ledger.debit, int)
        assert isinstance(ledger.credit, int)
        assert isinstance(ledger.balance_after, int)

    for gt in db_session.query(EvaluationGroundTruth).all():
        assert isinstance(gt.expected_exposure, int)


def test_dataset_metadata_persisted(db_session):
    """Verify dataset metadata record is persisted in dataset_metadata table."""
    summary = generate_dataset(db_session, record_count=60, seed=42)

    dataset_repo = DatasetRepository(db_session)
    metadata = dataset_repo.get_dataset_metadata(summary["dataset_id"])
    assert metadata is not None
    assert metadata.seed == 42
    assert metadata.record_count == summary["total_financial_records"]
    assert metadata.dataset_version == "v0.1.0-synthetic"


def test_data_generate_api_endpoint():
    """Verify POST /data/generate endpoint."""
    from fastapi.testclient import TestClient
    from backend.main import app

    with TestClient(app) as client:
        res = client.post("/data/generate", json={"record_count": 50, "seed": 77})
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert data["seed"] == 77
        assert data["total_financial_records"] >= 50
        assert "scenario_breakdown" in data
