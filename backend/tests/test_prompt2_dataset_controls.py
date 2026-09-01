"""Deterministic verification of Prompt 3 control engine against the Prompt 2 seeded synthetic dataset (Seed 42)."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.data.generator.service import generate_dataset
from backend.controls.engine import ControlEngine
from backend.controls.control_result import ControlStatus
from backend.controls.settlement_sla import SLATimingStatus, evaluate_settlement_sla
from backend.reconciliation.service import ReconciliationService
from backend.reconciliation.settlements import SettlementReconciliationStatus, aggregate_settlements_for_payment
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.enums import ExceptionType, PaymentStatus


def test_control_engine_against_seeded_prompt2_dataset(db_session: Session):
    """Executes deterministic controls across the 60-record seed 42 dataset and verifies scenario facts."""
    # 1. Generate standard Seed 42 dataset
    summary = generate_dataset(session=db_session, record_count=60, seed=42)
    db_session.commit()

    assert summary["dataset_id"] is not None
    assert summary["seed"] == 42

    # 2. Run the deterministic ControlEngine
    engine = ControlEngine()
    report = engine.run_all_controls(session=db_session)

    assert report.total_controls > 0
    assert report.passed_count > 0
    assert report.nodal_health is not None

    # Fetch operational records and ground truth
    ground_truth = list(db_session.scalars(select(EvaluationGroundTruth)).all())
    payments = list(db_session.scalars(select(GatewayTransaction)).all())
    settlements = list(db_session.scalars(select(BankSettlementBatch)).all())
    orders = list(db_session.scalars(select(MerchantOrder)).all())
    disputes = list(db_session.scalars(select(DisputeRefundEvent)).all())
    ledger_entries = list(db_session.scalars(select(NodalLedgerEntry)).all())

    # --- Scenario 1: Ghost Settlement ---
    # Payment status FAILED, yet settlement batch and ledger credit exist
    failed_payments = [p for p in payments if p.status == PaymentStatus.FAILED.value]
    ghost_cases = [
        p for p in failed_payments
        if any(s.payment_id == p.payment_id for s in settlements)
    ]
    assert len(ghost_cases) == 2, "Should identify 2 planted ghost settlement payments"
    for ghost_pmt in ghost_cases:
        # Check that bank settlement exists for failed payment
        linked_s = [s for s in settlements if s.payment_id == ghost_pmt.payment_id]
        assert len(linked_s) > 0
        # Ledger has credits for this failed transaction
        linked_led = [l for l in ledger_entries if l.transaction_id == ghost_pmt.payment_id]
        assert any(l.credit > 0 for l in linked_led)

    # --- Scenario 2: Refund + Chargeback Double Dip ---
    # Payment has both REFUND and CHARGEBACK events
    dispute_counts = {}
    for d in disputes:
        dispute_counts.setdefault(d.payment_id, []).append(d.event_type)
    
    double_dip_payments = [
        pid for pid, types in dispute_counts.items()
        if "REFUND" in types and "CHARGEBACK" in types
    ]
    assert len(double_dip_payments) == 2, "Should identify 2 planted double-dip cases"

    # --- Scenario 3: Genuine Settlement SLA Breach ---
    # Cleared after 54 hours
    sla_breaches = []
    for p in payments:
        if p.status == PaymentStatus.CAPTURED.value:
            res = evaluate_settlement_sla(p, settlements, config=engine.sla_config)
            if res.calculated_values.get("timing_status") == SLATimingStatus.SLA_BREACH.value:
                sla_breaches.append(p.payment_id)

    assert len(sla_breaches) >= 2, "Should detect at least 2 genuine SLA breach cases"

    # --- Scenario 4: Legitimate Partial Settlement (Must NOT produce false errors) ---
    partial_payments = []
    for p in payments:
        p_settles = [s for s in settlements if s.payment_id == p.payment_id]
        if len(p_settles) > 1:
            agg = aggregate_settlements_for_payment(p, p_settles)
            if agg.status == SettlementReconciliationStatus.PARTIAL_SETTLEMENT_COMPLETE:
                partial_payments.append(p.payment_id)

    assert len(partial_payments) == 2, "Should identify 2 legitimate partial multi-tranche settlement cases"

    # --- Scenario 5: Missing and Unallocated Settlements ---
    # 5A: Missing settlements (Captured payment, 0 settlement batches)
    missing_settlements = []
    for p in payments:
        if p.status == PaymentStatus.CAPTURED.value:
            p_settles = [s for s in settlements if s.payment_id == p.payment_id]
            if len(p_settles) == 0:
                missing_settlements.append(p.payment_id)
    assert len(missing_settlements) == 2, "Should identify 2 missing settlement cases"

    # 5B: Unallocated settlements (Settlement with payment_id = NULL)
    unallocated_settlements = [s for s in settlements if s.payment_id is None]
    assert len(unallocated_settlements) == 2, "Should identify 2 unallocated settlement batches"

    # --- Scenario 6: Legitimate Timing Exception (Must NOT be flagged as SLA breach) ---
    late_valid_payments = []
    for p in payments:
        if p.status == PaymentStatus.CAPTURED.value:
            res = evaluate_settlement_sla(p, settlements, config=engine.sla_config)
            if res.calculated_values.get("timing_status") == SLATimingStatus.LATE_BUT_VALID.value:
                late_valid_payments.append(p.payment_id)

    assert len(late_valid_payments) == 2, "Should identify 2 legitimate Friday/weekend timing exceptions as LATE_BUT_VALID"
