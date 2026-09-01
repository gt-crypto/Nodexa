"""Unit tests for Remediation Execution idempotency."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import ExceptionState, ExceptionType, PolicyActionType, RemediationStatus, PaymentStatus
from backend.models.exceptions import ExceptionRecord
from backend.models.financial_sources import GatewayTransaction, DisputeRefundEvent, NodalLedgerEntry
from backend.models.investigation import InvestigationRun
from backend.remediation.planner import RemediationPlanner
from backend.remediation.approval import ApprovalService
from backend.remediation.executor import RemediationExecutor


def test_remediation_execution_idempotency(db_session: Session):
    """Verifies that executing a remediation multiple times is strictly idempotent and does not create duplicate entries."""
    now = datetime.now(timezone.utc)
    
    gt = GatewayTransaction(
        payment_id="PAY-IDEMP-001",
        merchant_id="MERCH-001",
        amount=2500000,
        currency="INR",
        method="CARD",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
    )
    nle = NodalLedgerEntry(
        ledger_id="NLE-IDEMP-INIT",
        account_id="nodal_escrow_main",
        entry_type="OPENING_BALANCE",
        debit=0,
        credit=50000000,
        balance_after=50000000,
        reference="INIT",
        timestamp=now,
    )
    exc = ExceptionRecord(
        exception_id="EXC-IDEMP-PAY-IDEMP-001",
        primary_payment_id="PAY-IDEMP-001",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="CRITICAL",
        state=ExceptionState.DIAGNOSED.value,
        exposure=2500000,
        detected_at=now,
        created_at=now,
    )
    inv = InvestigationRun(
        investigation_id="INV-IDEMP-001",
        exception_id="EXC-IDEMP-PAY-IDEMP-001",
        status="COMPLETED",
        final_classification="PAYMENT_STATE_CONTRADICTION",
        confidence="0.95",
        root_cause="Diagnosed ghost settlement",
        created_at=now,
    )
    db_session.add_all([gt, nle, exc, inv])
    db_session.commit()

    plan = RemediationPlanner.create_plan(
        session=db_session,
        exception_id="EXC-IDEMP-PAY-IDEMP-001",
        action=PolicyActionType.REFUND.value,
        parameters={"payment_id": "PAY-IDEMP-001", "amount_minor_units": 2500000, "reason": "Idempotency test"},
        requested_by="operator-01",
    )
    db_session.commit()

    ApprovalService.record_approval(
        session=db_session,
        action_id=plan.action_id,
        approved_by="finance-approver-01",
        decision="APPROVED",
        reason="Approved for execution",
    )
    db_session.commit()

    # 1. First execution
    exec1 = RemediationExecutor.execute(session=db_session, action_id=plan.action_id)
    db_session.commit()
    assert exec1.status == RemediationStatus.AWAITING_VERIFICATION.value

    ledger_count_1 = len(list(db_session.scalars(select(NodalLedgerEntry)).all()))
    refund_count_1 = len(list(db_session.scalars(select(DisputeRefundEvent).where(DisputeRefundEvent.payment_id == "PAY-IDEMP-001")).all()))

    # 2. Second execution with same action_id
    exec2 = RemediationExecutor.execute(session=db_session, action_id=plan.action_id)
    db_session.commit()
    assert exec2.status == RemediationStatus.AWAITING_VERIFICATION.value

    ledger_count_2 = len(list(db_session.scalars(select(NodalLedgerEntry)).all()))
    refund_count_2 = len(list(db_session.scalars(select(DisputeRefundEvent).where(DisputeRefundEvent.payment_id == "PAY-IDEMP-001")).all()))

    # Invariant: No duplicate postings
    assert ledger_count_1 == ledger_count_2
    assert refund_count_1 == refund_count_2
