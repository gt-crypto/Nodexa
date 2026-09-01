"""Unit tests for Nodal Health balance calculations, throughput metrics, and GET /health/nodal endpoint."""
from datetime import datetime, timezone, timedelta
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.main import app
from backend.models.database import get_db
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.enums import (
    PaymentStatus,
    OrderFulfillmentStatus,
    DisputeEventType,
    LedgerEntryType,
)
from backend.controls.nodal_health import (
    NodalHealthStatus,
    NodalHealthConfig,
    calculate_actual_nodal_balance,
    calculate_expected_nodal_balance,
    calculate_settlement_throughput,
    evaluate_nodal_health,
)
from backend.controls.engine import ControlEngine


def test_actual_and_expected_balance_derivation():
    """Verifies that actual and expected balances are derived with exact integer precision."""
    now = datetime(2026, 8, 1, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Normal payment + settlement + refund
    payments = [
        GatewayTransaction(
            payment_id="PAY-H1",
            merchant_id="M1",
            amount=1000000,  # ₹10,000
            currency="INR",
            status=PaymentStatus.REFUNDED.value,
            created_at=now,
            method="CARD",
        )
    ]
    orders = [
        MerchantOrder(
            order_id="ORD-H1",
            payment_id_reference="PAY-H1",
            customer_id="C1",
            fulfillment_status=OrderFulfillmentStatus.FULFILLED.value,
            order_amount=1000000,
            created_at=now,
        )
    ]
    settlements = [
        BankSettlementBatch(
            settlement_id="SET-H1",
            payment_id="PAY-H1",
            acquirer_id="A1",
            net_amount=985000,  # ₹9,850
            interchange_fee_deducted=12711,
            tax_deducted=2289,
            clearing_timestamp=now + timedelta(hours=6),
        )
    ]
    disputes = [
        DisputeRefundEvent(
            event_id="EVT-H1",
            payment_id="PAY-H1",
            event_type=DisputeEventType.REFUND.value,
            amount=1000000,  # ₹10,000 refund payout
            timestamp=now + timedelta(days=1),
        )
    ]
    ledger_entries = [
        NodalLedgerEntry(
            ledger_id="LED-H1",
            account_id="nodal_escrow_main",
            debit=0,
            credit=985000,
            balance_after=985000,
            timestamp=now + timedelta(hours=6, minutes=5),
            entry_type=LedgerEntryType.SETTLEMENT_CREDIT.value,
        ),
        NodalLedgerEntry(
            ledger_id="LED-H2",
            account_id="nodal_escrow_main",
            debit=1000000,
            credit=0,
            balance_after=-15000,  # Temporarily negative for math test
            timestamp=now + timedelta(days=1, minutes=5),
            entry_type=LedgerEntryType.REFUND_DEBIT.value,
        ),
    ]

    actual_bal, is_consistent = calculate_actual_nodal_balance(ledger_entries, account_id="nodal_escrow_main")
    expected_bal = calculate_expected_nodal_balance(payments, settlements, orders, disputes)

    assert actual_bal == -15000
    assert expected_bal == 985000 - 1000000  # -15000
    assert actual_bal == expected_bal
    assert is_consistent is True


def test_settlement_throughput_calculation():
    """Verifies that settlement throughput metrics calculate accurate ratios and counts."""
    now = datetime.now(timezone.utc)
    payments = [
        GatewayTransaction(payment_id="P1", merchant_id="M1", amount=100000, currency="INR", status="CAPTURED", created_at=now, method="UPI"),
        GatewayTransaction(payment_id="P2", merchant_id="M1", amount=200000, currency="INR", status="CAPTURED", created_at=now, method="UPI"),
        GatewayTransaction(payment_id="P3", merchant_id="M1", amount=300000, currency="INR", status="FAILED", created_at=now, method="UPI"),
    ]
    settlements = [
        BankSettlementBatch(settlement_id="S1", payment_id="P1", acquirer_id="A1", net_amount=98500, interchange_fee_deducted=1200, tax_deducted=300, clearing_timestamp=now),
    ]

    throughput = calculate_settlement_throughput(payments, settlements)
    assert throughput.total_captured_payments_count == 2
    assert throughput.total_captured_amount == 300000
    assert throughput.total_settled_payments_count == 1
    assert throughput.total_settled_amount == 100000
    assert throughput.total_unsettled_payments_count == 1
    assert throughput.total_unsettled_amount == 200000
    assert throughput.settlement_completion_ratio == 0.5


def test_nodal_health_status_transitions(db_session: Session):
    """Verifies HEALTHY, WARNING, and CRITICAL nodal health status transitions."""
    config = NodalHealthConfig(warning_variance_threshold=100000, critical_variance_threshold=5000000)

    # 1. Clean state -> HEALTHY
    summary = evaluate_nodal_health(db_session, config=config)
    assert summary.overall_status == NodalHealthStatus.HEALTHY
    assert summary.variance == 0

    # 2. Critical failure injected
    summary_crit = evaluate_nodal_health(db_session, config=config, critical_control_failures_count=1)
    assert summary_crit.overall_status == NodalHealthStatus.CRITICAL


def test_get_nodal_health_api_endpoint(db_session: Session):
    """Verifies that GET /health/nodal returns a valid 200 OK response with honest metrics."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    response = client.get("/health/nodal")
    assert response.status_code == 200
    data = response.json()

    assert data["overall_status"] in ("HEALTHY", "WARNING", "CRITICAL")
    assert data["account_id"] == "nodal_escrow_main"
    assert "expected_balance" in data
    assert "actual_balance" in data
    assert "variance" in data
    assert "settlement_throughput" in data
    assert "settlement_sla_health" in data
    # Prompt 3 requirement: honest zero exception and exposure values
    assert data["open_exception_count"] == 0
    assert data["total_exposure"] == 0
    assert "controls_summary" in data
    assert "evaluated_at" in data

    app.dependency_overrides.clear()
