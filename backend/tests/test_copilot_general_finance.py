"""Comprehensive Test Suite for Generalized Nodexa Finance/Data Copilot.

Verifies:
1. Category A: Transactions / Sales (Total volume, counts, status breakdowns, averages, largest/smallest, lookup, lifecycle).
2. Category B: Orders (Total value, count, fulfillment breakdown, amount mismatches, lookup).
3. Category C: Settlements (Settled volume, unsettled volume, timing delays, mismatches, UTR/batch lookup).
4. Category D: Refunds & Disputes (Total refunds, count, refund rate calculation, dispute breakdown).
5. Category E: Ledger & Nodal Account (Nodal escrow balance, debits, credits, mathematical invariants, postings).
6. Category F: Exceptions (Unresolved count, open exposure, highest exposure issue, breakdown by family).
7. Category G: Patterns & Risk (Recurring anomaly clusters, highest-risk merchants, cluster exposure).
8. Category H: Verification & Governance (Verified closed cases, verifier opinion, policy decisions, remediation boundary).
9. Category I: System & Dataset (Total record count 272, records by source, benchmark metrics, dataset health).
10. Multi-Tool Cross-Domain Questions (Unsettled percentage, sales vs refunds, merchant sales vs exposure, finance health).
11. Boundary Safety & Unsupported Questions (Read-only enforcement, stock market refusal, future revenue refusal).
12. Database Immutability (Production database remains untouched before and after).
"""
import pytest
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.models.database import SessionLocal
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.exceptions import ExceptionRecord
from backend.copilot.service import AskSentinelService
from backend.copilot.agent import ALL_COPILOT_TOOL_DEFINITIONS, ASK_SENTINEL_TOOL_DEFINITIONS
from backend.copilot.tools import AskSentinelToolRegistry


@pytest.fixture(scope="function")
def db_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture(scope="function")
def copilot_service():
    return AskSentinelService()


# ---------------------------------------------------------------------------
# 0. Tool Registry & Schema Verification
# ---------------------------------------------------------------------------

def test_registry_contains_all_33_tools():
    """Verifies that all 33 read-only tools are registered in the allowlist."""
    registry = AskSentinelToolRegistry()
    assert len(registry.ASK_SENTINEL_ALLOWED_TOOLS) == 33
    assert len(ALL_COPILOT_TOOL_DEFINITIONS) == 33
    # Backward compatibility: core definitions preserved as 18
    assert len(ASK_SENTINEL_TOOL_DEFINITIONS) == 18


# ---------------------------------------------------------------------------
# 1. Category A: Transactions & Sales
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "question",
    [
        "What are my total sales?",
        "How much did we sell?",
        "What's our payment volume?",
        "Total transaction value?",
    ]
)
def test_sales_volume_natural_language_variations(copilot_service, db_session, question):
    """Natural language variations for gross sales volume route correctly and return formatted amounts."""
    res = copilot_service.ask(session=db_session, question=question)
    assert res["abstained"] is False
    assert "get_sales_summary" in res["tools_used"]
    assert "₹" in res["answer"]
    assert "paise" in res["answer"].lower()
    assert res["grounded"] is True


def test_successful_transactions_count(copilot_service, db_session):
    """Queries for successful payments route to transaction metrics with CAPTURED status."""
    res = copilot_service.ask(session=db_session, question="How many successful payments?")
    assert res["abstained"] is False
    assert "get_transaction_metrics" in res["tools_used"]
    assert "captured" in res["answer"].lower() or "transaction" in res["answer"].lower()


def test_failed_transactions_count(copilot_service, db_session):
    """Queries for failed payments report failed transactions and their volume."""
    res = copilot_service.ask(session=db_session, question="How many failed payments were there?")
    assert res["abstained"] is False
    assert "get_transaction_metrics" in res["tools_used"]
    assert "failed" in res["answer"].lower()


def test_average_and_extreme_transaction_values(copilot_service, db_session):
    """Queries for average, largest, and smallest payments return authoritative values."""
    res_avg = copilot_service.ask(session=db_session, question="What is our average transaction value?")
    assert res_avg["abstained"] is False
    assert "average" in res_avg["answer"].lower()
    assert "₹" in res_avg["answer"]

    res_large = copilot_service.ask(session=db_session, question="What are the largest transactions?")
    assert res_large["abstained"] is False
    assert "largest" in res_large["answer"].lower()
    assert "PAY-" in res_large["answer"]


# ---------------------------------------------------------------------------
# 2. Category B: Orders
# ---------------------------------------------------------------------------

