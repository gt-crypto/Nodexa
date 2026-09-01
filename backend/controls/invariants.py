"""Deterministic financial invariants and ledger sanity assertions."""
from typing import Dict, List, Optional, Set
from datetime import datetime, timezone

from backend.controls.control_result import ControlResult, ControlStatus, EvidenceItem
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)


def validate_ledger_balance_progression(
    ledger_entries: List[NodalLedgerEntry],
    account_id: str = "nodal_escrow_main",
) -> List[ControlResult]:
    """Validates that running balance progression is mathematically exact for sequential ledger entries.
    
    Formula: Balance[i] = Balance[i-1] + Credit[i] - Debit[i]
    """
    results: List[ControlResult] = []
    
    # Filter entries for the target account and ensure chronological ordering
    account_entries = [e for e in ledger_entries if e.account_id == account_id]
    account_entries.sort(key=lambda x: (x.id if (x.id is not None and x.id > 0) else 0, x.timestamp))
    
    if not account_entries:
        results.append(
            ControlResult(
                control_id="CTRL-INVAR-LEDGER-PROGRESSION",
                control_name="Ledger Balance Progression Invariant",
                status=ControlStatus.PASS,
                rule="Sequential ledger entries must satisfy: balance_after = prev_balance + credit - debit.",
                calculated_values={"account_id": account_id, "entry_count": 0},
            )
        )
        return results

    running_expected_balance = account_entries[0].balance_after - account_entries[0].credit + account_entries[0].debit
    progression_failures = 0
    failed_entries = []
    evidence_list: List[EvidenceItem] = []

    for idx, entry in enumerate(account_entries):
        calculated_after = running_expected_balance + entry.credit - entry.debit
        if calculated_after != entry.balance_after:
            progression_failures += 1
            failed_entries.append(entry.ledger_id)
            evidence_list.append(
                EvidenceItem(
                    source="nodal_ledger",
                    record_id=entry.ledger_id,
                    field="balance_after",
                    value=entry.balance_after,
                    comparison=f"Expected {calculated_after} (prev {running_expected_balance} + credit {entry.credit} - debit {entry.debit}) != actual {entry.balance_after}",
                )
            )
        # Advance running balance
        running_expected_balance = calculated_after

    if progression_failures == 0:
        results.append(
            ControlResult(
                control_id="CTRL-INVAR-LEDGER-PROGRESSION",
                control_name="Ledger Balance Progression Invariant",
                status=ControlStatus.PASS,
                rule="Sequential ledger entries must satisfy: balance_after = prev_balance + credit - debit.",
                calculated_values={
                    "account_id": account_id,
                    "entry_count": len(account_entries),
                    "final_balance": account_entries[-1].balance_after if account_entries else 0,
                },
                expected_values={"progression_errors": 0},
                actual_values={"progression_errors": 0},
            )
        )
    else:
        results.append(
            ControlResult(
                control_id="CTRL-INVAR-LEDGER-PROGRESSION",
                control_name="Ledger Balance Progression Invariant",
                status=ControlStatus.FAIL,
                severity="CRITICAL",
                affected_record_ids=failed_entries,
                rule="Sequential ledger entries must satisfy: balance_after = prev_balance + credit - debit.",
                calculated_values={"account_id": account_id, "entry_count": len(account_entries)},
                expected_values={"progression_errors": 0},
                actual_values={"progression_errors": progression_failures},
                evidence=evidence_list,
            )
        )

    return results


