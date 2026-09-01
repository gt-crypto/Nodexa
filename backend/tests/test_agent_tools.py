"""Unit tests for agent read-only tools and tool registry guards."""
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy.orm import Session

from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.enums import PaymentStatus, OrderFulfillmentStatus, LedgerEntryType
from backend.models.exceptions import ExceptionRecord
from backend.agent.tools.financial_records import (
    lookup_payment,
    lookup_settlements,
    lookup_disputes,
    lookup_ledger,
)
from backend.agent.tools.control_findings import lookup_control_findings
from backend.agent.tools.exception_details import lookup_exception_details
from backend.agent.tools.evidence import extract_investigation_evidence
from backend.agent.tools.registry import AgentToolRegistry


def test_agent_tools_read_only_lookups(db_session: Session):
    """Verifies that all read-only lookup tools return well-structured data."""
    now = datetime.now(timezone.utc)
    pmt = GatewayTransaction(
        payment_id="PAY-TOOL-1",
        merchant_id="M1",
        amount=1000000,
        currency="INR",
        status=PaymentStatus.CAPTURED.value,
        created_at=now,
        method="CARD",
    )
    order = MerchantOrder(
        order_id="ORD-TOOL-1",
        payment_id_reference="PAY-TOOL-1",
        customer_id="C1",
        fulfillment_status=OrderFulfillmentStatus.FULFILLED.value,
        order_amount=1000000,
        created_at=now,
    )
    settlement = BankSettlementBatch(
        settlement_id="SET-TOOL-1",
        payment_id="PAY-TOOL-1",
        acquirer_id="A1",
        net_amount=985000,
        interchange_fee_deducted=12711,
        tax_deducted=2289,
        clearing_timestamp=now + timedelta(hours=6),
    )
    dispute = DisputeRefundEvent(
        event_id="EVT-TOOL-1",
        payment_id="PAY-TOOL-1",
        event_type="REFUND",
        amount=1000000,
        timestamp=now + timedelta(days=1),
    )
    ledger = NodalLedgerEntry(
        ledger_id="LED-TOOL-1",
        transaction_id="PAY-TOOL-1",
        account_id="nodal_escrow_main",
        debit=0,
        credit=985000,
        balance_after=985000,
        timestamp=now + timedelta(hours=6),
        entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
    )
    exc = ExceptionRecord(
        exception_id="EXC-TOOL-1",
        exception_type="GHOST_SETTLEMENT",
        severity="HIGH",
        state="DETECTED",
        exposure=985000,
        primary_payment_id="PAY-TOOL-1",
        detected_at=now,
        created_at=now,
    )

    db_session.add_all([pmt, order, settlement, dispute, ledger, exc])
    db_session.commit()

    # 1. Lookup Payment
    p_data = lookup_payment(db_session, "PAY-TOOL-1")
    assert p_data is not None
    assert p_data["payment_id"] == "PAY-TOOL-1"
    assert len(p_data["associated_orders"]) == 1

    # 2. Lookup Settlements
    s_data = lookup_settlements(db_session, payment_id="PAY-TOOL-1")
    assert len(s_data) == 1
    assert s_data[0]["settlement_id"] == "SET-TOOL-1"

    # 3. Lookup Disputes
    d_data = lookup_disputes(db_session, "PAY-TOOL-1")
    assert len(d_data) == 1
    assert d_data[0]["event_type"] == "REFUND"

    # 4. Lookup Ledger
    l_data = lookup_ledger(db_session, payment_id="PAY-TOOL-1")
    assert len(l_data) == 1
    assert l_data[0]["credit"] == 985000

    # 5. Lookup Exception Details
    e_data = lookup_exception_details(db_session, "EXC-TOOL-1")
    assert e_data is not None
    assert e_data["exception_id"] == "EXC-TOOL-1"

    # 6. Extract full evidence
    ev_data = extract_investigation_evidence(db_session, "EXC-TOOL-1")
    assert "exception" in ev_data
    assert "payment" in ev_data
    assert len(ev_data["settlements"]) == 1


def test_agent_tool_registry_limits_and_sanitization(db_session: Session):
    """Verifies that tool registry enforces call caps and input sanitization."""
    registry = AgentToolRegistry(max_tool_calls=2)

    res1 = registry.execute_tool("lookup_payment", session=db_session, payment_id="PAY-NONE")
    assert res1["status"] == "success"

    res2 = registry.execute_tool("lookup_payment", session=db_session, payment_id="PAY-NONE")
    assert res2["status"] == "success"

    # 3rd call should hit call limit
    res3 = registry.execute_tool("lookup_payment", session=db_session, payment_id="PAY-NONE")
    assert "error" in res3
    assert "limit" in res3["error"].lower()

    # Invalid tool name
    registry.reset_call_counter()
    res_inv = registry.execute_tool("execute_sql_query", session=db_session)
    assert "error" in res_inv
    assert "not a registered" in res_inv["error"]
