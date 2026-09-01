"""Tests for financial invariants and double-entry balance verification."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from backend.models.financial_sources import GatewayTransaction, NodalLedgerEntry
from backend.models.enums import LedgerEntryType, PaymentStatus
from backend.verification.invariants import (
    verify_financial_invariants,
    verify_double_entry_balance_delta,
)


def utc_now():
    return datetime.now(timezone.utc)


def test_valid_ledger_invariants_pass(db_session: Session):
    """Verify that a valid sequential ledger satisfies all invariants."""
    e1 = NodalLedgerEntry(
        ledger_id="led_inv_01",
        account_id="nodal_escrow_main",
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        debit=0,
        credit=100000,
        balance_after=100000,
        timestamp=utc_now(),
    )
    e2 = NodalLedgerEntry(
        ledger_id="led_inv_02",
        account_id="nodal_escrow_main",
        entry_type=LedgerEntryType.REFUND_DEBIT.value,
        debit=40000,
        credit=0,
        balance_after=60000,
        timestamp=utc_now(),
    )
    db_session.add(e1)
    db_session.add(e2)

    passed, results, evidence = verify_financial_invariants(db_session, account_id="nodal_escrow_main")
    assert passed is True
    assert all(ev.result == "PASS" for ev in evidence)


def test_invalid_balance_progression_detected(db_session: Session):
    """Verify that an arithmetic leap in running balance triggers invariant failure."""
    e1 = NodalLedgerEntry(
        ledger_id="led_corrupt_01",
        account_id="nodal_escrow_main",
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        debit=0,
        credit=100000,
        balance_after=100000,
        timestamp=utc_now(),
    )
    # Corrupt entry: credit=20000 but balance_after jumped to 500000 (instead of 120000)
    e2 = NodalLedgerEntry(
        ledger_id="led_corrupt_02",
        account_id="nodal_escrow_main",
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        debit=0,
        credit=20000,
        balance_after=500000,
        timestamp=utc_now(),
    )
    db_session.add(e1)
    db_session.add(e2)

    passed, results, evidence = verify_financial_invariants(db_session, account_id="nodal_escrow_main")
    assert passed is False
    assert any(ev.check_id == "CHECK-INVAR-PROGRESSION" and ev.result == "FAIL" for ev in evidence)


def test_debit_credit_sanity_simultaneous_non_zero_fails(db_session: Session):
    """Verify that an entry with simultaneous non-zero debit and credit is rejected."""
    e = NodalLedgerEntry(
        ledger_id="led_simult_01",
        account_id="nodal_escrow_main",
        entry_type=LedgerEntryType.ADJUSTMENT.value,
        debit=50000,
        credit=50000,  # Illegal: simultaneous debit and credit
        balance_after=100000,
        timestamp=utc_now(),
    )
    db_session.add(e)

    passed, results, evidence = verify_financial_invariants(db_session, account_id="nodal_escrow_main")
    assert passed is False
    assert any(ev.check_id == "CHECK-INVAR-DEBIT-CREDIT" and ev.result == "FAIL" for ev in evidence)


def test_currency_consistency_mismatch_fails(db_session: Session):
    """Verify that non-standard currency entries trigger invariant failure."""
    tx = GatewayTransaction(
        payment_id="pay_curr_mismatch_01",
        merchant_id="mer_01",
        amount=100000,
        currency="USD",  # Mismatch: expected INR
        status=PaymentStatus.CAPTURED.value,
        method="CARD",
    )
    db_session.add(tx)

    passed, results, evidence = verify_financial_invariants(db_session, expected_currency="INR")
    assert passed is False
    assert any(ev.check_id == "CHECK-INVAR-CURRENCY" and ev.result == "FAIL" for ev in evidence)


def test_double_entry_balance_delta_verification():
    """Verify double-entry actual vs expected delta arithmetic."""
    # Valid credit: before 1000, after 1500, credit 500, debit 0 -> passed
    p1, ev1 = verify_double_entry_balance_delta(before_balance=1000, after_balance=1500, credits=500, debits=0)
    assert p1 is True
    assert ev1.result == "PASS"

    # Valid debit: before 1500, after 1200, credit 0, debit 300 -> passed
    p2, ev2 = verify_double_entry_balance_delta(before_balance=1500, after_balance=1200, credits=0, debits=300)
    assert p2 is True
    assert ev2.result == "PASS"

    # Invalid delta: before 1000, after 2000, credit 500, debit 0 -> failed
    p3, ev3 = verify_double_entry_balance_delta(before_balance=1000, after_balance=2000, credits=500, debits=0)
    assert p3 is False
    assert ev3.result == "FAIL"
