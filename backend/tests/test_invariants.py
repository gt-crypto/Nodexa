"""Unit tests for deterministic financial and ledger invariants."""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session

from backend.controls.invariants import (
    validate_ledger_balance_progression,
    validate_debit_credit_sanity,
    validate_non_negative_constraints,
    validate_currency_consistency,
    validate_reference_integrity,
)
from backend.controls.control_result import ControlStatus
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.enums import PaymentStatus, LedgerEntryType, OrderFulfillmentStatus


def test_ledger_balance_progression_valid():
    """Verifies that sequentially correct ledger entries pass the balance progression invariant."""
    now = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
    entries = [
        NodalLedgerEntry(
            ledger_id="LED-1",
            account_id="nodal_escrow_main",
            debit=0,
            credit=100000,
            balance_after=100000,
            timestamp=now,
            entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        ),
        NodalLedgerEntry(
            ledger_id="LED-2",
            account_id="nodal_escrow_main",
            debit=0,
            credit=50000,
            balance_after=150000,
            timestamp=now + timedelta(minutes=10),
            entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        ),
        NodalLedgerEntry(
            ledger_id="LED-3",
            account_id="nodal_escrow_main",
            debit=30000,
            credit=0,
            balance_after=120000,
            timestamp=now + timedelta(minutes=20),
            entry_type=LedgerEntryType.REFUND_DEBIT.value,
        ),
    ]

    results = validate_ledger_balance_progression(entries, account_id="nodal_escrow_main")
    assert len(results) == 1
    assert results[0].status == ControlStatus.PASS
    assert results[0].calculated_values["entry_count"] == 3
    assert results[0].calculated_values["final_balance"] == 120000


def test_ledger_balance_progression_corrupted():
    """Verifies that an altered balance_after triggers a CRITICAL failure."""
    now = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)
    entries = [
        NodalLedgerEntry(
            ledger_id="LED-1",
            account_id="nodal_escrow_main",
            debit=0,
            credit=100000,
            balance_after=100000,
            timestamp=now,
            entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        ),
        # Corrupted balance_after: should be 150000, but is 199999
        NodalLedgerEntry(
            ledger_id="LED-2",
            account_id="nodal_escrow_main",
            debit=0,
            credit=50000,
            balance_after=199999,
            timestamp=now + timedelta(minutes=10),
            entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        ),
    ]

    results = validate_ledger_balance_progression(entries, account_id="nodal_escrow_main")
    assert len(results) == 1
    assert results[0].status == ControlStatus.FAIL
    assert results[0].severity == "CRITICAL"
    assert "LED-2" in results[0].affected_record_ids


def test_debit_credit_sanity_rejections():
    """Verifies that simultaneous debit and credit or negative entries are rejected."""
    now = datetime.now(timezone.utc)
    bad_entries = [
        NodalLedgerEntry(
            ledger_id="LED-BAD-1",
            account_id="nodal_escrow_main",
            debit=5000,
            credit=5000,  # Illegal simultaneous debit and credit
            balance_after=5000,
            timestamp=now,
            entry_type=LedgerEntryType.ADJUSTMENT.value,
        ),
        NodalLedgerEntry(
            ledger_id="LED-BAD-2",
            account_id="nodal_escrow_main",
            debit=-1000,  # Illegal negative debit
            credit=0,
            balance_after=6000,
            timestamp=now,
            entry_type=LedgerEntryType.ADJUSTMENT.value,
        ),
    ]

    results = validate_debit_credit_sanity(bad_entries)
    assert len(results) == 1
    assert results[0].status == ControlStatus.FAIL
    assert len(results[0].affected_record_ids) == 2


def test_non_negative_constraints():
    """Verifies non-negative monetary constraints across tables."""
    now = datetime.now(timezone.utc)
    bad_payment = GatewayTransaction(
        payment_id="PAY-NEG",
        merchant_id="MERCH-1",
        amount=-5000,  # Negative amount
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
        method="CARD",
    )

    results = validate_non_negative_constraints(payments=[bad_payment])
    assert len(results) == 1
    assert results[0].status == ControlStatus.FAIL
    assert "PAY-NEG" in results[0].affected_record_ids


def test_currency_consistency():
    """Verifies that currency mismatches are flagged."""
    now = datetime.now(timezone.utc)
    payments = [
        GatewayTransaction(payment_id="PAY-1", merchant_id="M1", amount=1000, currency="INR", status="CAPTURED", created_at=now, method="UPI"),
        GatewayTransaction(payment_id="PAY-2", merchant_id="M1", amount=1000, currency="USD", status="CAPTURED", created_at=now, method="UPI"),
    ]

    results = validate_currency_consistency(payments, expected_currency="INR")
    assert len(results) == 1
    assert results[0].status == ControlStatus.FAIL
    assert "PAY-2" in results[0].affected_record_ids


def test_reference_integrity():
    """Verifies that dangling transaction_id references are identified."""
    now = datetime.now(timezone.utc)
    entries = [
        NodalLedgerEntry(
            ledger_id="LED-1",
            account_id="nodal_escrow_main",
            transaction_id="PAY-UNKNOWN",  # Does not exist in known_payment_ids
            debit=0,
            credit=10000,
            balance_after=10000,
            timestamp=now,
            entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        ),
    ]

    results = validate_reference_integrity(entries, known_payment_ids={"PAY-KNOWN-1", "PAY-KNOWN-2"})
    assert len(results) == 1
    assert results[0].status == ControlStatus.FAIL
    assert "LED-1" in results[0].affected_record_ids
