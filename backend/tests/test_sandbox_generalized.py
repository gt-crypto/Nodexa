"""Comprehensive tests for the Generalized Financial Dataset Intelligence Engine.

Validates:
1. Shape A: Nodexa standard schema (backward compatibility)
2. Shape B: Alternative column names (synonyms: txn_id, gross_amt, vendor_code, state)
3. Shape C: Transaction-only minimal schema (no settlement columns)
4. Shape D: Refund / dispute dataset
5. Shape E: Settlement reconciliation dataset
6. Shape F: Ledger audit trail (debit, credit, balance)
7. Extra & unmapped columns preserved
8. Missing optional columns handled with honest capability disclaimers
9. Small dataset (<10 rows, e.g. 8 rows) with sample size notice
10. Non-financial dataset properly rejected with informative error message
11. XLSX and JSON format ingestion
12. Grounded Natural Language Q&A queries
13. ZERO PRODUCTION DATABASE MUTATION: Exact count invariance
"""
import io
import json
import pytest
from openpyxl import Workbook
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from backend.models import (
    GatewayTransaction,
    MerchantOrder,
    BankSettlementBatch,
    DisputeRefundEvent,
    NodalLedgerEntry,
    ExceptionRecord,
)
from backend.sandbox.service import (
    SandboxValidationService,
    SandboxAnalysisService,
    format_inr,
)
from backend.sandbox.qa_engine import SandboxDatasetQAEngine
from backend.sandbox.models import SandboxQueryRequest
from backend.models import get_db


def get_production_record_counts(session) -> dict:
    """Helper to snapshot production database record counts."""
    return {
        "gateway": session.query(GatewayTransaction).count(),
        "orders": session.query(MerchantOrder).count(),
        "settlements": session.query(BankSettlementBatch).count(),
        "disputes": session.query(DisputeRefundEvent).count(),
        "ledger": session.query(NodalLedgerEntry).count(),
        "exceptions": session.query(ExceptionRecord).count(),
    }



# ─────────────────────────────────────────────────────────────────────────────
# 1. Shape A: Nodexa Standard Schema
# ─────────────────────────────────────────────────────────────────────────────
def test_shape_a_standard_nodexa_schema():
    csv_data = (
        "transaction_id,merchant_id,amount,status,transaction_date\n"
        "TXN_001,MERCH_A,1500.50,SUCCESS,2026-03-01T10:00:00Z\n"
        "TXN_002,MERCH_B,2500.00,SUCCESS,2026-03-01T11:00:00Z\n"
        "TXN_003,MERCH_A,500.00,FAILED,2026-03-01T12:00:00Z\n"
    )
    result, valid_rows, profile, canonical_rows = SandboxValidationService.validate_dataset(
        csv_data.encode("utf-8"), filename="nodexa_std.csv"
    )
    assert result.is_valid is True
    assert result.total_rows == 3
    assert result.valid_rows == 3
    assert len(profile.mapped_fields) >= 5

    report = SandboxAnalysisService.analyze_dataset(
        valid_rows=valid_rows,
        dataset_name="nodexa_std.csv",
        profile=profile,
        canonical_rows=canonical_rows,
    )
    assert report.status == "COMPLETED"
    assert report.analytics is not None
    assert report.analytics.total_volume_minor_units == 450050  # 1500.50 + 2500.00 + 500.00 = 4500.50 -> 450050 paise
    assert report.analytics.status_breakdown.get("SUCCESS") == 2
    assert report.analytics.status_breakdown.get("FAILED") == 1


# ─────────────────────────────────────────────────────────────────────────────
# 2. Shape B: Alternative Column Names (Synonyms)
# ─────────────────────────────────────────────────────────────────────────────
def test_shape_b_alternative_column_names():
    csv_data = (
        "txn_id,vendor_code,gross_amt,state,created_at\n"
        "TX_101,VEND_99,999.00,PAID,2026-02-15 09:30:00\n"
        "TX_102,VEND_99,450.00,DECLINED,2026-02-15 10:15:00\n"
        "TX_103,VEND_88,1200.00,SUCCESS,2026-02-15 11:00:00\n"
    )
    result, valid_rows, profile, canonical_rows = SandboxValidationService.validate_dataset(
        csv_data.encode("utf-8"), filename="alt_headers.csv"
    )
    assert result.is_valid is True
    assert result.total_rows == 3
    assert result.valid_rows == 3

    canon_map = {m.canonical_field: m.source_column for m in profile.mapped_fields}
    assert canon_map["transaction_id"] == "txn_id"
    assert canon_map["merchant_id"] == "vendor_code"
    assert canon_map["amount"] == "gross_amt"
    assert canon_map["status"] == "state"
    assert canon_map["transaction_date"] == "created_at"

    report = SandboxAnalysisService.analyze_dataset(
        valid_rows=valid_rows,
        dataset_name="alt_headers.csv",
        profile=profile,
        canonical_rows=canonical_rows,
    )
    assert report.analytics is not None
    assert report.analytics.total_volume_minor_units == 264900  # (999 + 450 + 1200) * 100
    assert report.analytics.status_breakdown.get("SUCCESS") == 2  # PAID and SUCCESS normalize to SUCCESS
    assert report.analytics.status_breakdown.get("FAILED") == 1  # DECLINED normalizes to FAILED


