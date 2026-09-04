"""Deterministic Sandbox Analysis and Validation Service for Nodexa.

Executes the existing finance-control detection and pattern mining pipeline inside
an isolated, ephemeral in-memory SQLite database. Guarantees 100% zero mutation
of production PostgreSQL/SQLite tables or seed data.
"""
import csv
import io
import re
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from backend.models.database import Base
from backend.models.financial_sources import (
    GatewayTransaction,
    MerchantOrder,
    BankSettlementBatch,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.enums import ExceptionState, ExceptionType, PolicyActionType
from backend.exceptions.service import ExceptionDetectionService
from backend.patterns.miner import PatternMinerService
from backend.sandbox.models import (
    SandboxValidationIssue,
    SandboxValidationResult,
    SandboxExceptionItem,
    SandboxPatternItem,
    SandboxDatasetSummary,
    SandboxAnalysisReport,
)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 Megabytes
MAX_ROWS = 5000

REQUIRED_COLUMNS = [
    "transaction_id",
    "merchant_id",
    "amount",
    "status",
    "transaction_date",
]

OPTIONAL_COLUMNS = [
    "settlement_id",
    "settlement_amount",
    "refund_amount",
    "order_id",
    "order_amount",
]

RECOMMENDED_ACTIONS: Dict[str, str] = {
    ExceptionType.GHOST_SETTLEMENT.value: "Initiate credit reversal and notify acquiring partner of unverified settlement credit.",
    ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value: "Place merchant hold on second payout and verify dispute documentation.",
    ExceptionType.SETTLEMENT_SLA_BREACH.value: "Flag acquiring bank SLA breach for penalty reconciliation and treasury rebalancing.",
    ExceptionType.PARTIAL_SETTLEMENT.value: "Demand settlement reconciliation line item from bank for remaining balance deficit.",
    ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value: "Allocate orphaned bank clearing credit to pending merchant escrow balance.",
    ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value: "No intervention needed. Verified legitimate multi-day banking holiday window.",
}


def parse_date(date_str: str) -> Optional[datetime]:
    """Parses various date formats safely."""
    clean = str(date_str).strip()
    if not clean:
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
            # If the user passed raw paise (e.g. 150000), or integer rupees
            # Assume any float or small integer < 10000 with decimals is rupees
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


class SandboxValidationService:
    """Validates uploaded CSV datasets against the standard Nodexa operational schema."""

    @staticmethod
    def validate_csv(csv_content: str) -> Tuple[SandboxValidationResult, List[Dict[str, Any]]]:
        """Performs full syntactic, schema, and data type validation on raw CSV text."""
        # 1. Byte size safety check
        byte_size = len(csv_content.encode("utf-8"))
        if byte_size > MAX_UPLOAD_BYTES:
            return SandboxValidationResult(
                is_valid=False,
                total_rows=0,
                valid_rows=0,
                invalid_rows=0,
                columns_detected=[],
                missing_required_columns=[],
                errors=[
                    SandboxValidationIssue(
                        row_number=0,
                        field="file_size",
                        error=f"File exceeds maximum allowed size of 5 MB ({round(byte_size / (1024 * 1024), 2)} MB)",
                        raw_value=str(byte_size),
                    )
                ],
                preview_rows=[],
                message="File size exceeds the 5 MB limit. Please upload a smaller dataset.",
            ), []

        # 2. Parse CSV
        reader = csv.DictReader(io.StringIO(csv_content))
        if not reader.fieldnames:
            return SandboxValidationResult(
                is_valid=False,
                total_rows=0,
                valid_rows=0,
                invalid_rows=0,
                columns_detected=[],
                missing_required_columns=REQUIRED_COLUMNS,
                errors=[
                    SandboxValidationIssue(
                        row_number=0,
                        field="header",
                        error="CSV file is empty or missing a valid header row.",
                        raw_value=None,
                    )
                ],
                preview_rows=[],
                message="CSV file is empty or has no header row.",
            ), []

        # Normalize fieldnames
        detected_columns = [col.strip().lower() for col in reader.fieldnames if col]
        missing = [req for req in REQUIRED_COLUMNS if req not in detected_columns]

        if missing:
            return SandboxValidationResult(
                is_valid=False,
                total_rows=0,
                valid_rows=0,
                invalid_rows=0,
                columns_detected=detected_columns,
                missing_required_columns=missing,
                errors=[
                    SandboxValidationIssue(
                        row_number=1,
                        field=col,
                        error=f"Required column '{col}' is missing from CSV header.",
                        raw_value=None,
                    )
                    for col in missing
                ],
                preview_rows=[],
                message=f"Missing required columns: {', '.join(missing)}.",
            ), []

        # 3. Row-level validation
        issues: List[SandboxValidationIssue] = []
        valid_rows: List[Dict[str, Any]] = []
        preview_rows: List[Dict[str, Any]] = []
        seen_tx_ids = set()
        row_idx = 1  # 1-based, header is row 1

        for raw_row in reader:
            row_idx += 1
            if row_idx > MAX_ROWS + 1:
                issues.append(
                    SandboxValidationIssue(
                        row_number=row_idx,
                        field="row_limit",
                        error=f"Dataset exceeds the maximum limit of {MAX_ROWS} rows.",
                    )
                )
                break

            # Strip whitespace and lowercase keys
            row = {k.strip().lower(): v.strip() if isinstance(v, str) else v for k, v in raw_row.items() if k}
            has_error = False

            # Transaction ID
            tx_id = row.get("transaction_id")
            if not tx_id:
                issues.append(SandboxValidationIssue(row_number=row_idx, field="transaction_id", error="Missing transaction_id"))
                has_error = True
            elif tx_id in seen_tx_ids:
                issues.append(SandboxValidationIssue(row_number=row_idx, field="transaction_id", error=f"Duplicate transaction_id: {tx_id}", raw_value=tx_id))
                has_error = True
            else:
                seen_tx_ids.add(tx_id)

            # Merchant ID
            merch_id = row.get("merchant_id")
            if not merch_id:
                issues.append(SandboxValidationIssue(row_number=row_idx, field="merchant_id", error="Missing merchant_id"))
                has_error = True

            # Amount
            amt_raw = row.get("amount")
            amt_paise = parse_amount_to_paise(amt_raw)
            if amt_paise is None or amt_paise <= 0:
                issues.append(SandboxValidationIssue(row_number=row_idx, field="amount", error=f"Invalid transaction amount: '{amt_raw}' (must be positive number)", raw_value=str(amt_raw)))
                has_error = True

            # Status
            status = (row.get("status") or "").upper()
            if status not in ("SUCCESS", "FAILED"):
                issues.append(SandboxValidationIssue(row_number=row_idx, field="status", error=f"Status '{status}' invalid. Expected 'SUCCESS' or 'FAILED'", raw_value=status))
                has_error = True

            # Transaction Date
            date_raw = row.get("transaction_date")
            tx_date = parse_date(date_raw)
            if not tx_date:
                issues.append(SandboxValidationIssue(row_number=row_idx, field="transaction_date", error=f"Invalid date format: '{date_raw}'", raw_value=str(date_raw)))
                has_error = True

            # Optional settlement validation
            settle_id = row.get("settlement_id") or None
            settle_amt_raw = row.get("settlement_amount")
            settle_amt_paise = parse_amount_to_paise(settle_amt_raw) if settle_amt_raw else None

            # Optional refund validation
            refund_amt_raw = row.get("refund_amount")
            refund_amt_paise = parse_amount_to_paise(refund_amt_raw) if refund_amt_raw else 0

            # Optional order validation
            order_id = row.get("order_id") or None
            order_amt_raw = row.get("order_amount")
            order_amt_paise = parse_amount_to_paise(order_amt_raw) if order_amt_raw else amt_paise

            if not has_error:
                normalized = {
                    "transaction_id": tx_id,
                    "merchant_id": merch_id,
                    "amount_paise": amt_paise,
                    "status": status,
                    "transaction_date": tx_date,
                    "settlement_id": settle_id,
                    "settlement_amount_paise": settle_amt_paise,
                    "refund_amount_paise": refund_amt_paise or 0,
                    "order_id": order_id,
                    "order_amount_paise": order_amt_paise or amt_paise,
                }
                valid_rows.append(normalized)

            # Store first 10 rows for preview regardless of errors
            if len(preview_rows) < 10:
                preview_rows.append({
                    "row": row_idx - 1,
                    "transaction_id": tx_id or "—",
                    "merchant_id": merch_id or "—",
                    "amount": amt_raw or "—",
                    "status": status or "—",
                    "transaction_date": date_raw or "—",
                    "settlement_id": settle_id or "—",
                    "settlement_amount": settle_amt_raw or "—",
                    "refund_amount": refund_amt_raw or "—",
                    "is_valid": not has_error,
                })

        total_rows = row_idx - 1
        valid_count = len(valid_rows)
        invalid_count = total_rows - valid_count
        is_valid = total_rows > 0 and invalid_count == 0

        if total_rows == 0:
            msg = "CSV contains a header but zero operational data rows."
        elif is_valid:
            msg = f"Dataset validated successfully: {valid_count} valid operational records ready for sandbox analysis."
        else:
            msg = f"Validation failed: {invalid_count} of {total_rows} rows contain errors. Review issues below."

        result = SandboxValidationResult(
            is_valid=is_valid,
            total_rows=total_rows,
            valid_rows=valid_count,
            invalid_rows=invalid_count,
            columns_detected=detected_columns,
            missing_required_columns=[],
            errors=issues[:50],  # cap at 50 for display
            preview_rows=preview_rows,
            message=msg,
        )
        return result, valid_rows


class SandboxAnalysisService:
    """Executes deterministic exception detection and pattern mining on isolated in-memory datasets."""

    @staticmethod
    def analyze_dataset(valid_rows: List[Dict[str, Any]], dataset_name: str = "sandbox_dataset.csv") -> SandboxAnalysisReport:
        """Loads valid rows into an isolated in-memory SQLite database and executes the detection pipeline."""
        now_utc = datetime.now(timezone.utc)

        # 1. Initialize isolated in-memory SQLite database (100% ephemeral)
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine)
        SandboxSession = sessionmaker(bind=engine)
        session = SandboxSession()

        try:
            # 2. Populate operational models into in-memory sandbox
            gw_count = 0
            order_count = 0
            settle_count = 0
            dispute_count = 0
            ledger_count = 0
            merchants_set = set()

            running_balance = 0

            for r in valid_rows:
                tx_id = r["transaction_id"]
                merch_id = r["merchant_id"]
                merchants_set.add(merch_id)
                amt = r["amount_paise"]
                tx_date = r["transaction_date"]
                status = r["status"]

                # Gateway Transaction
                gw = GatewayTransaction(
                    payment_id=tx_id,
                    merchant_id=merch_id,
                    amount=amt,
                    currency="INR",
                    status=status,
                    created_at=tx_date,
                    method="UPI",
                )
                session.add(gw)
                gw_count += 1

                # Merchant Order
                ord_id = r["order_id"] or f"ORD_{tx_id}"
                ord_amt = r["order_amount_paise"]
                mo = MerchantOrder(
                    order_id=ord_id,
                    payment_id_reference=tx_id,
                    customer_id=f"CUST_{merch_id}",
                    fulfillment_status="DELIVERED" if status == "SUCCESS" else "CANCELLED",
                    order_amount=ord_amt,
                    created_at=tx_date,
                )
                session.add(mo)
                order_count += 1

                # Settlement Batch (if present)
                if r.get("settlement_id") or r.get("settlement_amount_paise") is not None:
                    s_id = r.get("settlement_id") or f"SETTLE_{tx_id}"
                    s_amt = r.get("settlement_amount_paise") if r.get("settlement_amount_paise") is not None else amt
                    sb = BankSettlementBatch(
                        settlement_id=s_id,
                        payment_id=tx_id,
                        net_amount=s_amt,
                        acquirer_id="ACQ_HDFC",
                        clearing_timestamp=tx_date + timedelta(hours=2),
                        created_at=tx_date + timedelta(hours=2),
                    )
                    session.add(sb)
                    settle_count += 1

                # Dispute / Refund (if refund amount > 0)
                if r.get("refund_amount_paise", 0) > 0:
                    ref_amt = r["refund_amount_paise"]
                    evt = DisputeRefundEvent(
                        event_id=f"EVT_REF_{tx_id}",
                        payment_id=tx_id,
                        event_type="REFUND",
                        amount=ref_amt,
                        timestamp=tx_date + timedelta(hours=4),
                    )
                    session.add(evt)
                    dispute_count += 1

                # Nodal Ledger Postings (matching double-entry progression)
                if status == "SUCCESS":
                    running_balance += amt
                    session.add(
                        NodalLedgerEntry(
                            ledger_id=f"LEDGER_{tx_id}_CR",
                            transaction_id=tx_id,
                            account_id="nodal_escrow_main",
                            debit=0,
                            credit=amt,
                            balance_after=running_balance,
                            timestamp=tx_date,
                            entry_type="PAYMENT_CREDIT",
                            reference=f"PAYMENT_{tx_id}",
                        )
                    )
                    ledger_count += 1

            session.commit()

            # 3. Execute Existing Deterministic Exception Detection Engine
            detection_service = ExceptionDetectionService()
            detection_report = detection_service.detect_exceptions(session=session, account_id="nodal_escrow_main")

            # 4. Execute Existing Pattern Miner Service
            pattern_miner = PatternMinerService(min_cluster_size=2)
            mined_clusters = pattern_miner.mine_patterns(session=session, persist=True)

            # 5. Extract structured exception items
            exception_items: List[SandboxExceptionItem] = []
            high_risk_count = 0

            for exc in detection_report.exceptions:
                severity = exc.get("severity", "MEDIUM")
                if severity in ("HIGH", "CRITICAL"):
                    high_risk_count += 1

                exp_minor = exc.get("exposure", 0)
                exc_type = exc.get("exception_type", "UNKNOWN")
                action_rec = RECOMMENDED_ACTIONS.get(exc_type, "Review and investigate discrepancy with merchant partner.")

                exception_items.append(
                    SandboxExceptionItem(
                        exception_id=exc.get("exception_id", "EXC-000"),
                        exception_type=exc_type,
                        severity=severity,
                        exposure_minor_units=exp_minor,
                        exposure_inr_formatted=format_inr(exp_minor),
                        primary_payment_id=exc.get("primary_payment_id"),
                        primary_order_id=exc.get("primary_order_id"),
                        description=exc.get("description"),
                        is_legitimate_observation=exc.get("is_legitimate_observation", False),
                        evidence=exc.get("evidence", []),
                        recommended_action=action_rec,
                    )
                )

            # 6. Extract structured pattern items
            pattern_items: List[SandboxPatternItem] = []
            for cl in mined_clusters:
                cl_exp = cl.get("total_exposure", 0)
                pattern_items.append(
                    SandboxPatternItem(
                        cluster_id=cl.get("cluster_id", "CL-000"),
                        pattern_type=cl.get("pattern_type", "RECURRING_DISCREPANCY"),
                        exception_count=cl.get("exception_count", 0),
                        total_exposure_minor_units=cl_exp,
                        total_exposure_inr_formatted=format_inr(cl_exp),
                        signature=cl.get("signature", {}),
                        description=cl.get("description", "Recurring anomaly cluster discovered."),
                    )
                )

            # 7. Compile final report
            total_records = gw_count + order_count + settle_count + dispute_count + ledger_count
            report = SandboxAnalysisReport(
                status="COMPLETED",
                dataset_name=dataset_name,
                evaluated_at=now_utc.isoformat(),
                isolation_mode="EPHEMERAL_IN_MEMORY_SQLITE",
                production_database_modified=False,
                dataset_summary=SandboxDatasetSummary(
                    total_records=total_records,
                    gateway_transactions=gw_count,
                    merchant_orders=order_count,
                    settlement_batches=settle_count,
                    dispute_events=dispute_count,
                    ledger_entries=ledger_count,
                    merchants_impacted=len(merchants_set),
                ),
                exceptions_detected=len(exception_items),
                high_risk_cases=high_risk_count,
                total_exposure_minor_units=detection_report.total_exposure,
                total_exposure_inr_formatted=format_inr(detection_report.total_exposure),
                recurring_patterns_count=len(pattern_items),
                ground_truth_available=False,
                ground_truth_status="Not provided",
                accuracy_metrics_message="Accuracy metrics (Precision/Recall/F1) unavailable for this dataset because external ground-truth labels were not supplied.",
                exceptions=exception_items,
                patterns=pattern_items,
            )
            return report

        finally:
            session.close()
            engine.dispose()


