"""Unit tests for Evaluation security guarantees and zero operational mutation."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.data.generator.service import generate_dataset
from backend.exceptions.service import ExceptionDetectionService
from backend.models.financial_sources import GatewayTransaction, NodalLedgerEntry
from backend.models.exceptions import ExceptionRecord
from backend.evaluation.service import BenchmarkEvaluationService
from backend.evaluation.models import EvaluationRunRequest


def test_evaluation_guarantees_zero_operational_mutation(db_session: Session):
    """Ensures that executing evaluation runs causes zero changes to operational financial and exception records."""
    # 1. Setup initial state
    summary = generate_dataset(session=db_session, record_count=30, seed=42)
    db_session.commit()
    dataset_id = summary["dataset_id"]

    det_service = ExceptionDetectionService()
    det_service.detect_exceptions(session=db_session)
    db_session.commit()

    # Capture operational snapshots
    tx_before = [(t.payment_id, t.status, t.amount) for t in db_session.scalars(select(GatewayTransaction)).all()]
    led_before = [(l.ledger_id, l.debit, l.credit) for l in db_session.scalars(select(NodalLedgerEntry)).all()]
    exc_before = [(e.exception_id, e.state, e.exposure) for e in db_session.scalars(select(ExceptionRecord)).all()]

    # 2. Run benchmark evaluation
    eval_service = BenchmarkEvaluationService()
    req = EvaluationRunRequest(dataset_id=dataset_id, force_rerun=True)
    report = eval_service.run_benchmark(session=db_session, request=req)

    # 3. Capture operational state after evaluation
    tx_after = [(t.payment_id, t.status, t.amount) for t in db_session.scalars(select(GatewayTransaction)).all()]
    led_after = [(l.ledger_id, l.debit, l.credit) for l in db_session.scalars(select(NodalLedgerEntry)).all()]
    exc_after = [(e.exception_id, e.state, e.exposure) for e in db_session.scalars(select(ExceptionRecord)).all()]

    # 4. Strict assertions of absolute equality (0 mutations)
    assert tx_before == tx_after
    assert led_before == led_after
    assert exc_before == exc_after
