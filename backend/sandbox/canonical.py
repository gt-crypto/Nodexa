"""Transforms raw dataset rows into canonical financial records using the dataset profile."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from backend.sandbox.models import DatasetProfile


def parse_date(date_str: Any) -> Optional[datetime]:
    """Parses various date formats safely."""
    if date_str is None:
        return None
    clean = str(date_str).strip()
    if not clean or clean.lower() in ("nan", "null", "none"):
        return None
    formats = [
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(clean.replace("Z", "+00:00") if "Z" in clean else clean, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def parse_amount_to_paise(val: Any) -> Optional[int]:
    """Converts a string or float numeric currency into integer minor units (paise)."""
    if val is None:
        return None
    clean = str(val).strip().replace(",", "").replace("₹", "").replace("$", "")
    if not clean or clean.lower() in ("nan", "null", "none"):
        return None
    try:
        # Check if already integer
        if clean.isdigit() or (clean.startswith("-") and clean[1:].isdigit()):
            return int(clean)
        # Decimal rupees -> paise
        amt_float = float(clean)
        return int(round(amt_float * 100))
    except (ValueError, TypeError):
        return None


def format_inr(paise: int) -> str:
    """Formats paise minor units into human readable INR."""
    rupees = paise / 100.0
    return f"₹{rupees:,.2f}"



class CanonicalFinancialRow(BaseModel):
    """Normalized internal representation of a financial record."""
    row_number: int
    transaction_id: str
    merchant_id: str
    amount_paise: int
    status: str  # "SUCCESS", "FAILED", "PENDING"
    transaction_date: datetime
    settlement_id: Optional[str] = None
    settlement_amount_paise: Optional[int] = None
    settlement_date: Optional[datetime] = None
    refund_amount_paise: int = 0
    order_id: Optional[str] = None
    order_amount_paise: Optional[int] = None
    debit_paise: Optional[int] = None
    credit_paise: Optional[int] = None
    balance_paise: Optional[int] = None
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    original_row: Dict[str, Any] = Field(default_factory=dict)


def normalize_status(val: Any) -> str:
    """Normalizes raw status strings/integers to SUCCESS, FAILED, or PENDING."""
    if val is None:
        return "SUCCESS"
    token = str(val).strip().upper()
    if token in ("SUCCESS", "CAPTURED", "PAID", "APPROVED", "COMPLETED", "SETTLED", "OK", "PASS", "1", "TRUE"):
        return "SUCCESS"
    if token in ("FAILED", "DECLINED", "CANCELLED", "REJECTED", "VOID", "FAIL", "0", "FALSE", "ERROR"):
        return "FAILED"
    if token in ("PENDING", "IN_PROGRESS", "PROCESSING", "QUEUED"):
        return "PENDING"
    return "SUCCESS"


def transform_to_canonical(
    profile: DatasetProfile,
    raw_rows: List[Dict[str, Any]],
) -> Tuple[List[CanonicalFinancialRow], List[str]]:
    """Maps raw rows into CanonicalFinancialRow list using discovered column mappings."""
    mapping_by_canon: Dict[str, str] = {
        m.canonical_field: m.source_column for m in profile.mapped_fields
    }
    warnings: List[str] = []
    canonical_rows: List[CanonicalFinancialRow] = []

    now_utc = datetime.now(timezone.utc)
    seen_tx_ids = set()

    for idx, raw in enumerate(raw_rows, start=1):
        # 1. Transaction ID
        tx_col = mapping_by_canon.get("transaction_id")
        tx_id_raw = raw.get(tx_col) if tx_col else None
        tx_id = str(tx_id_raw).strip() if tx_id_raw is not None and str(tx_id_raw).strip() else f"TXN_ROW_{idx}"
        if tx_id in seen_tx_ids:
            tx_id = f"{tx_id}_DUP_{idx}"
        seen_tx_ids.add(tx_id)

        # 2. Merchant ID
        merch_col = mapping_by_canon.get("merchant_id")
        merch_id_raw = raw.get(merch_col) if merch_col else None
        merch_id = str(merch_id_raw).strip() if merch_id_raw is not None and str(merch_id_raw).strip() else "MERCH_DEFAULT"

        # 3. Amount
        amt_col = mapping_by_canon.get("amount")
        amt_raw = raw.get(amt_col) if amt_col else None
        amt_paise = parse_amount_to_paise(amt_raw)
        if amt_paise is None or amt_paise < 0:
            amt_paise = 0

        # 4. Status
        stat_col = mapping_by_canon.get("status")
        stat_raw = raw.get(stat_col) if stat_col else None
        status = normalize_status(stat_raw) if stat_raw is not None else "SUCCESS"

        # 5. Transaction Date
        date_col = mapping_by_canon.get("transaction_date")
        date_raw = raw.get(date_col) if date_col else None
        tx_date = parse_date(str(date_raw)) if date_raw else None
        if not tx_date:
            tx_date = now_utc

        # 6. Settlement Fields
        settle_id_col = mapping_by_canon.get("settlement_id")
        settle_id = str(raw[settle_id_col]).strip() if settle_id_col and raw.get(settle_id_col) is not None else None

        settle_amt_col = mapping_by_canon.get("settlement_amount")
        settle_amt_raw = raw.get(settle_amt_col) if settle_amt_col else None
        settle_amt_paise = parse_amount_to_paise(settle_amt_raw) if settle_amt_raw is not None else None

        settle_date_col = mapping_by_canon.get("settlement_date")
        settle_date_raw = raw.get(settle_date_col) if settle_date_col else None
        settle_date = parse_date(str(settle_date_raw)) if settle_date_raw else None

        # 7. Refund
        ref_col = mapping_by_canon.get("refund_amount")
        ref_raw = raw.get(ref_col) if ref_col else None
        ref_amt_paise = parse_amount_to_paise(ref_raw) if ref_raw is not None else 0

        # 8. Order
        ord_col = mapping_by_canon.get("order_id")
        ord_id = str(raw[ord_col]).strip() if ord_col and raw.get(ord_col) is not None else None

        ord_amt_col = mapping_by_canon.get("order_amount")
        ord_amt_raw = raw.get(ord_amt_col) if ord_amt_col else None
        ord_amt_paise = parse_amount_to_paise(ord_amt_raw) if ord_amt_raw is not None else None

        # 9. Ledger
        debit_col = mapping_by_canon.get("debit")
        debit_paise = parse_amount_to_paise(raw.get(debit_col)) if debit_col else None

        credit_col = mapping_by_canon.get("credit")
        credit_paise = parse_amount_to_paise(raw.get(credit_col)) if credit_col else None

        balance_col = mapping_by_canon.get("balance")
        balance_paise = parse_amount_to_paise(raw.get(balance_col)) if balance_col else None

        # Fallback amt_paise if amount column is absent but other monetary columns exist
        if amt_paise == 0:
            if settle_amt_paise is not None:
                amt_paise = settle_amt_paise
            elif ord_amt_paise is not None:
                amt_paise = ord_amt_paise
            elif ref_amt_paise:
                amt_paise = ref_amt_paise
            elif credit_paise is not None:
                amt_paise = credit_paise
            elif debit_paise is not None:
                amt_paise = debit_paise

        canonical_rows.append(
            CanonicalFinancialRow(
                row_number=idx,
                transaction_id=tx_id,
                merchant_id=merch_id,
                amount_paise=amt_paise,
                status=status,
                transaction_date=tx_date,
                settlement_id=settle_id,
                settlement_amount_paise=settle_amt_paise,
                settlement_date=settle_date,
                refund_amount_paise=ref_amt_paise or 0,
                order_id=ord_id,
                order_amount_paise=ord_amt_paise,
                debit_paise=debit_paise,
                credit_paise=credit_paise,
                balance_paise=balance_paise,
                raw_data=raw,
                original_row=raw,
            )
        )

    return canonical_rows, warnings
