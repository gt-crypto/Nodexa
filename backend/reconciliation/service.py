"""Deterministic reconciliation service providing payment, settlement, and account reconciliation."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.controls.control_result import ControlResult, ControlStatus
from backend.controls.settlement_sla import evaluate_settlement_sla, SettlementSLAConfig
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.reconciliation.matching import (
    match_payment_to_orders,
    match_payment_to_settlements,
    match_settlement_to_payment,
    MatchStatus,
)
from backend.reconciliation.amounts import (
    validate_gateway_order_amounts,
    validate_settlement_components,
    validate_payment_vs_settlement_amount,
)
from backend.reconciliation.settlements import (
    aggregate_settlements_for_payment,
    validate_settlement_totals,
    SettlementAggregation,
)
from backend.reconciliation.duplicates import (
    detect_duplicate_settlements,
    detect_duplicate_disputes,
    detect_duplicate_ledger_postings,
)
from backend.controls.invariants import (
    validate_ledger_balance_progression,
    validate_debit_credit_sanity,
    validate_non_negative_constraints,
    validate_currency_consistency,
    validate_reference_integrity,
)


@dataclass
class PaymentReconciliationResult:
    """Complete deterministic reconciliation summary for a single payment."""
    payment_id: str
    is_reconciled: bool
    control_results: List[ControlResult] = field(default_factory=list)
    settlement_aggregation: Optional[SettlementAggregation] = None
    order_id: Optional[str] = None
    settlement_ids: List[str] = field(default_factory=list)
    dispute_event_ids: List[str] = field(default_factory=list)
    ledger_entry_ids: List[str] = field(default_factory=list)


@dataclass
class SettlementReconciliationResult:
    """Deterministic reconciliation summary for an individual settlement batch."""
    settlement_id: str
    is_reconciled: bool
    payment_id: Optional[str] = None
    control_results: List[ControlResult] = field(default_factory=list)


@dataclass
class AccountReconciliationResult:
    """Deterministic reconciliation summary for a nodal account."""
    account_id: str
    is_reconciled: bool
    total_ledger_entries: int
    control_results: List[ControlResult] = field(default_factory=list)


class ReconciliationService:
    """Encapsulates all deterministic reconciliation and matching workflows."""

    def __init__(self, session: Session, sla_config: Optional[SettlementSLAConfig] = None):
        self.session = session
        self.sla_config = sla_config or SettlementSLAConfig()

    def reconcile_payment(
        self,
        payment_id: str,
        current_time: Optional[datetime] = None,
    ) -> Optional[PaymentReconciliationResult]:
        """Performs full deterministic multi-source reconciliation for a payment."""
        stmt = select(GatewayTransaction).where(GatewayTransaction.payment_id == payment_id)
        payment = self.session.scalars(stmt).first()
        if not payment:
            return None

        # Fetch related records
        order_stmt = select(MerchantOrder).where(MerchantOrder.payment_id_reference == payment_id)
        orders = list(self.session.scalars(order_stmt).all())

        settle_stmt = select(BankSettlementBatch).where(BankSettlementBatch.payment_id == payment_id)
        settlements = list(self.session.scalars(settle_stmt).all())

        # Also search raw reference if direct link is empty
        if not settlements:
            raw_stmt = select(BankSettlementBatch).where(
                BankSettlementBatch.raw_payment_reference.like(f"%{payment_id}%")
            )
            settlements = list(self.session.scalars(raw_stmt).all())

        dispute_stmt = select(DisputeRefundEvent).where(DisputeRefundEvent.payment_id == payment_id)
        disputes = list(self.session.scalars(dispute_stmt).all())

        ledger_stmt = select(NodalLedgerEntry).where(NodalLedgerEntry.transaction_id == payment_id)
        ledger_entries = list(self.session.scalars(ledger_stmt).all())

        controls: List[ControlResult] = []

        # 1. Identifier Matching
        order_match = match_payment_to_orders(payment, orders)
        controls.append(order_match.to_control_result(f"CTRL-MATCH-ORDER-{payment_id}", "Order Matching"))

        settle_match = match_payment_to_settlements(payment, settlements)
        controls.append(settle_match.to_control_result(f"CTRL-MATCH-SETTLE-{payment_id}", "Settlement Matching"))

        # 2. Amounts Validation
        controls.append(validate_gateway_order_amounts(payment, orders))
        for s in settlements:
            controls.append(validate_settlement_components(s))
        controls.append(validate_payment_vs_settlement_amount(payment, settlements))

        # 3. Settlement Totals & Tranche Aggregation
        controls.append(validate_settlement_totals(payment, settlements))
        aggregation = aggregate_settlements_for_payment(payment, settlements)

        # 4. Settlement SLA
        controls.append(evaluate_settlement_sla(payment, settlements, current_time=current_time, config=self.sla_config))

        is_reconciled = all(c.status in (ControlStatus.PASS, ControlStatus.NOT_APPLICABLE) for c in controls)

        return PaymentReconciliationResult(
            payment_id=payment_id,
            is_reconciled=is_reconciled,
            control_results=controls,
            settlement_aggregation=aggregation,
            order_id=orders[0].order_id if orders else None,
            settlement_ids=[s.settlement_id for s in settlements],
            dispute_event_ids=[d.event_id for d in disputes],
            ledger_entry_ids=[l.ledger_id for l in ledger_entries],
        )

    def reconcile_settlement(self, settlement_id: str) -> Optional[SettlementReconciliationResult]:
        """Performs deterministic reconciliation for a single bank settlement batch."""
        stmt = select(BankSettlementBatch).where(BankSettlementBatch.settlement_id == settlement_id)
        settlement = self.session.scalars(stmt).first()
        if not settlement:
            return None

        controls: List[ControlResult] = []
        controls.append(validate_settlement_components(settlement))

        payments = list(self.session.scalars(select(GatewayTransaction)).all())
        match_res = match_settlement_to_payment(settlement, payments)
        controls.append(match_res.to_control_result(f"CTRL-MATCH-PMT-{settlement_id}", "Payment Identifier Match"))

        is_reconciled = all(c.status in (ControlStatus.PASS, ControlStatus.NOT_APPLICABLE) for c in controls)

        return SettlementReconciliationResult(
            settlement_id=settlement_id,
            is_reconciled=is_reconciled,
            payment_id=settlement.payment_id,
            control_results=controls,
        )

    def reconcile_account(self, account_id: str = "nodal_escrow_main") -> AccountReconciliationResult:
        """Performs deterministic ledger and invariant reconciliation for a nodal account."""
        ledger_stmt = select(NodalLedgerEntry).where(NodalLedgerEntry.account_id == account_id).order_by(NodalLedgerEntry.timestamp.asc())
        ledger_entries = list(self.session.scalars(ledger_stmt).all())

        payments = list(self.session.scalars(select(GatewayTransaction)).all())
        settlements = list(self.session.scalars(select(BankSettlementBatch)).all())
        orders = list(self.session.scalars(select(MerchantOrder)).all())
        disputes = list(self.session.scalars(select(DisputeRefundEvent)).all())

        known_payment_ids = {p.payment_id for p in payments}

        controls: List[ControlResult] = []
        controls.extend(validate_ledger_balance_progression(ledger_entries, account_id=account_id))
        controls.extend(validate_debit_credit_sanity(ledger_entries))
        controls.extend(validate_non_negative_constraints(payments, settlements, orders, disputes, ledger_entries))
        controls.extend(validate_currency_consistency(payments))
        controls.extend(validate_reference_integrity(ledger_entries, known_payment_ids))
        controls.extend(detect_duplicate_settlements(settlements))
        controls.extend(detect_duplicate_disputes(disputes))
        controls.extend(detect_duplicate_ledger_postings(ledger_entries))

        is_reconciled = all(c.status in (ControlStatus.PASS, ControlStatus.NOT_APPLICABLE) for c in controls)

        return AccountReconciliationResult(
            account_id=account_id,
            is_reconciled=is_reconciled,
            total_ledger_entries=len(ledger_entries),
            control_results=controls,
        )