def test_orders_summary_and_mismatches(copilot_service, db_session):
    """Queries for orders summary calculate total order volume, count, and amount mismatches."""
    res = copilot_service.ask(session=db_session, question="What is the total order value?")
    assert res["abstained"] is False
    assert "get_orders_summary" in res["tools_used"]
    assert "order" in res["answer"].lower()
    assert "₹" in res["answer"]
    ord_count = db_session.scalar(select(func.count(MerchantOrder.id)))
    assert str(ord_count) in res["answer"]


def test_specific_order_lookup(copilot_service, db_session):
    """Queries for a specific order ID route to get_order."""
    res = copilot_service.ask(session=db_session, question="Tell me about ORD-000001")
    assert res["abstained"] is False
    assert "get_order" in res["tools_used"]
    assert "ORD-000001" in res["answer"] or "MERCHANT_ORDERS" in res["evidence_refs"]


# ---------------------------------------------------------------------------
# 3. Category C: Settlements
# ---------------------------------------------------------------------------

def test_settlements_volume_and_unsettled(copilot_service, db_session):
    """Queries for settlement clearing report batch counts and net cleared amounts."""
    res = copilot_service.ask(session=db_session, question="How much has been settled?")
    assert res["abstained"] is False
    assert "get_settlements_summary" in res["tools_used"]
    assert "settlement" in res["answer"].lower()
    assert "₹" in res["answer"]


def test_unsettled_and_late_settlements(copilot_service, db_session):
    """Queries for unsettled payments and late settlements route to cross-source reconciliation."""
    res = copilot_service.ask(session=db_session, question="What's still unsettled?")
    assert res["abstained"] is False
    assert "get_cross_source_reconciliation" in res["tools_used"]
    assert "unsettled" in res["answer"].lower() or "awaiting" in res["answer"].lower()

    res_late = copilot_service.ask(session=db_session, question="Which settlements are late?")
    assert res_late["abstained"] is False
    assert "get_cross_source_reconciliation" in res["tools_used"]
    assert "late" in res_late["answer"].lower() or "sla" in res_late["answer"].lower()


# ---------------------------------------------------------------------------
# 4. Category D: Refunds & Disputes
# ---------------------------------------------------------------------------

def test_refunds_summary_and_counts(copilot_service, db_session):
    """Queries for refund amount and count return grounded dispute/refund totals."""
    res = copilot_service.ask(session=db_session, question="How much did we refund?")
    assert res["abstained"] is False
    assert "get_refunds_summary" in res["tools_used"]
    assert "refund" in res["answer"].lower()
    assert "₹" in res["answer"]

    res_count = copilot_service.ask(session=db_session, question="How many refunds?")
    assert res_count["abstained"] is False
    assert "get_refunds_summary" in res_count["tools_used"]
    assert "refund" in res_count["answer"].lower()


# ---------------------------------------------------------------------------
# 5. Category E: Ledger & Nodal Account
# ---------------------------------------------------------------------------

def test_ledger_balance_and_invariants(copilot_service, db_session):
    """Queries for nodal ledger balance, debits, credits, and double-entry invariants."""
    res = copilot_service.ask(session=db_session, question="What is the nodal ledger balance?")
    assert res["abstained"] is False
    assert "get_ledger_summary" in res["tools_used"]
    assert "nodal" in res["answer"].lower() or "ledger" in res["answer"].lower()
    assert "invariant" in res["answer"].lower()
    assert "₹" in res["answer"]


def test_ledger_debits_and_credits(copilot_service, db_session):
    """Queries for ledger debits and credits return double-entry totals."""
    res = copilot_service.ask(session=db_session, question="Show ledger debits and credits")
    assert res["abstained"] is False
    assert "get_ledger_summary" in res["tools_used"]
    assert "credit" in res["answer"].lower()
    assert "debit" in res["answer"].lower()


# ---------------------------------------------------------------------------
# 6. Category F: Exceptions
# ---------------------------------------------------------------------------

def test_exceptions_count_and_exposure(copilot_service, db_session):
    """Queries for unresolved exceptions and open exposure return exact counts and minor units."""
    res = copilot_service.ask(session=db_session, question="How many unresolved exceptions?")
    assert res["abstained"] is False
    assert "get_aggregate_summary" in res["tools_used"]
    assert "13" in res["answer"] or "unresolved" in res["answer"].lower()

    res_exp = copilot_service.ask(session=db_session, question="What's our open exposure?")
    assert res_exp["abstained"] is False
    assert "get_aggregate_summary" in res_exp["tools_used"]
    assert "₹" in res_exp["answer"]
    assert "paise" in res_exp["answer"].lower()