# ─────────────────────────────────────────────────────────────────────────────
# 3. Shape C: Transaction-Only Minimal Schema (No Settlement Columns)
# ─────────────────────────────────────────────────────────────────────────────
def test_shape_c_transaction_only_minimal_schema():
    csv_data = (
        "transaction_id,amount\n"
        "TX_A,100.00\n"
        "TX_B,200.00\n"
    )
    result, valid_rows, profile, canonical_rows = SandboxValidationService.validate_dataset(
        csv_data.encode("utf-8"), filename="minimal_tx.csv"
    )
    assert result.is_valid is True
    assert result.total_rows == 2

    # Verify capability matrix
    caps = {c.capability_id: c.available for c in profile.capabilities}
    assert caps["TRANSACTION_METRICS"] is True
    assert caps["SETTLEMENT_RECONCILIATION"] is False
    assert caps["DETERMINISTIC_EXCEPTIONS"] is False

    report = SandboxAnalysisService.analyze_dataset(
        valid_rows=valid_rows,
        dataset_name="minimal_tx.csv",
        profile=profile,
        canonical_rows=canonical_rows,
    )
    assert report.analytics is not None
    assert report.analytics.total_volume_minor_units == 30000
    # Transparent capability disclosure
    assert any("Settlement reconciliation unavailable" in d for d in report.analytics.unavailable_capabilities)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Shape D: Refund / Dispute Dataset
# ─────────────────────────────────────────────────────────────────────────────
def test_shape_d_refund_dispute_dataset():
    csv_data = (
        "payment_id,refund_amount,chargeback_id,reason\n"
        "PAY_01,500.00,CB_01,Fraudulent\n"
        "PAY_02,300.00,,Customer Return\n"
    )
    result, valid_rows, profile, canonical_rows = SandboxValidationService.validate_dataset(
        csv_data.encode("utf-8"), filename="refunds.csv"
    )
    assert result.is_valid is True
    assert result.total_rows == 2

    caps = {c.capability_id: c.available for c in profile.capabilities}
    assert caps["REFUND_ANALYSIS"] is True

    report = SandboxAnalysisService.analyze_dataset(
        valid_rows=valid_rows,
        dataset_name="refunds.csv",
        profile=profile,
        canonical_rows=canonical_rows,
    )
    assert report.analytics is not None
    assert report.analytics.refund_total_minor_units == 80000  # (500 + 300) * 100


# ─────────────────────────────────────────────────────────────────────────────
# 5. Shape E: Settlement Reconciliation Dataset
# ─────────────────────────────────────────────────────────────────────────────
def test_shape_e_settlement_reconciliation_dataset():
    csv_data = (
        "payout_id,bank_utr,cleared_amt,status,settled_at\n"
        "PO_001,UTR12345,50000.00,SUCCESS,2026-03-01\n"
        "PO_002,UTR12346,75000.00,SUCCESS,2026-03-02\n"
    )
    result, valid_rows, profile, canonical_rows = SandboxValidationService.validate_dataset(
        csv_data.encode("utf-8"), filename="settlements.csv"
    )
    assert result.is_valid is True
    assert result.total_rows == 2

    report = SandboxAnalysisService.analyze_dataset(
        valid_rows=valid_rows,
        dataset_name="settlements.csv",
        profile=profile,
        canonical_rows=canonical_rows,
    )
    assert report.analytics is not None
    assert report.analytics.total_volume_minor_units == 12500000  # 125,000 * 100 paise


