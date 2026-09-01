"""Unit tests for Remediation Execution engine and transactional invariant checks."""
from datetime import datetime, timezone
import json
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import ExceptionState, ExceptionType, PolicyActionType, RemediationStatus, PaymentStatus, DisputeEventType
from backend.models.exceptions import ExceptionRecord
from backend.models.financial_sources import GatewayTransaction, DisputeRefundEvent, NodalLedgerEntry
from backend.models.investigation import InvestigationRun
from backend.remediation.planner import RemediationPlanner
from backend.remediation.approval import ApprovalService
from backend.remediation.executor import RemediationExecutor


def test_remediation_refund_execution(db_session: Session):
    """Verifies that executing an approved REFUND updates gateway status, creates refund event, posts ledger debit, and captures snapshots."""
    now = datetime.now(timezone.utc)
    
    # 1. Setup financial records
    gt = GatewayTransaction(
        payment_id="PAY-EXEC-001",
        merchant_id="MERCH-001",
        amount=5000000,
        currency="INR",
        method="CARD",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
    )
    nle = NodalLedgerEntry(
        ledger_id="NLE-INIT-001",
        account_id="nodal_escrow_main",
        entry_type="OPENING_BALANCE",
        debit=0,
        credit=100000000,
        balance_after=100000000,
        reference="INIT",
        timestamp=now,
    )
    exc = ExceptionRecord(
        exception_id="EXC-EXEC-TEST-PAY-EXEC-001",
        primary_payment_id="PAY-EXEC-001",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity="CRITICAL",
        state=ExceptionState.DIAGNOSED.value,
        exposure=5000000,
        detected_at=now,
        created_at=now,
    )
    inv = InvestigationRun(
        investigation_id="INV-EXEC-001",
        exception_id="EXC-EXEC-TEST-PAY-EXEC-001",
        status="COMPLETED",
        final_classification="PAYMENT_STATE_CONTRADICTION",
        confidence="0.95",
        root_cause="Diagnosed ghost settlement",
        created_at=now,
    )
    db_session.add_all([gt, nle, exc, inv])
    db_session.commit()

    # 2. Plan
    plan = RemediationPlanner.create_plan(
        session=db_session,
        exception_id="EXC-EXEC-TEST-PAY-EXEC-001",
        action=PolicyActionType.REFUND.value,
        parameters={"payment_id": "PAY-EXEC-001", "amount_minor_units": 5000000, "reason": "Refund ghost settlement"},
        requested_by="operator-01",
    )
    db_session.commit()

    # 3. Approve
    ApprovalService.record_approval(
        session=db_session,
        action_id=plan.action_id,
        approved_by="finance-approver-01",
        decision="APPROVED",
        reason="Approved for execution",
    )
    db_session.commit()

    # 4. Execute
    executed_plan = RemediationExecutor.execute(
        session=db_session,
        action_id=plan.action_id,
        executed_by="service-executor",
    )
    db_session.commit()

    assert executed_plan.status == RemediationStatus.AWAITING_VERIFICATION.value
    assert executed_plan.before_snapshot is not None
    assert executed_plan.after_snapshot is not None

    after_data = json.loads(executed_plan.after_snapshot)
    assert after_data["payment_status"] == PaymentStatus.REFUNDED.value
    assert after_data["ledger_balance_after"] == 95000000  # 100M - 5M

    # Verify GatewayTransaction status updated
    gt_updated = db_session.scalars(select(GatewayTransaction).where(GatewayTransaction.payment_id == "PAY-EXEC-001")).first()
    assert gt_updated.status == PaymentStatus.REFUNDED.value

    # Verify DisputeRefundEvent created
    refund_evts = list(db_session.scalars(select(DisputeRefundEvent).where(DisputeRefundEvent.payment_id == "PAY-EXEC-001")).all())
    assert len(refund_evts) == 1
    assert refund_evts[0].amount == 5000000
    assert refund_evts[0].event_type == DisputeEventType.REFUND.value