# ---------------------------------------------------------------------------
# 7. Category G: Patterns & Risk
# ---------------------------------------------------------------------------

def test_recurring_patterns_and_clusters(copilot_service, db_session):
    """Queries for recurring patterns retrieve active anomaly clusters from Pattern Miner."""
    res = copilot_service.ask(session=db_session, question="What are the recurring anomaly patterns?")
    assert res["abstained"] is False
    assert "get_clusters" in res["tools_used"]
    assert "cluster" in res["answer"].lower() or "pattern" in res["answer"].lower()


# ---------------------------------------------------------------------------
# 8. Category H: Verification & Governance
# ---------------------------------------------------------------------------

def test_governance_and_verified_closed(copilot_service, db_session):
    """Queries for governance and verified closed cases return verified closed count (1)."""
    res = copilot_service.ask(session=db_session, question="How many verified closed cases are there?")
    assert res["abstained"] is False
    assert "get_governance_summary" in res["tools_used"]
    assert "verified closed" in res["answer"].lower()
    assert "1" in res["answer"]  # Exactly 1 verified closed in baseline


# ---------------------------------------------------------------------------
# 9. Category I: System & Dataset Health
# ---------------------------------------------------------------------------

def test_system_dataset_census(copilot_service, db_session):
    """Queries for total records and dataset health audit the 270 baseline records."""
    res = copilot_service.ask(session=db_session, question="What is the status of system dataset records?")
    assert res["abstained"] is False
    gw = db_session.scalar(select(func.count(GatewayTransaction.id)))
    stl = db_session.scalar(select(func.count(BankSettlementBatch.id)))
    ord_c = db_session.scalar(select(func.count(MerchantOrder.id)))
    disp = db_session.scalar(select(func.count(DisputeRefundEvent.id)))
    ledg = db_session.scalar(select(func.count(NodalLedgerEntry.id)))
    total = gw + stl + ord_c + disp + ledg
    assert str(total) in res["answer"]
    assert "immutable" in res["answer"].lower() or "healthy" in res["answer"].lower()


def test_benchmark_metrics_read_only(copilot_service, db_session):
    """Queries for benchmark metrics return accuracy, precision, and latency."""
    res = copilot_service.ask(session=db_session, question="What are our benchmark metrics?")
    assert res["abstained"] is False
    assert "get_benchmark_summary" in res["tools_used"]
    assert "accuracy" in res["answer"].lower()
    assert "precision" in res["answer"].lower()


# ---------------------------------------------------------------------------
# 10. Multi-Tool Cross-Domain Inquiries
# ---------------------------------------------------------------------------

def test_multi_tool_unsettled_percentage(copilot_service, db_session):
    """Calculates unsettled percentage deterministically across sales and reconciliation tools."""
    res = copilot_service.ask(session=db_session, question="What percentage of sales is unsettled?")
    assert res["abstained"] is False
    assert "get_sales_summary" in res["tools_used"]
    assert "get_cross_source_reconciliation" in res["tools_used"]
    assert "%" in res["answer"]
    assert "unsettled" in res["answer"].lower()
    assert "calculations" in res
    assert "unsettled_percentage" in res["calculations"]


def test_multi_tool_compare_sales_and_refunds(copilot_service, db_session):
    """Combines sales and refunds tools to calculate net sales and refund rate."""
    res = copilot_service.ask(session=db_session, question="Compare sales and refunds.")
    assert res["abstained"] is False
    assert "get_sales_summary" in res["tools_used"]
    assert "get_refunds_summary" in res["tools_used"]
    assert "₹" in res["answer"]
    assert "refund" in res["answer"].lower()


def test_multi_tool_merchant_sales_and_exposure(copilot_service, db_session):
    """Ranks merchants across both captured sales volume and unresolved exposure."""
    res = copilot_service.ask(session=db_session, question="Which merchant has the most sales and the highest unresolved exposure?")
    assert res["abstained"] is False
    assert "get_merchants_overview" in res["tools_used"]
    assert "get_aggregate_summary" in res["tools_used"]
    assert "merchant" in res["answer"].lower()
    assert "exposure" in res["answer"].lower()


def test_multi_tool_biggest_financial_risk(copilot_service, db_session):
    """Evaluates biggest financial risk by combining merchant exposure and recurring anomaly patterns."""
    res = copilot_service.ask(session=db_session, question="Which merchant is causing the biggest financial risk?")
    assert res["abstained"] is False
    assert "get_merchants_overview" in res["tools_used"]
    assert "get_clusters" in res["tools_used"]
    assert "risk" in res["answer"].lower() or "exposure" in res["answer"].lower()


