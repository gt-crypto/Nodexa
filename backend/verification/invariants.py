"""Financial invariant and double-entry balance verification for post-remediation validation."""
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.controls.control_result import ControlResult, ControlStatus
from backend.controls.invariants import (
    validate_ledger_balance_progression,
    validate_debit_credit_sanity,
    validate_non_negative_constraints,
    validate_currency_consistency,
    validate_reference_integrity,
)
from backend.verification.models import VerificationEvidenceItem


def verify_financial_invariants(
    session: Session,
    account_id: str = "nodal_escrow_main",
    expected_currency: str = "INR",
) -> Tuple[bool, List[ControlResult], List[VerificationEvidenceItem]]:
    """Runs all deterministic financial invariants across operational and ledger records.
    
    Returns:
        (all_passed, control_results, evidence_items)
    """
    ledger_entries = list(
        session.scalars(
            select(NodalLedgerEntry)
            .where(NodalLedgerEntry.account_id == account_id)
            .order_by(NodalLedgerEntry.timestamp.asc(), NodalLedgerEntry.id.asc())
        ).all()
    )
    payments = list(session.scalars(select(GatewayTransaction)).all())
    settlements = list(session.scalars(select(BankSettlementBatch)).all())
    orders = list(session.scalars(select(MerchantOrder)).all())
    disputes = list(session.scalars(select(DisputeRefundEvent)).all())

    known_payment_ids: Set[str] = {p.payment_id for p in payments}

    results: List[ControlResult] = []
    evidence: List[VerificationEvidenceItem] = []

    # 1. Balance Progression Invariant
    prog_res = validate_ledger_balance_progression(ledger_entries, account_id=account_id)
    results.extend(prog_res)
    for r in prog_res:
        evidence.append(
            VerificationEvidenceItem(
                check_id="CHECK-INVAR-PROGRESSION",
                check_type="INVARIANT",
                source_table="nodal_ledger",
                expected_value={"progression_errors": 0},
                actual_value=r.actual_values or {"status": r.status.value},
                result="PASS" if r.status == ControlStatus.PASS else "FAIL",
                explanation=r.rule,
            )
        )

    # 2. Debit/Credit Sanity
    sanity_res = validate_debit_credit_sanity(ledger_entries)
    results.extend(sanity_res)
    for r in sanity_res:
        evidence.append(
            VerificationEvidenceItem(
                check_id="CHECK-INVAR-DEBIT-CREDIT",
                check_type="INVARIANT",
                source_table="nodal_ledger",
                expected_value={"sanity_violations": 0},
                actual_value=r.actual_values or {"status": r.status.value},
                result="PASS" if r.status == ControlStatus.PASS else "FAIL",
                explanation=r.rule,
            )
        )

    # 3. Non-negative constraints
    non_neg_res = validate_non_negative_constraints(payments, settlements, orders, disputes, ledger_entries)
    results.extend(non_neg_res)
    for r in non_neg_res:
        evidence.append(
            VerificationEvidenceItem(
                check_id="CHECK-INVAR-NON-NEGATIVE",
                check_type="INVARIANT",
                source_table="financial_sources",
                expected_value={"violations": 0},
                actual_value=r.actual_values or {"status": r.status.value},
                result="PASS" if r.status == ControlStatus.PASS else "FAIL",
                explanation=r.rule,
            )
        )

    # 4. Currency consistency
    curr_res = validate_currency_consistency(payments, expected_currency=expected_currency)
    results.extend(curr_res)
    for r in curr_res:
        evidence.append(
            VerificationEvidenceItem(
                check_id="CHECK-INVAR-CURRENCY",
                check_type="INVARIANT",
                source_table="gateway_transactions",
                expected_value={"expected_currency": expected_currency},
                actual_value=r.actual_values or {"status": r.status.value},
                result="PASS" if r.status == ControlStatus.PASS else "FAIL",
                explanation=r.rule,
            )
        )

    # 5. Reference integrity
    ref_res = validate_reference_integrity(ledger_entries, known_payment_ids)
    results.extend(ref_res)
    for r in ref_res:
        evidence.append(
            VerificationEvidenceItem(
                check_id="CHECK-INVAR-REF-INTEGRITY",
                check_type="INVARIANT",
                source_table="nodal_ledger",
                expected_value={"dangling_references": 0},
                actual_value=r.actual_values or {"status": r.status.value},
                result="PASS" if r.status == ControlStatus.PASS else "FAIL",
                explanation=r.rule,
            )
        )

    all_passed = all(c.status in (ControlStatus.PASS, ControlStatus.NOT_APPLICABLE) for c in results)
    return all_passed, results, evidence


def verify_double_entry_balance_delta(
    before_balance: int,
    after_balance: int,
    credits: int,
    debits: int,
) -> Tuple[bool, VerificationEvidenceItem]:
    """Verifies that actual ledger balance delta exactly matches expected delta.
    
    Formula:
        actual_delta = after_balance - before_balance
        expected_delta = credits - debits
    """
    actual_delta = after_balance - before_balance
    expected_delta = credits - debits
    passed = (actual_delta == expected_delta)

    evidence = VerificationEvidenceItem(
        check_id="CHECK-DOUBLE-ENTRY-DELTA",
        check_type="DOUBLE_ENTRY",
        source_table="nodal_ledger",
        expected_value=f"expected_delta={expected_delta} (credits {credits} - debits {debits})",
        actual_value=f"actual_delta={actual_delta} (after {after_balance} - before {before_balance})",
        result="PASS" if passed else "FAIL",
        explanation="Ledger actual balance delta must mathematically equal credits minus debits.",
    )
    return passed, evidence
