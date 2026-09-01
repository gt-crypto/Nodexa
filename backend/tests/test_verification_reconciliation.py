"""Tests for deterministic reconciliation and action-specific verification."""
import json
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from backend.models.financial_sources import GatewayTransaction, BankSettlementBatch, MerchantOrder
from backend.models.exceptions import ExceptionRecord, ExceptionAffectedRecord
from backend.models.remediation import RemediationAction
from backend.models.enums import (
    ExceptionType,
    ExceptionSeverity,
    ExceptionState,
    PolicyActionType,
    PaymentStatus,
    RemediationStatus,
)
from backend.services.repositories import ExceptionRepository, RemediationRepository
from backend.verification.reconciliation import verify_reconciliation_state, verify_action_specific_outcome


def utc_now():
    return datetime.now(timezone.utc)


def test_reconciliation_verification_success(db_session: Session):
    """Verify that a reconciled payment and settlement pass reconciliation checks."""
    exc_repo = ExceptionRepository(db_session)

    pmt = GatewayTransaction(
        payment_id="pay_recon_ok_01",
        merchant_id="mer_01",
        amount=100000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        method="UPI",
    )
    db_session.add(pmt)

    order = MerchantOrder(
        order_id="ord_recon_ok_01",
        order_amount=100000,
        payment_id_reference="pay_recon_ok_01",
        fulfillment_status="FULFILLED",
        created_at=utc_now(),
    )
    db_session.add(order)

    stl = BankSettlementBatch(
        settlement_id="stl_recon_ok_01",
        payment_id="pay_recon_ok_01",
        acquirer_id="ACQ_01",
        net_amount=98000,
        interchange_fee_deducted=2000,
        tax_deducted=0,
        utr_number="UTR_RECON_OK_01",
        clearing_timestamp=utc_now(),
    )
    db_session.add(stl)

    exc = ExceptionRecord(
        exception_id="exc_recon_ok_01",
        exception_type=ExceptionType.SETTLEMENT_SLA_BREACH.value,
        severity=ExceptionSeverity.MEDIUM.value,
        state=ExceptionState.DIAGNOSED.value,
        primary_payment_id="pay_recon_ok_01",
        exposure=100000,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    is_reconciled, evidence = verify_reconciliation_state(db_session, exc)
    assert is_reconciled is True
    assert len(evidence) > 0
    assert all(ev.result == "PASS" for ev in evidence)


def test_action_specific_allocate_settlement(db_session: Session):
    """Verify ALLOCATE_SETTLEMENT action verification verifies settlement linkage."""
    exc_repo = ExceptionRepository(db_session)
    rem_repo = RemediationRepository(db_session)

    pmt = GatewayTransaction(
        payment_id="pay_target_01",
        merchant_id="mer_01",
        amount=500000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        method="CARD",
    )
    db_session.add(pmt)

    stl = BankSettlementBatch(
        settlement_id="stl_alloc_test_01",
        payment_id="pay_target_01",  # Linked
        acquirer_id="ACQ_01",
        net_amount=490000,
        interchange_fee_deducted=10000,
        tax_deducted=0,
        utr_number="UTR_ALLOC_01",
        clearing_timestamp=utc_now(),
    )
    db_session.add(stl)

    exc = ExceptionRecord(
        exception_id="exc_alloc_01",
        exception_type=ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.DIAGNOSED.value,
        primary_payment_id="pay_target_01",
        exposure=500000,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    plan = RemediationAction(
        action_id="act_alloc_01",
        exception_id="exc_alloc_01",
        action_type=PolicyActionType.ALLOCATE_SETTLEMENT.value,
        status=RemediationStatus.AWAITING_VERIFICATION.value,
        action_payload=json.dumps({
            "settlement_id": "stl_alloc_test_01",
            "payment_id": "pay_target_01",
            "amount_minor_units": 500000,
        }),
        created_at=utc_now(),
        requested_at=utc_now(),
    )
    rem_repo.create_action(plan)

    passed, fail_reasons, evidence = verify_action_specific_outcome(db_session, plan, exc)
    assert passed is True
    assert len(fail_reasons) == 0
    assert any(ev.check_id == "CHECK-SETTLE-ALLOC-LINK" and ev.result == "PASS" for ev in evidence)
