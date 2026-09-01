"""Deterministic Nodal Account Health, Balance Reconciliation, and Throughput engine."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.controls.control_result import ControlResult, ControlStatus, EvidenceItem
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.enums import PaymentStatus, OrderFulfillmentStatus, DisputeEventType, LedgerEntryType


class NodalHealthStatus(str, Enum):
    """Overall deterministic nodal account health status."""
    HEALTHY = "HEALTHY"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class NodalHealthConfig:
    """Configurable thresholds for deterministic nodal health status."""
    # Thresholds in integer minor units (paisa: 100 minor units = ₹1.00)
    warning_variance_threshold: int = 100_000    # ₹1,000.00
    critical_variance_threshold: int = 5_000_000  # ₹50,000.00
    max_critical_failures_allowed: int = 0


@dataclass
class SettlementThroughputMetrics:
    """Operational throughput metrics calculated deterministically from synthetic data."""
    total_captured_payments_count: int
    total_captured_amount: int
    total_settled_payments_count: int
    total_settled_amount: int
    total_unsettled_payments_count: int
    total_unsettled_amount: int
    settlement_completion_ratio: float
    settlement_batches_count: int
    total_net_settlement_amount: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_captured_payments_count": self.total_captured_payments_count,
            "total_captured_amount": self.total_captured_amount,
            "total_settled_payments_count": self.total_settled_payments_count,
            "total_settled_amount": self.total_settled_amount,
            "total_unsettled_payments_count": self.total_unsettled_payments_count,
            "total_unsettled_amount": self.total_unsettled_amount,
            "settlement_completion_ratio": round(self.settlement_completion_ratio, 4),
            "settlement_batches_count": self.settlement_batches_count,
            "total_net_settlement_amount": self.total_net_settlement_amount,
        }


@dataclass
class NodalHealthSummary:
    """Consolidated deterministic nodal account health summary."""
    overall_status: NodalHealthStatus
    expected_balance: int
    actual_balance: int
    variance: int
    absolute_variance: int
    account_id: str
    throughput: SettlementThroughputMetrics
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "expected_balance": self.expected_balance,
            "actual_balance": self.actual_balance,
            "variance": self.variance,
            "absolute_variance": self.absolute_variance,
            "account_id": self.account_id,
            "throughput": self.throughput.to_dict(),
            "evaluated_at": self.evaluated_at.isoformat(),
            "reasons": self.reasons,
        }


def calculate_actual_nodal_balance(
    ledger_entries: List[NodalLedgerEntry],
    account_id: str = "nodal_escrow_main",
) -> Tuple[int, bool]:
    """Calculates actual nodal balance directly from the nodal_ledger.
    
    Returns:
    - (actual_balance, is_internally_consistent)
    """
    account_entries = [e for e in ledger_entries if e.account_id == account_id]
    account_entries.sort(key=lambda x: (x.timestamp, x.id or 0))

    if not account_entries:
        return 0, True

    total_credits = sum(e.credit for e in account_entries)
    total_debits = sum(e.debit for e in account_entries)
    net_ledger_change = total_credits - total_debits

    final_balance_after = account_entries[-1].balance_after
    is_consistent = net_ledger_change == final_balance_after

    return final_balance_after, is_consistent


def calculate_expected_nodal_balance(
    payments: List[GatewayTransaction],
    settlements: List[BankSettlementBatch],
    orders: List[MerchantOrder],
    disputes: List[DisputeRefundEvent],
) -> int:
    """Deterministically derives expected nodal balance from valid operational events.
    
    Formula:
    Expected Inflows = Sum(net_amount of cleared settlements for legitimately captured & fulfilled payments)
    Expected Outflows = Sum(amount of valid customer refunds and chargeback events)
    Expected Balance = Expected Inflows - Expected Outflows
    """
    # 1. Map valid payments (Captured and fulfilled or clean)
    order_by_payment = {o.payment_id_reference: o for o in orders if o.payment_id_reference}
    
    valid_captured_payment_ids = set()
    for tx in payments:
        if tx.status in (PaymentStatus.CAPTURED.value, PaymentStatus.REFUNDED.value, PaymentStatus.PARTIALLY_REFUNDED.value, PaymentStatus.DISPUTED.value):
            # Must not be a cancelled order
            order = order_by_payment.get(tx.payment_id)
            if order and order.fulfillment_status != OrderFulfillmentStatus.CANCELLED.value:
                valid_captured_payment_ids.add(tx.payment_id)

    # 2. Sum valid settlement inflows (excluding ghost settlements on failed/cancelled payments)
    valid_settlement_inflow = 0
    for s in settlements:
        if s.payment_id and s.payment_id in valid_captured_payment_ids:
            valid_settlement_inflow += s.net_amount
        # Note: Unallocated settlements without payment mapping or ghost settlements are not part of expected business inflows

    # 3. Sum dispute and refund outflows for valid payments
    valid_dispute_outflow = 0
    for d in disputes:
        if d.payment_id in valid_captured_payment_ids:
            valid_dispute_outflow += d.amount

    expected_balance = valid_settlement_inflow - valid_dispute_outflow
    return expected_balance


def calculate_settlement_throughput(
    payments: List[GatewayTransaction],
    settlements: List[BankSettlementBatch],
) -> SettlementThroughputMetrics:
    """Calculates settlement throughput operational metrics from synthetic financial records."""
    captured_statuses = {
        PaymentStatus.CAPTURED.value,
        PaymentStatus.REFUNDED.value,
        PaymentStatus.PARTIALLY_REFUNDED.value,
        PaymentStatus.DISPUTED.value,
    }

    captured_payments = [p for p in payments if p.status in captured_statuses]
    total_captured_count = len(captured_payments)
    total_captured_amount = sum(p.amount for p in captured_payments)

    # Settlements mapped by payment_id
    settlements_by_payment = {}
    for s in settlements:
        if s.payment_id:
            settlements_by_payment.setdefault(s.payment_id, []).append(s)

    settled_count = 0
    settled_amount = 0

    for p in captured_payments:
        p_settlements = settlements_by_payment.get(p.payment_id, [])
        gross_settled = sum(s.net_amount + s.interchange_fee_deducted + s.tax_deducted for s in p_settlements)
        if gross_settled >= p.amount and p.amount > 0:
            settled_count += 1
            settled_amount += p.amount
        elif gross_settled > 0:
            # Partially settled
            settled_amount += gross_settled

    unsettled_count = total_captured_count - settled_count
    unsettled_amount = max(0, total_captured_amount - settled_amount)
    
    completion_ratio = (settled_count / total_captured_count) if total_captured_count > 0 else 1.0
    total_net_amount = sum(s.net_amount for s in settlements)

    return SettlementThroughputMetrics(
        total_captured_payments_count=total_captured_count,
        total_captured_amount=total_captured_amount,
        total_settled_payments_count=settled_count,
        total_settled_amount=settled_amount,
        total_unsettled_payments_count=unsettled_count,
        total_unsettled_amount=unsettled_amount,
        settlement_completion_ratio=completion_ratio,
        settlement_batches_count=len(settlements),
        total_net_settlement_amount=total_net_amount,
    )


def evaluate_nodal_health(
    session: Session,
    account_id: str = "nodal_escrow_main",
    config: Optional[NodalHealthConfig] = None,
    critical_control_failures_count: int = 0,
    warning_control_failures_count: int = 0,
) -> NodalHealthSummary:
    """Evaluates comprehensive nodal health, balance variance, and operational throughput."""
    cfg = config or NodalHealthConfig()

    payments = list(session.scalars(select(GatewayTransaction)).all())
    settlements = list(session.scalars(select(BankSettlementBatch)).all())
    orders = list(session.scalars(select(MerchantOrder)).all())
    disputes = list(session.scalars(select(DisputeRefundEvent)).all())
    ledger_entries = list(session.scalars(select(NodalLedgerEntry).where(NodalLedgerEntry.account_id == account_id)).all())

    # 1. Balances & Variance
    actual_balance, is_consistent = calculate_actual_nodal_balance(ledger_entries, account_id=account_id)
    expected_balance = calculate_expected_nodal_balance(payments, settlements, orders, disputes)
    
    variance = actual_balance - expected_balance
    abs_variance = abs(variance)

    # 2. Throughput
    throughput = calculate_settlement_throughput(payments, settlements)

    # 3. Deterministic Health Status Classification
    reasons = []
    if not is_consistent:
        reasons.append("Ledger running balance is internally inconsistent.")

    if abs_variance >= cfg.critical_variance_threshold:
        reasons.append(f"Balance variance {abs_variance} minor units exceeds critical threshold ({cfg.critical_variance_threshold}).")

    if critical_control_failures_count > cfg.max_critical_failures_allowed:
        reasons.append(f"{critical_control_failures_count} critical financial control failures detected.")

    if abs_variance >= cfg.warning_variance_threshold and abs_variance < cfg.critical_variance_threshold:
        reasons.append(f"Balance variance {abs_variance} minor units exceeds warning threshold ({cfg.warning_variance_threshold}).")

    if warning_control_failures_count > 0:
        reasons.append(f"{warning_control_failures_count} warning-level control issues detected.")

    if not is_consistent or abs_variance >= cfg.critical_variance_threshold or critical_control_failures_count > 0:
        status = NodalHealthStatus.CRITICAL
    elif abs_variance >= cfg.warning_variance_threshold or warning_control_failures_count > 0 or throughput.total_unsettled_payments_count > 0:
        status = NodalHealthStatus.WARNING
    else:
        status = NodalHealthStatus.HEALTHY

    return NodalHealthSummary(
        overall_status=status,
        expected_balance=expected_balance,
        actual_balance=actual_balance,
        variance=variance,
        absolute_variance=abs_variance,
        account_id=account_id,
        throughput=throughput,
        reasons=reasons,
    )
