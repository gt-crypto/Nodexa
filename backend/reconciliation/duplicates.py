"""Deterministic duplicate event and duplicate record detection."""
from collections import defaultdict
from datetime import timedelta
from typing import Dict, List, Optional, Tuple

from backend.controls.control_result import ControlResult, ControlStatus, EvidenceItem
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    DisputeRefundEvent,
    NodalLedgerEntry,
)


def detect_duplicate_settlements(
    settlements: List[BankSettlementBatch],
) -> List[ControlResult]:
    """Detects suspicious duplicate bank settlement records or duplicated UTR references."""
    results: List[ControlResult] = []
    
    # 1. Duplicate Settlement IDs
    id_counts = defaultdict(list)
    for s in settlements:
        id_counts[s.settlement_id].append(s)

    dup_id_batches = {k: v for k, v in id_counts.items() if len(v) > 1}

    # 2. Duplicate UTR Numbers (ignoring None / empty)
    utr_counts = defaultdict(list)
    for s in settlements:
        if s.utr_number:
            utr_counts[s.utr_number].append(s)

    dup_utr_batches = {k: v for k, v in utr_counts.items() if len(v) > 1}

    if not dup_id_batches and not dup_utr_batches:
        results.append(
            ControlResult(
                control_id="CTRL-DUP-SETTLEMENTS",
                control_name="Duplicate Settlement Detection",
                status=ControlStatus.PASS,
                rule="Settlement IDs and UTR numbers must be unique across all settlement batches.",
                calculated_values={"duplicate_settlement_ids": 0, "duplicate_utrs": 0},
                expected_values={"duplicates": 0},
                actual_values={"duplicates": 0},
            )
        )
    else:
        affected_ids = []
        evidence = []

        for sid, batches in dup_id_batches.items():
            for b in batches:
                affected_ids.append(b.settlement_id)
                evidence.append(
                    EvidenceItem(
                        source="bank_settlement_batches",
                        record_id=b.settlement_id,
                        field="settlement_id",
                        value=b.settlement_id,
                        comparison=f"Duplicate settlement_id seen {len(batches)} times",
                    )
                )

        for utr, batches in dup_utr_batches.items():
            for b in batches:
                affected_ids.append(b.settlement_id)
                evidence.append(
                    EvidenceItem(
                        source="bank_settlement_batches",
                        record_id=b.settlement_id,
                        field="utr_number",
                        value=utr,
                        comparison=f"Duplicate UTR seen across {len(batches)} settlement records",
                    )
                )

        results.append(
            ControlResult(
                control_id="CTRL-DUP-SETTLEMENTS",
                control_name="Duplicate Settlement Detection",
                status=ControlStatus.FAIL,
                severity="HIGH",
                affected_record_ids=list(set(affected_ids)),
                rule="Settlement IDs and UTR numbers must be unique across all settlement batches.",
                calculated_values={
                    "duplicate_settlement_ids": len(dup_id_batches),
                    "duplicate_utrs": len(dup_utr_batches),
                },
                expected_values={"duplicates": 0},
                actual_values={"duplicates": len(dup_id_batches) + len(dup_utr_batches)},
                evidence=evidence,
            )
        )

    return results