def get_sample_sandbox_csv() -> str:
    """Returns a ready-to-run canonical sample CSV dataset containing representative anomalies."""
    rows = [
        "transaction_id,merchant_id,amount,status,transaction_date,settlement_id,settlement_amount,refund_amount,order_id,order_amount",
        # Clean normal transactions
        "TXN_SANDBOX_101,MERCH_ALPHA,1499.00,SUCCESS,2026-03-01T10:00:00Z,SETTLE_B101,1499.00,0,ORD_101,1499.00",
        "TXN_SANDBOX_102,MERCH_ALPHA,2999.00,SUCCESS,2026-03-01T10:15:00Z,SETTLE_B102,2999.00,0,ORD_102,2999.00",
        "TXN_SANDBOX_103,MERCH_BETA,450.00,SUCCESS,2026-03-01T11:00:00Z,SETTLE_B103,450.00,0,ORD_103,450.00",
        "TXN_SANDBOX_104,MERCH_GAMMA,890.00,FAILED,2026-03-01T11:30:00Z,,,0,ORD_104,890.00",
        # Ghost settlement scenario (Settlement recorded for payment that does not exist or was failed)
        "TXN_SANDBOX_GHOST_105,MERCH_DELTA,7500.00,FAILED,2026-03-01T12:00:00Z,SETTLE_GHOST_105,7500.00,0,ORD_105,7500.00",
        # Partial settlement / deficit scenario
        "TXN_SANDBOX_PARTIAL_106,MERCH_ALPHA,5000.00,SUCCESS,2026-03-01T12:30:00Z,SETTLE_PART_106,3200.00,0,ORD_106,5000.00",
        # Refund chargeback double dip scenario
        "TXN_SANDBOX_DOUBLEDIP_107,MERCH_BETA,3400.00,SUCCESS,2026-03-01T13:00:00Z,SETTLE_DD_107,3400.00,3400.00,ORD_107,3400.00",
        # Additional clean baseline transactions
        "TXN_SANDBOX_108,MERCH_GAMMA,1200.00,SUCCESS,2026-03-01T13:45:00Z,SETTLE_B108,1200.00,0,ORD_108,1200.00",
        "TXN_SANDBOX_109,MERCH_DELTA,650.00,SUCCESS,2026-03-01T14:10:00Z,SETTLE_B109,650.00,0,ORD_109,650.00",
        "TXN_SANDBOX_110,MERCH_ALPHA,1800.00,SUCCESS,2026-03-01T14:30:00Z,SETTLE_B110,1800.00,0,ORD_110,1800.00",
        "TXN_SANDBOX_111,MERCH_BETA,2400.00,SUCCESS,2026-03-01T15:00:00Z,SETTLE_B111,2400.00,0,ORD_111,2400.00",
        "TXN_SANDBOX_112,MERCH_GAMMA,3100.00,SUCCESS,2026-03-01T15:30:00Z,SETTLE_B112,3100.00,0,ORD_112,3100.00",
        # Second double dip anomaly to form a recurring pattern
        "TXN_SANDBOX_DOUBLEDIP_113,MERCH_BETA,4200.00,SUCCESS,2026-03-01T16:00:00Z,SETTLE_DD_113,4200.00,4200.00,ORD_113,4200.00",
        # Clean closing records
        "TXN_SANDBOX_114,MERCH_DELTA,950.00,SUCCESS,2026-03-01T16:30:00Z,SETTLE_B114,950.00,0,ORD_114,950.00",
        "TXN_SANDBOX_115,MERCH_ALPHA,520.00,SUCCESS,2026-03-01T17:00:00Z,SETTLE_B115,520.00,0,ORD_115,520.00",
    ]
    return "\n".join(rows)