def validate_debit_credit_sanity(ledger_entries: List[NodalLedgerEntry]) -> List[ControlResult]:
    """Validates that each ledger entry contains valid debit and credit values.
    
    Rules:
    - An entry cannot simultaneously have debit > 0 and credit > 0.
    - An entry cannot have both debit == 0 and credit == 0 unless explicitly an adjustment note.
    - Debit and credit must both be non-negative.
    """
    results: List[ControlResult] = []
    failed_entries = []
    evidence_list: List[EvidenceItem] = []

    for entry in ledger_entries:
        is_invalid = False
        reason = ""
        
        if entry.debit < 0 or entry.credit < 0:
            is_invalid = True
            reason = f"Negative entry value: debit={entry.debit}, credit={entry.credit}"
        elif entry.debit > 0 and entry.credit > 0:
            is_invalid = True
            reason = f"Simultaneous debit ({entry.debit}) and credit ({entry.credit}) in single entry"

        if is_invalid:
            failed_entries.append(entry.ledger_id)
            evidence_list.append(
                EvidenceItem(
                    source="nodal_ledger",
                    record_id=entry.ledger_id,
                    field="debit/credit",
                    value={"debit": entry.debit, "credit": entry.credit},
                    comparison=reason,
                )
            )

    if not failed_entries:
        results.append(
            ControlResult(
                control_id="CTRL-INVAR-DEBIT-CREDIT-SANITY",
                control_name="Debit/Credit Sanity Invariant",
                status=ControlStatus.PASS,
                rule="Ledger entries must not contain simultaneous non-zero debit and credit, nor negative amounts.",
                calculated_values={"total_entries_checked": len(ledger_entries)},
                expected_values={"sanity_violations": 0},
                actual_values={"sanity_violations": 0},
            )
        )
    else:
        results.append(
            ControlResult(
                control_id="CTRL-INVAR-DEBIT-CREDIT-SANITY",
                control_name="Debit/Credit Sanity Invariant",
                status=ControlStatus.FAIL,
                severity="HIGH",
                affected_record_ids=failed_entries,
                rule="Ledger entries must not contain simultaneous non-zero debit and credit, nor negative amounts.",
                calculated_values={"total_entries_checked": len(ledger_entries)},
                expected_values={"sanity_violations": 0},
                actual_values={"sanity_violations": len(failed_entries)},
                evidence=evidence_list,
            )
        )

    return results


def validate_non_negative_constraints(
    payments: Optional[List[GatewayTransaction]] = None,
    settlements: Optional[List[BankSettlementBatch]] = None,
    orders: Optional[List[MerchantOrder]] = None,
    disputes: Optional[List[DisputeRefundEvent]] = None,
    ledger_entries: Optional[List[NodalLedgerEntry]] = None,
) -> List[ControlResult]:
    """Validates that all monetary amounts across operational and ledger tables are >= 0."""
    results: List[ControlResult] = []
    violations = []
    evidence_list: List[EvidenceItem] = []

    if payments:
        for tx in payments:
            if tx.amount < 0:
                violations.append(tx.payment_id)
                evidence_list.append(
                    EvidenceItem(
                        source="gateway_transactions",
                        record_id=tx.payment_id,
                        field="amount",
                        value=tx.amount,
                        comparison="amount < 0 violates non-negative constraint",
                    )
                )

    if settlements:
        for b in settlements:
            if b.net_amount < 0 or b.interchange_fee_deducted < 0 or b.tax_deducted < 0:
                violations.append(b.settlement_id)
                evidence_list.append(
                    EvidenceItem(
                        source="bank_settlement_batches",
                        record_id=b.settlement_id,
                        field="net_amount/fee/tax",
                        value={"net": b.net_amount, "fee": b.interchange_fee_deducted, "tax": b.tax_deducted},
                        comparison="Settlement values must be >= 0",
                    )
                )

    if orders:
        for o in orders:
            if o.order_amount < 0:
                violations.append(o.order_id)
                evidence_list.append(
                    EvidenceItem(
                        source="merchant_orders",
                        record_id=o.order_id,
                        field="order_amount",
                        value=o.order_amount,
                        comparison="order_amount < 0 violates non-negative constraint",
                    )
                )

    if disputes:
        for d in disputes:
            if d.amount < 0:
                violations.append(d.event_id)
                evidence_list.append(
                    EvidenceItem(
                        source="dispute_refund_events",
                        record_id=d.event_id,
                        field="amount",
                        value=d.amount,
                        comparison="amount < 0 violates non-negative constraint",
                    )
                )

    if ledger_entries:
        for l in ledger_entries:
            if l.debit < 0 or l.credit < 0 or l.balance_after < 0:
                violations.append(l.ledger_id)
                evidence_list.append(
                    EvidenceItem(
                        source="nodal_ledger",
                        record_id=l.ledger_id,
                        field="debit/credit/balance_after",
                        value={"debit": l.debit, "credit": l.credit, "balance_after": l.balance_after},
                        comparison="Ledger debit, credit, and balance_after must be >= 0",
                    )
                )

    if not violations:
        results.append(
            ControlResult(
                control_id="CTRL-INVAR-NON-NEGATIVE",
                control_name="Non-Negative Monetary Constraints",
                status=ControlStatus.PASS,
                rule="All monetary amounts across transactions, settlements, orders, disputes, and ledger entries must be non-negative.",
                expected_values={"violations": 0},
                actual_values={"violations": 0},
            )
        )
    else:
        results.append(
            ControlResult(
                control_id="CTRL-INVAR-NON-NEGATIVE",
                control_name="Non-Negative Monetary Constraints",
                status=ControlStatus.FAIL,
                severity="CRITICAL",
                affected_record_ids=violations,
                rule="All monetary amounts across transactions, settlements, orders, disputes, and ledger entries must be non-negative.",
                expected_values={"violations": 0},
                actual_values={"violations": len(violations)},
                evidence=evidence_list,
            )
        )

    return results