def detect_duplicate_disputes(
    disputes: List[DisputeRefundEvent],
) -> List[ControlResult]:
    """Detects exact duplicate dispute/refund events for the same payment and event type."""
    results: List[ControlResult] = []
    
    # Group by (payment_id, event_type, amount)
    event_groups = defaultdict(list)
    for d in disputes:
        key = (d.payment_id, d.event_type, d.amount)
        event_groups[key].append(d)

    duplicate_groups = []
    for key, group in event_groups.items():
        if len(group) > 1:
            # Check timestamps to confirm if they occurred closely (within 1 hour)
            sorted_group = sorted(group, key=lambda x: x.timestamp)
            for i in range(len(sorted_group) - 1):
                if abs((sorted_group[i+1].timestamp - sorted_group[i].timestamp).total_seconds()) < 3600:
                    duplicate_groups.append((key, sorted_group))
                    break

    if not duplicate_groups:
        results.append(
            ControlResult(
                control_id="CTRL-DUP-DISPUTES",
                control_name="Duplicate Dispute & Refund Event Detection",
                status=ControlStatus.PASS,
                rule="Dispute and refund events for the same payment, type, and amount should not be duplicated in short intervals.",
                calculated_values={"duplicate_dispute_groups": 0},
                expected_values={"duplicate_events": 0},
                actual_values={"duplicate_events": 0},
            )
        )
    else:
        affected_ids = []
        evidence = []
        for (payment_id, event_type, amount), group in duplicate_groups:
            for d in group:
                affected_ids.append(d.event_id)
                evidence.append(
                    EvidenceItem(
                        source="dispute_refund_events",
                        record_id=d.event_id,
                        field="event_id",
                        value={"payment_id": payment_id, "event_type": event_type, "amount": amount},
                        comparison=f"Duplicate {event_type} event detected for payment {payment_id}",
                    )
                )

        results.append(
            ControlResult(
                control_id="CTRL-DUP-DISPUTES",
                control_name="Duplicate Dispute & Refund Event Detection",
                status=ControlStatus.FAIL,
                severity="HIGH",
                affected_record_ids=list(set(affected_ids)),
                rule="Dispute and refund events for the same payment, type, and amount should not be duplicated in short intervals.",
                calculated_values={"duplicate_dispute_groups": len(duplicate_groups)},
                expected_values={"duplicate_events": 0},
                actual_values={"duplicate_events": len(duplicate_groups)},
                evidence=evidence,
            )
        )

    return results


def detect_duplicate_ledger_postings(
    ledger_entries: List[NodalLedgerEntry],
) -> List[ControlResult]:
    """Detects suspicious duplicate ledger entries posted for the same transaction and entry type."""
    results: List[ControlResult] = []
    
    # Filter entries with transaction_id
    tx_entries = [e for e in ledger_entries if e.transaction_id is not None]
    
    groups = defaultdict(list)
    for e in tx_entries:
        key = (e.transaction_id, e.entry_type, e.debit, e.credit)
        groups[key].append(e)

    duplicate_entries = []
    for key, group in groups.items():
        if len(group) > 1:
            sorted_group = sorted(group, key=lambda x: x.timestamp)
            for i in range(len(sorted_group) - 1):
                # Within 2 minutes and same amounts
                if abs((sorted_group[i+1].timestamp - sorted_group[i].timestamp).total_seconds()) < 120:
                    duplicate_entries.append((key, sorted_group))
                    break

    if not duplicate_entries:
        results.append(
            ControlResult(
                control_id="CTRL-DUP-LEDGER-POSTINGS",
                control_name="Duplicate Ledger Posting Detection",
                status=ControlStatus.PASS,
                rule="Ledger entries for the same transaction and entry type should not have identical amounts posted in immediate succession.",
                calculated_values={"duplicate_posting_groups": 0},
                expected_values={"duplicates": 0},
                actual_values={"duplicates": 0},
            )
        )
    else:
        affected_ids = []
        evidence = []
        for (tx_id, entry_type, debit, credit), group in duplicate_entries:
            for e in group:
                affected_ids.append(e.ledger_id)
                evidence.append(
                    EvidenceItem(
                        source="nodal_ledger",
                        record_id=e.ledger_id,
                        field="ledger_id",
                        value={"transaction_id": tx_id, "entry_type": entry_type, "debit": debit, "credit": credit},
                        comparison="Suspicious duplicate posting in short timeframe",
                    )
                )

        results.append(
            ControlResult(
                control_id="CTRL-DUP-LEDGER-POSTINGS",
                control_name="Duplicate Ledger Posting Detection",
                status=ControlStatus.FAIL,
                severity="HIGH",
                affected_record_ids=list(set(affected_ids)),
                rule="Ledger entries for the same transaction and entry type should not have identical amounts posted in immediate succession.",
                calculated_values={"duplicate_posting_groups": len(duplicate_entries)},
                expected_values={"duplicates": 0},
                actual_values={"duplicates": len(duplicate_entries)},
                evidence=evidence,
            )
        )

    return results
