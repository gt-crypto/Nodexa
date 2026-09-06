"""Semantic profiler and schema mapper for arbitrary financial datasets.

Discovers semantic mappings from raw column names to canonical financial concepts,
evaluates data types across sample values, assigns confidence scores,
and computes the capability matrix.
"""
import re
from typing import Any, Dict, List, Optional, Set, Tuple
from backend.sandbox.models import (
    CapabilityItem,
    DatasetProfile,
    FieldMappingItem,
)
from backend.sandbox.file_parser import ParsedDataset

# Canonical concept definitions with synonym dictionaries
# Order matters: more specific synonyms are checked first
CANONICAL_SYNONYMS: Dict[str, Dict[str, Any]] = {
    "transaction_id": {
        "primary": ["transaction_id", "txn_id", "tx_id", "payment_id", "payment_ref", "trans_id", "trx_id"],
        "secondary": ["invoice_number", "order_ref", "reference", "id", "ref_id", "reference_id", "trans_ref"],
        "type": "string",
    },
    "merchant_id": {
        "primary": ["merchant_id", "merchant", "merch_id", "merchant_name", "vendor_id", "seller_id", "store_id"],
        "secondary": ["vendor", "seller", "store", "client", "customer", "counterparty", "party_id", "partner", "account_id"],
        "type": "string",
    },
    "amount": {
        "primary": ["amount", "payment_value", "gross_amount", "gross_amt", "transaction_amount", "txn_amount", "txn_amt", "trans_amount", "trans_amt", "amt", "net_amount", "net_amt", "total_amt", "order_amt", "amount_paise", "amt_paise"],
        "secondary": ["total", "price", "sum", "net_value", "charge_amount", "debit_amount", "cost", "value"],
        "type": "amount",
    },
    "status": {
        "primary": ["status", "payment_status", "payment_state", "txn_status", "tx_status"],
        "secondary": ["state", "status_code", "result", "outcome", "flag"],
        "type": "status",
    },
    "transaction_date": {
        "primary": ["transaction_date", "txn_date", "trans_date", "payment_date", "created_at", "created_date"],
        "secondary": ["timestamp", "date", "time", "datetime", "logged_at"],
        "type": "date",
    },
    "settlement_id": {
        "primary": ["settlement_id", "settle_id", "clearing_id", "settlement_ref", "payout_id"],
        "secondary": ["batch_id", "batch_ref", "clearing_ref"],
        "type": "string",
    },
    "settlement_amount": {
        "primary": ["settlement_amount", "settled_value", "settled_amount", "clearing_amount", "settled_amt", "payout_amount", "cleared_amt", "cleared_amount", "settlement_amount_paise"],
        "secondary": ["net_settled", "bank_amount"],
        "type": "amount",
    },
    "settlement_date": {
        "primary": ["settlement_date", "settled_at", "clearing_date", "payout_date", "clearing_timestamp"],
        "secondary": ["settle_date", "cleared_at", "disbursed_at"],
        "type": "date",
    },
    "refund_amount": {
        "primary": ["refund_amount", "refund_value", "chargeback_amount", "dispute_amount", "reversal_amount", "refund_amount_paise"],
        "secondary": ["refunded", "refund_paise", "cb_amount", "dispute_value"],
        "type": "amount",
    },
    "order_id": {
        "primary": ["order_id", "order_ref", "purchase_id", "invoice_id"],
        "secondary": ["checkout_id", "basket_id", "cart_id"],
        "type": "string",
    },
    "order_amount": {
        "primary": ["order_amount", "order_value", "gross_order_amount", "order_amount_paise"],
        "secondary": ["order_total", "cart_total"],
        "type": "amount",
    },
    "debit": {
        "primary": ["debit", "dr", "debit_amount"],
        "secondary": ["withdrawal", "dr_amount"],
        "type": "amount",
    },
    "credit": {
        "primary": ["credit", "cr", "credit_amount"],
        "secondary": ["deposit", "cr_amount"],
        "type": "amount",
    },
    "balance": {
        "primary": ["balance", "ledger_balance", "running_balance"],
        "secondary": ["current_balance", "account_balance", "closing_balance"],
        "type": "amount",
    },
}


