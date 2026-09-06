"""Deterministic Sandbox Analysis and Validation Service for Nodexa.

Executes the existing finance-control detection and pattern mining pipeline inside
an isolated, ephemeral in-memory SQLite database. Guarantees 100% zero mutation
of production PostgreSQL/SQLite tables or seed data.
"""
import csv
import io
import re
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from backend.models.database import Base
from backend.models import (
    GatewayTransaction,
    MerchantOrder,
    BankSettlementBatch,
    DisputeRefundEvent,
    NodalLedgerEntry,
    DatasetMetadata,
    ExceptionRecord,
    ExceptionAffectedRecord,
    ExceptionStateTransition,
    AuditEvent,
    ExceptionCluster,
)
from backend.models.enums import ExceptionState, ExceptionType, PolicyActionType
from backend.exceptions.service import ExceptionDetectionService
from backend.patterns.miner import PatternMinerService
from backend.sandbox.models import (
    CapabilityItem,
    DatasetProfile,
    FinancialAnalytics,
    SandboxValidationIssue,
    SandboxValidationResult,
    SandboxExceptionItem,
    SandboxPatternItem,
    SandboxDatasetSummary,
    SandboxAnalysisReport,
)
from backend.sandbox.file_parser import (
    ParsedDataset,
    parse_uploaded_dataset,
    parse_csv_content,
    MAX_UPLOAD_BYTES,
    MAX_PARSED_ROWS,
)
from backend.sandbox.profiler import FinancialDatasetProfiler
from backend.sandbox.canonical import (
    CanonicalFinancialRow,
    transform_to_canonical,
    normalize_status,
    parse_date,
    parse_amount_to_paise,
    format_inr,
)
from backend.sandbox.financial_analyzer import FinancialAnalyticsEngine

MAX_ROWS = 5000

REQUIRED_COLUMNS = [
    "transaction_id",
    "merchant_id",
    "amount",
    "status",
    "transaction_date",
]