# ─────────────────────────────────────────────────────────────────────────────
# 6. Shape F: Ledger Audit Trail Dataset
# ─────────────────────────────────────────────────────────────────────────────
def test_shape_f_ledger_audit_dataset():
    csv_data = (
        "entry_id,account_id,dr,cr,running_bal,posted_at\n"
        "L_1,acc_merchant,1000.00,0.00,9000.00,2026-03-01 12:00:00\n"
        "L_2,acc_merchant,0.00,2500.00,11500.00,2026-03-01 13:00:00\n"
    )
    result, valid_rows, profile, canonical_rows = SandboxValidationService.validate_dataset(
        csv_data.encode("utf-8"), filename="ledger.csv"
    )
    assert result.is_valid is True
    caps = {c.capability_id: c.available for c in profile.capabilities}
    assert caps["LEDGER_AUDIT"] is True


# ─────────────────────────────────────────────────────────────────────────────
# 7. Extra and Unmapped Columns Preserved
# ─────────────────────────────────────────────────────────────────────────────
def test_extra_and_unmapped_columns_preserved():
    csv_data = (
        "transaction_id,amount,custom_tag,device_os,fraud_score\n"
        "TX_EXTRA_1,150.00,PROMO_2026,iOS,0.02\n"
        "TX_EXTRA_2,250.00,VIP_MEMBER,Android,0.15\n"
    )
    result, valid_rows, profile, canonical_rows = SandboxValidationService.validate_dataset(
        csv_data.encode("utf-8"), filename="extras.csv"
    )
    assert result.is_valid is True
    assert "custom_tag" in profile.unmapped_columns
    assert "device_os" in profile.unmapped_columns
    assert "fraud_score" in profile.unmapped_columns
    assert canonical_rows[0].original_row["custom_tag"] == "PROMO_2026"


# ─────────────────────────────────────────────────────────────────────────────
# 8. Small Dataset (<10 rows, e.g. 8 rows) with Sample Size Notice
# ─────────────────────────────────────────────────────────────────────────────
def test_small_8_row_dataset_sample_size_notice():
    rows = ["transaction_id,merchant_id,amount,status,transaction_date"]
    for i in range(1, 9):
        rows.append(f"TXN_SMALL_{i},M_001,{i * 100}.00,SUCCESS,2026-03-01T10:0{i}:00Z")
    csv_data = "\n".join(rows)

    result, valid_rows, profile, canonical_rows = SandboxValidationService.validate_dataset(
        csv_data.encode("utf-8"), filename="small_8_rows.csv"
    )
    assert result.is_valid is True
    assert result.total_rows == 8

    report = SandboxAnalysisService.analyze_dataset(
        valid_rows=valid_rows,
        dataset_name="small_8_rows.csv",
        profile=profile,
        canonical_rows=canonical_rows,
    )
    assert report.analytics is not None
    assert report.analytics.sample_size_notice is not None
    assert "8 records" in report.analytics.sample_size_notice


# ─────────────────────────────────────────────────────────────────────────────
# 9. Non-Financial Dataset Handling (Rejection with Clear Message)
# ─────────────────────────────────────────────────────────────────────────────
def test_non_financial_dataset_rejection():
    csv_data = (
        "id,name,value\n"
        "1,Alice,blue\n"
        "2,Bob,green\n"
    )
    result, valid_rows, profile, canonical_rows = SandboxValidationService.validate_dataset(
        csv_data.encode("utf-8"), filename="names.csv"
    )
    assert result.is_valid is False
    assert "missing" in result.message.lower() or "not identify enough financial fields" in result.message.lower()


# ─────────────────────────────────────────────────────────────────────────────
# 10. XLSX Multi-Format Ingestion
# ─────────────────────────────────────────────────────────────────────────────
def test_xlsx_format_ingestion():
    wb = Workbook()
    ws = wb.active
    ws.title = "Financials"
    ws.append(["transaction_id", "merchant_id", "amount", "status", "transaction_date"])
    ws.append(["XLSX_01", "MERCH_EXCEL", 1250.75, "SUCCESS", "2026-03-05 10:00:00"])
    ws.append(["XLSX_02", "MERCH_EXCEL", 840.25, "SUCCESS", "2026-03-05 11:00:00"])

    buf = io.BytesIO()
    wb.save(buf)
    xlsx_bytes = buf.getvalue()

    result, valid_rows, profile, canonical_rows = SandboxValidationService.validate_dataset(
        xlsx_bytes, filename="workbook.xlsx"
    )
    assert result.is_valid is True
    assert profile.file_format in ("XLSX", "EXCEL (XLSX)")
    assert result.total_rows == 2

    report = SandboxAnalysisService.analyze_dataset(
        valid_rows=valid_rows,
        dataset_name="workbook.xlsx",
        profile=profile,
        canonical_rows=canonical_rows,
    )
    assert report.analytics is not None
    assert report.analytics.total_volume_minor_units == 209100  # 1250.75 + 840.25 = 2091.00 -> 209100 paise