def normalize_col_name(col: str) -> str:
    """Normalizes column name for fuzzy matching (strips punctuation, lowers)."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", col.strip().lower())
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    return cleaned


def test_amount_heuristic(samples: List[Any]) -> bool:
    """Checks if sample values look like numeric currency."""
    valid_count = 0
    tested_count = 0
    for s in samples:
        if s is None:
            continue
        val_str = str(s).strip().replace(",", "").replace("₹", "").replace("$", "").replace("€", "")
        if not val_str or val_str.lower() in ("nan", "null", "none", ""):
            continue
        tested_count += 1
        try:
            float(val_str)
            valid_count += 1
        except ValueError:
            pass
    if tested_count == 0:
        return False
    return (valid_count / tested_count) >= 0.7


def test_date_heuristic(samples: List[Any]) -> bool:
    """Checks if sample values look like dates."""
    date_patterns = [
        r"^\d{4}-\d{2}-\d{2}",
        r"^\d{2}[/-]\d{2}[/-]\d{4}",
        r"^\d{4}/\d{2}/\d{2}",
        r"^\d{4}-\d{2}-\d{2}T",
    ]
    valid_count = 0
    tested_count = 0
    for s in samples:
        if s is None:
            continue
        val_str = str(s).strip()
        if not val_str:
            continue
        tested_count += 1
        if any(re.search(pat, val_str) for pat in date_patterns):
            valid_count += 1
    if tested_count == 0:
        return False
    return (valid_count / tested_count) >= 0.6


def test_status_heuristic(samples: List[Any]) -> bool:
    """Checks if sample values match known status tokens."""
    known = {
        "success", "failed", "pending", "captured", "paid", "approved",
        "completed", "settled", "declined", "cancelled", "rejected",
        "void", "ok", "pass", "fail", "error", "processing", "queued",
        "1", "0", "true", "false"
    }
    valid_count = 0
    tested_count = 0
    for s in samples:
        if s is None:
            continue
        token = str(s).strip().lower()
        if not token:
            continue
        tested_count += 1
        if token in known:
            valid_count += 1
    if tested_count == 0:
        return False
    return (valid_count / tested_count) >= 0.5


class FinancialDatasetProfiler:
    """Discovers semantic structure and evaluates analytical capabilities of an arbitrary dataset."""

    @classmethod
    def profile(cls, parsed: ParsedDataset) -> DatasetProfile:
        headers = parsed.headers
        raw_rows = parsed.raw_rows
        row_count = len(raw_rows)

        mapped_fields: List[FieldMappingItem] = []
        mapped_canonicals: Set[str] = set()
        mapped_source_cols: Set[str] = set()

        # Step 1: Exact and primary synonym matching with type heuristics
        for col in headers:
            norm_col = normalize_col_name(col)
            # Check primary matches
            for canon, syn_spec in CANONICAL_SYNONYMS.items():
                if canon in mapped_canonicals:
                    continue
                if norm_col in syn_spec["primary"] or norm_col == canon:
                    samples = [r.get(col) for r in raw_rows[:15]]
                    expected_type = syn_spec["type"]
                    type_ok = True
                    if expected_type == "amount":
                        type_ok = test_amount_heuristic(samples)
                    elif expected_type == "date":
                        type_ok = test_date_heuristic(samples)
                    elif expected_type == "status":
                        type_ok = test_status_heuristic(samples)

                    confidence = "HIGH" if type_ok else "MEDIUM"
                    rationale = f"Primary synonym match for '{canon}'"
                    if not type_ok:
                        rationale += " (data type partially divergent from standard expectations)"

                    sample_strs = [str(s) for s in samples if s is not None and str(s).strip()][:3]
                    mapped_fields.append(
                        FieldMappingItem(
                            canonical_field=canon,
                            source_column=col,
                            confidence=confidence,
                            sample_values=sample_strs,
                            rationale=rationale,
                        )
                    )
                    mapped_canonicals.add(canon)
                    mapped_source_cols.add(col)
                    break

        # Step 2: Secondary synonym and fuzzy matching for remaining canonicals
        for col in headers:
            if col in mapped_source_cols:
                continue
            norm_col = normalize_col_name(col)
            for canon, syn_spec in CANONICAL_SYNONYMS.items():
                if canon in mapped_canonicals:
                    continue
                # Check secondary matches
                matched = False
                for sec in syn_spec["secondary"]:
                    if sec in norm_col or norm_col in sec:
                        matched = True
                        break

                if matched:
                    samples = [r.get(col) for r in raw_rows[:15]]
                    expected_type = syn_spec["type"]
                    type_ok = True
                    if expected_type == "amount":
                        type_ok = test_amount_heuristic(samples)
                    elif expected_type == "date":
                        type_ok = test_date_heuristic(samples)
                    elif expected_type == "status":
                        type_ok = test_status_heuristic(samples)

                    if (expected_type in ("amount", "date", "status")) and not type_ok:
                        continue

                    confidence = "MEDIUM"
                    rationale = f"Secondary semantic match for '{canon}' on header '{col}'"
                    sample_strs = [str(s) for s in samples if s is not None and str(s).strip()][:3]
                    mapped_fields.append(
                        FieldMappingItem(
                            canonical_field=canon,
                            source_column=col,
                            confidence=confidence,
                            sample_values=sample_strs,
                            rationale=rationale,
                        )
                    )
                    mapped_canonicals.add(canon)
                    mapped_source_cols.add(col)
                    break

        # Step 3: Identify unmapped columns
        unmapped_cols = [c for c in headers if c not in mapped_source_cols]

        # Step 4: Evaluate Capability Matrix
        capabilities = cls.evaluate_capabilities(mapped_canonicals, row_count)

        # Step 5: Profiling Notes
        notes: List[str] = []
        if parsed.truncated:
            notes.append(f"Dataset exceeded maximum row display limit. Truncated to first {row_count} rows.")
        if row_count < 10:
            notes.append(
                f"Small sample size notice: Dataset contains {row_count} rows. Statistical risk metrics "
                "should be interpreted with caution."
            )
        if "amount" not in mapped_canonicals:
            notes.append("No financial amount column identified; volume and exposure calculations are disabled.")
        if "transaction_id" not in mapped_canonicals:
            notes.append("No distinct transaction ID found; auto-generating deterministic row identifiers.")

        return DatasetProfile(
            file_format=parsed.file_format,
            row_count=row_count,
            raw_columns=headers,
            mapped_fields=mapped_fields,
            unmapped_columns=unmapped_cols,
            capabilities=capabilities,
            profiling_notes=notes,
        )

    @classmethod
    def evaluate_capabilities(
        cls,
        mapped_canonicals: Set[str],
        row_count: int,
    ) -> List[CapabilityItem]:
        """Calculates which financial capabilities are available based on mapped fields."""
        items: List[CapabilityItem] = []

        # 1. TRANSACTION_METRICS
        req = ["amount"]
        missing = [f for f in req if f not in mapped_canonicals]
        avail = len(missing) == 0
        items.append(
            CapabilityItem(
                capability_id="TRANSACTION_METRICS",
                name="Transaction Volume & Extremes",
                available=avail,
                required_fields=req,
                missing_fields=missing,
                reason="Available (gross volume, average amount, and extremes computed)" if avail
                else "Unavailable: amount column not identified.",
            )
        )

        # 2. STATUS_DISTRIBUTION
        req = ["status"]
        missing = [f for f in req if f not in mapped_canonicals]
        avail = len(missing) == 0
        items.append(
            CapabilityItem(
                capability_id="STATUS_DISTRIBUTION",
                name="Transaction Outcome & Failure Rate",
                available=avail,
                required_fields=req,
                missing_fields=missing,
                reason="Available (success, failure, and pending status ratios computed)" if avail
                else "Unavailable: status column not identified.",
            )
        )

        # 3. SETTLEMENT_RECONCILIATION
        req = ["settlement_amount"]
        has_settle = ("settlement_amount" in mapped_canonicals or "settlement_id" in mapped_canonicals)
        missing = [] if has_settle else ["settlement_amount"]
        items.append(
            CapabilityItem(
                capability_id="SETTLEMENT_RECONCILIATION",
                name="Bank Settlement Discrepancy & Deficit",
                available=has_settle,
                required_fields=["settlement_amount"],
                missing_fields=missing,
                reason="Available (reconciles gateway payments with acquirer settlement batches)" if has_settle
                else "Settlement data not present — Settlement reconciliation unavailable.",
            )
        )

        # 4. SETTLEMENT_TIMING_SLA
        req = ["transaction_date", "settlement_date"]
        missing = [f for f in req if f not in mapped_canonicals]
        avail = len(missing) == 0
        items.append(
            CapabilityItem(
                capability_id="SETTLEMENT_TIMING_SLA",
                name="Acquirer Settlement SLA & Timing",
                available=avail,
                required_fields=req,
                missing_fields=missing,
                reason="Available (measures clearing latency and regulatory SLA adherence)" if avail
                else f"Unavailable: missing {', '.join(missing)}.",
            )
        )

        # 5. REFUND_ANALYSIS
        req = ["refund_amount"]
        missing = [f for f in req if f not in mapped_canonicals]
        avail = len(missing) == 0
        items.append(
            CapabilityItem(
                capability_id="REFUND_ANALYSIS",
                name="Dispute & Refund Leakage Analysis",
                available=avail,
                required_fields=req,
                missing_fields=missing,
                reason="Available (analyzes dispute ratios and double-dip reversals)" if avail
                else "Refund data not present — dispute/refund analysis unavailable.",
            )
        )

        # 6. MERCHANT_CONCENTRATION
        req = ["merchant_id"]
        missing = [f for f in req if f not in mapped_canonicals]
        avail = len(missing) == 0
        items.append(
            CapabilityItem(
                capability_id="MERCHANT_CONCENTRATION",
                name="Merchant Concentration & Risk Ranking",
                available=avail,
                required_fields=req,
                missing_fields=missing,
                reason="Available (merchant portfolio concentration and anomaly volume computed)" if avail
                else "Merchant identifier not present — merchant concentration breakdown unavailable.",
            )
        )

        # 7. LEDGER_AUDIT
        has_ledger = ("debit" in mapped_canonicals and "credit" in mapped_canonicals) or ("balance" in mapped_canonicals)
        missing = [] if has_ledger else ["debit", "credit"]
        items.append(
            CapabilityItem(
                capability_id="LEDGER_AUDIT",
                name="Nodal Ledger Balance Continuity",
                available=has_ledger,
                required_fields=["debit", "credit"],
                missing_fields=missing,
                reason="Available (verifies double-entry ledger balance continuity)" if has_ledger
                else "Ledger postings not provided — nodal ledger audit unavailable.",
            )
        )

        # 8. DETERMINISTIC_EXCEPTIONS
        has_det = "amount" in mapped_canonicals and (
            "status" in mapped_canonicals or has_settle or ("refund_amount" in mapped_canonicals)
        )
        items.append(
            CapabilityItem(
                capability_id="DETERMINISTIC_EXCEPTIONS",
                name="Deterministic Exception Detection",
                available=has_det,
                required_fields=["amount"],
                missing_fields=[] if has_det else ["amount"],
                reason="Available (rule-based detection in ephemeral SQLite)" if has_det
                else "Unavailable: requires at least transaction amount and status/settlement fields.",
            )
        )

        # 9. PATTERN_MINING
        can_mine = has_det and row_count >= 2
        items.append(
            CapabilityItem(
                capability_id="PATTERN_MINING",
                name="Recurring Pattern Mining",
                available=can_mine,
                required_fields=["amount"],
                missing_fields=[] if can_mine else (["amount"] if not has_det else ["at least 2 records"]),
                reason="Available (clusters recurrent failure signatures across merchants)" if can_mine
                else "Pattern mining requires deterministic exceptions and at least 2 records.",
            )
        )

        return items