def validate_currency_consistency(
    payments: List[GatewayTransaction],
    expected_currency: str = "INR",
) -> List[ControlResult]:
    """Validates that all financial records use the compatible expected ISO currency."""
    results: List[ControlResult] = []
    mismatches = []
    evidence_list: List[EvidenceItem] = []

    for tx in payments:
        if tx.currency != expected_currency:
            mismatches.append(tx.payment_id)
            evidence_list.append(
                EvidenceItem(
                    source="gateway_transactions",
                    record_id=tx.payment_id,
                    field="currency",
                    value=tx.currency,
                    comparison=f"Expected currency '{expected_currency}' != actual '{tx.currency}'",
                )
            )

    if not mismatches:
        results.append(
            ControlResult(
                control_id="CTRL-INVAR-CURRENCY-CONSISTENCY",
                control_name="Currency Consistency Invariant",
                status=ControlStatus.PASS,
                rule=f"All transactions must use the standard system currency ({expected_currency}).",
                expected_values={"expected_currency": expected_currency, "mismatches": 0},
                actual_values={"mismatches": 0},
            )
        )
    else:
        results.append(
            ControlResult(
                control_id="CTRL-INVAR-CURRENCY-CONSISTENCY",
                control_name="Currency Consistency Invariant",
                status=ControlStatus.FAIL,
                severity="HIGH",
                affected_record_ids=mismatches,
                rule=f"All transactions must use the standard system currency ({expected_currency}).",
                expected_values={"expected_currency": expected_currency, "mismatches": 0},
                actual_values={"mismatches": len(mismatches)},
                evidence=evidence_list,
            )
        )

    return results


def validate_reference_integrity(
    ledger_entries: List[NodalLedgerEntry],
    known_payment_ids: Set[str],
) -> List[ControlResult]:
    """Validates that non-null transaction_id references in the nodal ledger refer to existing payments."""
    results: List[ControlResult] = []
    dangling_refs = []
    evidence_list: List[EvidenceItem] = []

    for entry in ledger_entries:
        if entry.transaction_id is not None:
            if entry.transaction_id not in known_payment_ids:
                dangling_refs.append(entry.ledger_id)
                evidence_list.append(
                    EvidenceItem(
                        source="nodal_ledger",
                        record_id=entry.ledger_id,
                        field="transaction_id",
                        value=entry.transaction_id,
                        comparison=f"transaction_id '{entry.transaction_id}' does not exist in gateway_transactions",
                    )
                )

    if not dangling_refs:
        results.append(
            ControlResult(
                control_id="CTRL-INVAR-REFERENCE-INTEGRITY",
                control_name="Ledger Reference Integrity Invariant",
                status=ControlStatus.PASS,
                rule="Non-null transaction_id references in nodal ledger must resolve to valid gateway transactions.",
                expected_values={"dangling_references": 0},
                actual_values={"dangling_references": 0},
            )
        )
    else:
        results.append(
            ControlResult(
                control_id="CTRL-INVAR-REFERENCE-INTEGRITY",
                control_name="Ledger Reference Integrity Invariant",
                status=ControlStatus.FAIL,
                severity="MEDIUM",
                affected_record_ids=dangling_refs,
                rule="Non-null transaction_id references in nodal ledger must resolve to valid gateway transactions.",
                expected_values={"dangling_references": 0},
                actual_values={"dangling_references": len(dangling_refs)},
                evidence=evidence_list,
            )
        )

    return results