# ─────────────────────────────────────────────────────────────────────────────
# 11. JSON Multi-Format Ingestion
# ─────────────────────────────────────────────────────────────────────────────
def test_json_format_ingestion():
    json_data = json.dumps([
        {"txn_id": "J_01", "merchant": "JSON_VENDOR", "amount": "3500.00", "status": "SUCCESS"},
        {"txn_id": "J_02", "merchant": "JSON_VENDOR", "amount": "1500.00", "status": "FAILED"},
    ])
    result, valid_rows, profile, canonical_rows = SandboxValidationService.validate_dataset(
        json_data.encode("utf-8"), filename="transactions.json"
    )
    assert result.is_valid is True
    assert profile.file_format == "JSON"
    assert result.total_rows == 2

    report = SandboxAnalysisService.analyze_dataset(
        valid_rows=valid_rows,
        dataset_name="transactions.json",
        profile=profile,
        canonical_rows=canonical_rows,
    )
    assert report.analytics is not None
    assert report.analytics.total_volume_minor_units == 500000


# ─────────────────────────────────────────────────────────────────────────────
# 12. Grounded Dataset Q&A Engine Queries
# ─────────────────────────────────────────────────────────────────────────────
def test_grounded_qa_queries():
    csv_data = (
        "transaction_id,merchant_id,amount,status,transaction_date\n"
        "TXN_A1,MERCH_MEGA,5000.00,SUCCESS,2026-03-01T10:00:00Z\n"
        "TXN_A2,MERCH_MEGA,10000.00,SUCCESS,2026-03-01T11:00:00Z\n"
        "TXN_A3,MERCH_MINI,500.00,FAILED,2026-03-01T12:00:00Z\n"
    )
    result, valid_rows, profile, canonical_rows = SandboxValidationService.validate_dataset(
        csv_data.encode("utf-8"), filename="qa_dataset.csv"
    )
    report = SandboxAnalysisService.analyze_dataset(
        valid_rows=valid_rows,
        dataset_name="qa_dataset.csv",
        profile=profile,
        canonical_rows=canonical_rows,
    )

    # Query 1: Total Volume
    resp_vol = SandboxDatasetQAEngine.answer_query("What is the total volume?", report)
    assert "₹15,500.00" in resp_vol.answer
    assert resp_vol.confidence == "HIGH"
    assert "TRANSACTION_METRICS" in resp_vol.capabilities_used

    # Query 2: Largest Transaction
    resp_max = SandboxDatasetQAEngine.answer_query("What is the largest transaction?", report)
    assert "₹10,000.00" in resp_max.answer

    # Query 3: Top Merchant
    resp_top = SandboxDatasetQAEngine.answer_query("Who is the top merchant by volume?", report)
    assert "MERCH_MEGA" in resp_top.answer

    # Query 4: Failure Rate
    resp_fail = SandboxDatasetQAEngine.answer_query("What is the failure rate?", report)
    assert "1 failed transaction" in resp_fail.answer
    assert "33.3%" in resp_fail.answer


# ─────────────────────────────────────────────────────────────────────────────
# 13. ZERO PRODUCTION DATABASE MUTATION GUARANTEE
# ─────────────────────────────────────────────────────────────────────────────
def test_zero_production_database_mutation():
    """Validates that running generalized sandbox validation & analysis NEVER mutates the production database."""
    session = next(get_db())

    try:
        # Snapshot before
        counts_before = get_production_record_counts(session)

        # Run multiple sandbox analyses with different formats & schemas
        datasets = [
            ("transaction_id,amount,status\nT_P1,1000,SUCCESS\nT_P2,2000,FAILED", "csv1.csv"),
            ("txn_id,vendor_id,gross_amt\nT_V1,V_1,5000\nT_V2,V_2,12000", "csv2.csv"),
            (json.dumps([{"transaction_id": "TJ1", "amount": 999}]), "test.json"),
        ]

        for content, name in datasets:
            res, valid_rows, prof, can_rows = SandboxValidationService.validate_dataset(
                content.encode("utf-8"), filename=name
            )
            if res.is_valid:
                rep = SandboxAnalysisService.analyze_dataset(
                    valid_rows=valid_rows,
                    dataset_name=name,
                    profile=prof,
                    canonical_rows=can_rows,
                )
                assert rep.production_database_modified is False

        # Snapshot after
        counts_after = get_production_record_counts(session)

        # Assert 100% exact equality across all tables
        assert counts_after == counts_before, (
            f"Production database was mutated during sandbox run! Before: {counts_before}, After: {counts_after}"
        )
    finally:
        session.close()