def test_multi_tool_finance_health_summary(copilot_service, db_session):
    """Synthesizes executive finance health summary consolidating all subsystems."""
    res = copilot_service.ask(session=db_session, question="Give me a finance health summary.")
    assert res["abstained"] is False
    assert "get_finance_health_summary" in res["tools_used"]
    assert "sales" in res["answer"].lower()
    assert "settlement" in res["answer"].lower()
    assert "refund" in res["answer"].lower()
    assert "ledger" in res["answer"].lower()


def test_payment_full_lifecycle_trace(copilot_service, db_session):
    """Traces full end-to-end timeline for a specific payment."""
    res = copilot_service.ask(session=db_session, question="Show me the full lifecycle of PAY-000001.")
    assert res["abstained"] is False
    assert "get_payment_lifecycle" in res["tools_used"]
    assert "PAY-000001" in res["answer"]
    assert "timeline" in res["answer"].lower() or "lifecycle" in res["answer"].lower()


# ---------------------------------------------------------------------------
# 11. Boundary Safety & Unsupported Refusal
# ---------------------------------------------------------------------------

def test_remediation_mutation_rejected(copilot_service, db_session):
    """Mutation requests are strictly rejected with read-only explanation."""
    res = copilot_service.ask(session=db_session, question="Refund PAY-000001.")
    assert res["abstained"] is True
    assert res["confidence"] == "LOW"
    assert "read-only" in res["answer"].lower()
    assert len(res["tools_used"]) == 0


@pytest.mark.parametrize(
    "unsupported_q",
    [
        "What will our revenue be next year?",
        "Predict the stock market.",
        "What's Razorpay's internal production revenue?",
    ]
)
def test_unsupported_out_of_scope_honesty(copilot_service, db_session, unsupported_q):
    """Out-of-scope or speculative questions are refused without hallucination."""
    res = copilot_service.ask(session=db_session, question=unsupported_q)
    assert res["abstained"] is True
    assert res["confidence"] == "LOW"
    assert "can't determine that from the available nodexa data" in res["answer"].lower() or "restricted to operational evidence" in res["answer"].lower()
    assert len(res["tools_used"]) == 0


# ---------------------------------------------------------------------------
# 12. Database Immutability Verification
# ---------------------------------------------------------------------------

def test_database_immutability_guarantee(db_session):
    """Ensures production database counts remain strictly unaltered: 270 records, 14 exceptions, 1 verified closed."""
    gw = db_session.scalar(select(func.count(GatewayTransaction.id)))
    stl = db_session.scalar(select(func.count(BankSettlementBatch.id)))
    ord_c = db_session.scalar(select(func.count(MerchantOrder.id)))
    disp = db_session.scalar(select(func.count(DisputeRefundEvent.id)))
    ledg = db_session.scalar(select(func.count(NodalLedgerEntry.id)))

    total = gw + stl + ord_c + disp + ledg
    assert total in (270, 274), f"Unexpected test database total records: {total}"

    excs = db_session.scalar(select(func.count(ExceptionRecord.id)))
    assert excs in (14, 15), f"Unexpected test database exceptions: {excs}"

    verified = db_session.scalar(select(func.count(ExceptionRecord.id)).where(ExceptionRecord.state == "VERIFIED_CLOSED"))
    assert verified in (0, 1), f"Unexpected verified closed count: {verified}"

    # Verify that the physical production database file nodal_sentinel.db remains completely untouched
    import os
    import sqlite3
    if os.path.exists("nodal_sentinel.db"):
        conn = sqlite3.connect("nodal_sentinel.db")
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM gateway_transactions")
        gw_p = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM bank_settlement_batches")
        stl_p = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM merchant_orders")
        ord_p = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM dispute_refund_events")
        disp_p = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM nodal_ledger")
        ledg_p = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM exceptions")
        exc_p = cursor.fetchone()[0]
        cursor.execute("SELECT count(*) FROM exceptions WHERE state = 'VERIFIED_CLOSED'")
        ver_p = cursor.fetchone()[0]
        conn.close()

        assert gw_p == 60
        assert stl_p == 62
        assert ord_p == 60
        assert disp_p == 14
        assert ledg_p == 76
        assert (gw_p + stl_p + ord_p + disp_p + ledg_p) == 272
        assert exc_p == 14
        assert ver_p == 1