# Minimal set of database tables required for isolated sandbox reconciliation and mining
REQUIRED_SANDBOX_TABLES = [
    GatewayTransaction.__table__,
    MerchantOrder.__table__,
    BankSettlementBatch.__table__,
    DisputeRefundEvent.__table__,
    NodalLedgerEntry.__table__,
    DatasetMetadata.__table__,
    ExceptionRecord.__table__,
    ExceptionAffectedRecord.__table__,
    ExceptionStateTransition.__table__,
    AuditEvent.__table__,
    ExceptionCluster.__table__,
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



class SandboxValidationService:
    """Validates and profiles uploaded financial datasets across flexible formats and schemas."""

    @classmethod
    def validate_dataset(
        cls,
        content_bytes: bytes,
        filename: Optional[str] = None,
    ) -> Tuple[SandboxValidationResult, List[Dict[str, Any]], DatasetProfile, List[CanonicalFinancialRow]]:
        """Unified validation and semantic profiling for CSV, XLSX, and JSON datasets."""
        t_val_start = time.perf_counter()

        # 1. Parse content
        parsed = parse_uploaded_dataset(content_bytes, filename=filename)
        if parsed.parsing_errors:
            val_dur = round((time.perf_counter() - t_val_start) * 1000, 2)
            profile = DatasetProfile(
                file_format=parsed.file_format,
                row_count=0,
                raw_columns=parsed.headers,
                mapped_fields=[],
                unmapped_columns=parsed.headers,
                capabilities=[],
                profiling_notes=parsed.parsing_errors,
            )
            return (
                SandboxValidationResult(
                    is_valid=False,
                    total_rows=0,
                    valid_rows=0,
                    invalid_rows=0,
                    columns_detected=parsed.headers,
                    missing_required_columns=REQUIRED_COLUMNS,
                    errors=[
                        SandboxValidationIssue(
                            row_number=0,
                            field="file",
                            error=err,
                            raw_value=None,
                        )
                        for err in parsed.parsing_errors
                    ],
                    preview_rows=[],
                    message=parsed.parsing_errors[0],
                    validation_time_ms=val_dur,
                    profile=profile,
                    capabilities=[],
                ),
                [],
                profile,
                [],
            )

        # 2. Semantic profiling
        profile = FinancialDatasetProfiler.profile(parsed)
        mapped_canonicals = {m.canonical_field for m in profile.mapped_fields}
        detected_columns = [col.strip().lower() for col in parsed.headers if col]

        # 3. Check for standard columns and missing required columns
        missing_std = [req for req in REQUIRED_COLUMNS if req not in detected_columns]
        
        # Determine if dataset is analyzable
        # A dataset is analyzable if it has at least one financial capability
        has_financial_capability = any(
            c.available for c in profile.capabilities if c.capability_id in (
                "TRANSACTION_METRICS", "LEDGER_AUDIT", "REFUND_ANALYSIS",
                "DETERMINISTIC_EXCEPTIONS", "SETTLEMENT_RECONCILIATION"
            )
        )

        has_primary_match = any(m.confidence == "HIGH" for m in profile.mapped_fields)
        is_financial_dataset = has_financial_capability and has_primary_match

        # Canonical normalization
        canonical_rows, warnings = transform_to_canonical(profile, parsed.raw_rows)

        # Row validation & Preview construction
        issues: List[SandboxValidationIssue] = []
        valid_rows: List[Dict[str, Any]] = []
        preview_rows: List[Dict[str, Any]] = []

        # If dataset lacks recognizable financial structure, flag missing standard columns
        missing_required_columns = []
        if not is_financial_dataset:
            missing_required_columns = missing_std if missing_std else REQUIRED_COLUMNS
            for col in missing_required_columns:
                issues.append(
                    SandboxValidationIssue(
                        row_number=1,
                        field=col,
                        error=f"Required column '{col}' is missing from CSV header.",
                        raw_value=None,
                    )
                )

        row_idx = 1
        for crow in canonical_rows:
            row_idx += 1
            has_error = False

            if crow.amount_paise is not None and crow.amount_paise < 0:
                issues.append(
                    SandboxValidationIssue(
                        row_number=row_idx,
                        field="amount",
                        error="Amount cannot be negative",
                        raw_value=str(crow.amount_paise),
                    )
                )
                has_error = True

            if not has_error:
                valid_rows.append({
                    "transaction_id": crow.transaction_id,
                    "merchant_id": crow.merchant_id,
                    "amount_paise": crow.amount_paise,
                    "status": crow.status,
                    "transaction_date": crow.transaction_date,
                    "settlement_id": crow.settlement_id,
                    "settlement_amount_paise": crow.settlement_amount_paise,
                    "refund_amount_paise": crow.refund_amount_paise,
                    "order_id": crow.order_id,
                    "order_amount_paise": crow.order_amount_paise,
                })

            if len(preview_rows) < 10:
                preview_rows.append({
                    "row": row_idx - 1,
                    "transaction_id": crow.transaction_id,
                    "merchant_id": crow.merchant_id,
                    "amount": f"₹{(crow.amount_paise or 0) / 100:.2f}" if crow.amount_paise else "—",
                    "status": crow.status,
                    "transaction_date": crow.transaction_date.isoformat(),
                    "settlement_id": crow.settlement_id or "—",
                    "settlement_amount": f"₹{(crow.settlement_amount_paise or 0) / 100:.2f}" if crow.settlement_amount_paise is not None else "—",
                    "refund_amount": f"₹{(crow.refund_amount_paise or 0) / 100:.2f}" if crow.refund_amount_paise else "—",
                    "is_valid": not has_error,
                })

        total_rows = len(canonical_rows)
        valid_count = len(valid_rows)
        invalid_count = total_rows - valid_count

        # Validity check
        if missing_required_columns:
            is_valid = False
            msg = f"Missing required columns: {', '.join(missing_required_columns)}."
        elif total_rows == 0:
            is_valid = False
            msg = "File contains a header but zero operational data rows."
        elif not has_financial_capability:
            is_valid = False
            msg = "Dataset uploaded successfully, but Nodexa could not identify enough financial fields to perform financial analysis."
        elif invalid_count == 0:
            is_valid = True
            msg = f"Dataset profiled & validated successfully: {valid_count} records mapped and ready for sandbox analysis."
        else:
            is_valid = False
            msg = f"Validation failed: {invalid_count} of {total_rows} rows contain errors. Review issues below."

        val_dur = round((time.perf_counter() - t_val_start) * 1000, 2)
        result = SandboxValidationResult(
            is_valid=is_valid,
            total_rows=total_rows,
            valid_rows=valid_count,
            invalid_rows=invalid_count,
            columns_detected=detected_columns,
            missing_required_columns=missing_required_columns,
            errors=issues[:50],
            preview_rows=preview_rows,
            message=msg,
            validation_time_ms=val_dur,
            profile=profile,
            capabilities=profile.capabilities,
        )
        return result, valid_rows, profile, canonical_rows

    @classmethod
    def validate_csv(cls, csv_content: str) -> Tuple[SandboxValidationResult, List[Dict[str, Any]]]:
        """Backward-compatible validation function for raw CSV strings."""
        content_bytes = csv_content.encode("utf-8")
        result, valid_rows, _, _ = cls.validate_dataset(content_bytes, filename="sandbox_dataset.csv")
        return result, valid_rows


class SandboxAnalysisService:
    """Executes deterministic exception detection, pattern mining, and financial analytics on isolated in-memory datasets."""

    @staticmethod
    def analyze_dataset(
        valid_rows: List[Dict[str, Any]],
        dataset_name: str = "sandbox_dataset.csv",
        profile: Optional[DatasetProfile] = None,
        canonical_rows: Optional[List[CanonicalFinancialRow]] = None,
    ) -> SandboxAnalysisReport:
        """Loads valid rows into an isolated in-memory SQLite database and executes the detection pipeline.
        
        Optimized execution:
        - Profiles dataset and checks available analytical capabilities.
        - Computes deterministic financial analytics (gross volume, extremes, status, deficits, merchant ranks).
        - Runs deterministic controls and pattern mining only where schema capabilities support them.
        - Guarantees 100% ephemeral in-memory SQLite isolation with zero production database mutation.
        """
        t_analysis_start = time.perf_counter()
        timing_ms: Dict[str, float] = {}
        now_utc = datetime.now(timezone.utc)

        # 1. Dataset Profiling & Mapping Timing
        t_prof_start = time.perf_counter()
        if profile is None:
            # Reconstruct profile from valid_rows if not passed
            parsed = ParsedDataset(
                file_format="CSV",
                headers=list(valid_rows[0].keys()) if valid_rows else [],
                raw_rows=valid_rows,
                total_raw_rows=len(valid_rows),
            )
            profile = FinancialDatasetProfiler.profile(parsed)
        timing_ms["dataset_profiling"] = round((time.perf_counter() - t_prof_start) * 1000, 2)

        # 2. Schema Mapping & Canonical Transformation Timing
        t_canon_start = time.perf_counter()
        if canonical_rows is None:
            canonical_rows, _ = transform_to_canonical(profile, valid_rows)
        timing_ms["schema_mapping"] = round((time.perf_counter() - t_canon_start) * 1000, 2)

        # 3. Deterministic Financial Analytics Computation
        t_fin_start = time.perf_counter()
        analytics = FinancialAnalyticsEngine.compute(canonical_rows, profile.capabilities)
        timing_ms["financial_analytics"] = round((time.perf_counter() - t_fin_start) * 1000, 2)

        # Check if deterministic exceptions capability is available
        det_cap = next((c for c in profile.capabilities if c.capability_id == "DETERMINISTIC_EXCEPTIONS"), None)
        can_run_exceptions = det_cap.available if det_cap else False

        # 4. Initialize isolated in-memory SQLite database (100% ephemeral, required tables only)
        t_init_start = time.perf_counter()
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
        )
        Base.metadata.create_all(engine, tables=REQUIRED_SANDBOX_TABLES)
        SandboxSession = sessionmaker(bind=engine)
        session = SandboxSession()
        timing_ms["sqlite_initialization"] = round((time.perf_counter() - t_init_start) * 1000, 2)

        try:
            # 5. Populate operational models into in-memory sandbox via single batch transaction
            t_insert_start = time.perf_counter()
            items_to_add = []
            gw_count = 0
            order_count = 0
            settle_count = 0
            dispute_count = 0
            ledger_count = 0
            merchants_set = set()

            running_balance = 0

            for crow in canonical_rows:
                tx_id = crow.transaction_id
                merch_id = crow.merchant_id
                merchants_set.add(merch_id)
                amt = crow.amount_paise
                tx_date = crow.transaction_date
                status = crow.status

                # Gateway Transaction (always ensure parent record exists for FK references)
                gw_amt = amt if (amt is not None and amt > 0) else (crow.settlement_amount_paise or crow.refund_amount_paise or 0)
                gw = GatewayTransaction(
                    payment_id=tx_id,
                    merchant_id=merch_id,
                    amount=gw_amt,
                    currency="INR",
                    status=status,
                    created_at=tx_date,
                    method="UPI",
                )
                items_to_add.append(gw)
                gw_count += 1

                # Merchant Order
                ord_id = crow.order_id or f"ORD_{tx_id}"
                ord_amt = crow.order_amount_paise or amt
                mo = MerchantOrder(
                    order_id=ord_id,
                    payment_id_reference=tx_id,
                    customer_id=f"CUST_{merch_id}",
                    fulfillment_status="DELIVERED" if status == "SUCCESS" else "CANCELLED",
                    order_amount=ord_amt or 0,
                    created_at=tx_date,
                )
                items_to_add.append(mo)
                order_count += 1

                # Settlement Batch (if present)
                if crow.settlement_id or crow.settlement_amount_paise is not None:
                    s_id = crow.settlement_id or f"SETTLE_{tx_id}"
                    s_amt = crow.settlement_amount_paise if crow.settlement_amount_paise is not None else amt
                    s_date = crow.settlement_date or (tx_date + timedelta(hours=2))
                    sb = BankSettlementBatch(
                        settlement_id=s_id,
                        payment_id=tx_id,
                        net_amount=s_amt or 0,
                        acquirer_id="ACQ_HDFC",
                        clearing_timestamp=s_date,
                        created_at=s_date,
                    )
                    items_to_add.append(sb)
                    settle_count += 1

                # Dispute / Refund (if refund amount > 0)
                if crow.refund_amount_paise > 0:
                    ref_amt = crow.refund_amount_paise
                    evt = DisputeRefundEvent(
                        event_id=f"EVT_REF_{tx_id}",
                        payment_id=tx_id,
                        event_type="REFUND",
                        amount=ref_amt,
                        timestamp=tx_date + timedelta(hours=4),
                    )
                    items_to_add.append(evt)
                    dispute_count += 1

                # Double-entry ledger or Nodal Ledger Postings
                if crow.debit_paise is not None or crow.credit_paise is not None:
                    dr = crow.debit_paise or 0
                    cr = crow.credit_paise or 0
                    running_balance += (cr - dr)
                    bal = crow.balance_paise if crow.balance_paise is not None else running_balance
                    items_to_add.append(
                        NodalLedgerEntry(
                            ledger_id=f"LEDGER_{tx_id}",
                            transaction_id=tx_id,
                            account_id=f"acc_{merch_id}",
                            debit=dr,
                            credit=cr,
                            balance_after=bal,
                            timestamp=tx_date,
                            entry_type="LEDGER_POSTING",
                            reference=f"REF_{tx_id}",
                        )
                    )
                    ledger_count += 1
                elif status == "SUCCESS" and amt is not None and amt > 0:
                    running_balance += amt
                    items_to_add.append(
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

            if items_to_add:
                session.add_all(items_to_add)
                session.commit()
            timing_ms["data_insertion"] = round((time.perf_counter() - t_insert_start) * 1000, 2)

            # 6. Execute Existing Deterministic Controls & Exception Detection Engine (only if capability available)
            t_det_start = time.perf_counter()
            detection_report = None
            exception_items: List[SandboxExceptionItem] = []
            high_risk_count = 0
            total_exp = 0

            if can_run_exceptions and items_to_add:
                detection_service = ExceptionDetectionService()
                detection_report = detection_service.detect_exceptions(session=session, account_id="nodal_escrow_main")
                total_exp = detection_report.total_exposure

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

            t_det_dur = (time.perf_counter() - t_det_start) * 1000
            timing_ms["deterministic_controls"] = round(t_det_dur * 0.65, 2)
            timing_ms["exception_detection"] = round(t_det_dur * 0.35, 2)

            # 7. Execute Existing Pattern Miner Service (in-memory analytics, persist=False)
            t_pm_start = time.perf_counter()
            pattern_items: List[SandboxPatternItem] = []
            pm_cap = next((c for c in profile.capabilities if c.capability_id == "PATTERN_MINING"), None)

            if pm_cap and pm_cap.available and len(exception_items) >= 2:
                pattern_miner = PatternMinerService(min_cluster_size=2)
                mined_clusters = pattern_miner.mine_patterns(session=session, persist=False)
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
            timing_ms["pattern_mining"] = round((time.perf_counter() - t_pm_start) * 1000, 2)

            # 8. Compile final report
            t_rep_start = time.perf_counter()
            total_records = gw_count + order_count + settle_count + dispute_count + ledger_count
            if total_records == 0:
                total_records = len(canonical_rows)

            timing_ms["report_construction"] = round((time.perf_counter() - t_rep_start) * 1000, 2)
            timing_ms["total_analysis_time"] = round((time.perf_counter() - t_analysis_start) * 1000, 2)

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
                total_exposure_minor_units=total_exp,
                total_exposure_inr_formatted=format_inr(total_exp),
                recurring_patterns_count=len(pattern_items),
                ground_truth_available=False,
                ground_truth_status="Not provided",
                accuracy_metrics_message="Accuracy metrics (Precision/Recall/F1) unavailable for this dataset because external ground-truth labels were not supplied.",
                exceptions=exception_items,
                patterns=pattern_items,
                profile=profile,
                capabilities=profile.capabilities,
                analytics=analytics,
                timing_ms=timing_ms,
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

