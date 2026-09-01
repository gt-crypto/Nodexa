"""Deterministic correlation engine for grouping operational records and control findings by primary entity."""
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.controls.control_result import ControlResult
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)


@dataclass
class CorrelatedEntity:
    """Group of related operational records and deterministic control results for a financial case."""
    entity_key: str  # payment_id or unallocated_settlement_id
    payment: Optional[GatewayTransaction] = None
    orders: List[MerchantOrder] = field(default_factory=list)
    settlements: List[BankSettlementBatch] = field(default_factory=list)
    disputes: List[DisputeRefundEvent] = field(default_factory=list)
    ledger_entries: List[NodalLedgerEntry] = field(default_factory=list)
    control_results: List[ControlResult] = field(default_factory=list)

    @property
    def primary_payment_id(self) -> Optional[str]:
        return self.payment.payment_id if self.payment else None

    @property
    def primary_order_id(self) -> Optional[str]:
        return self.orders[0].order_id if self.orders else None

    @property
    def all_record_references(self) -> List[tuple[str, str]]:
        """Returns list of (record_type, record_identifier) for affected records linkage."""
        refs: List[tuple[str, str]] = []
        if self.payment:
            refs.append(("payment", self.payment.payment_id))
        for o in self.orders:
            refs.append(("order", o.order_id))
        for s in self.settlements:
            refs.append(("settlement", s.settlement_id))
        for d in self.disputes:
            refs.append(("dispute", d.event_id))
        for l in self.ledger_entries:
            refs.append(("ledger", l.ledger_id))
        return refs


def correlate_operational_entities(
    session: Session,
    control_results: Optional[List[ControlResult]] = None,
    account_id: str = "nodal_escrow_main",
) -> Dict[str, CorrelatedEntity]:
    """Correlates all operational tables and control findings into structured entity groups."""
    payments = list(session.scalars(select(GatewayTransaction)).all())
    orders = list(session.scalars(select(MerchantOrder)).all())
    settlements = list(session.scalars(select(BankSettlementBatch)).all())
    disputes = list(session.scalars(select(DisputeRefundEvent)).all())
    ledger_entries = list(
        session.scalars(select(NodalLedgerEntry).where(NodalLedgerEntry.account_id == account_id)).all()
    )

    correlated: Dict[str, CorrelatedEntity] = {}

    # 1. Initialize with Payments
    for p in payments:
        correlated[p.payment_id] = CorrelatedEntity(
            entity_key=p.payment_id,
            payment=p,
        )

    # 2. Correlate Orders
    for o in orders:
        if o.payment_id_reference and o.payment_id_reference in correlated:
            correlated[o.payment_id_reference].orders.append(o)
        else:
            key = f"order_{o.order_id}"
            correlated.setdefault(key, CorrelatedEntity(entity_key=key)).orders.append(o)

    # 3. Correlate Settlements
    for s in settlements:
        if s.payment_id and s.payment_id in correlated:
            correlated[s.payment_id].settlements.append(s)
        elif s.raw_payment_reference:
            # Check if any payment_id is contained in raw reference
            matched_key = None
            for p_id in correlated.keys():
                if p_id in s.raw_payment_reference:
                    matched_key = p_id
                    break
            if matched_key:
                correlated[matched_key].settlements.append(s)
            else:
                key = f"settlement_{s.settlement_id}"
                correlated.setdefault(key, CorrelatedEntity(entity_key=key)).settlements.append(s)
        else:
            key = f"settlement_{s.settlement_id}"
            correlated.setdefault(key, CorrelatedEntity(entity_key=key)).settlements.append(s)

    # 4. Correlate Disputes
    for d in disputes:
        if d.payment_id in correlated:
            correlated[d.payment_id].disputes.append(d)
        else:
            key = f"dispute_{d.event_id}"
            correlated.setdefault(key, CorrelatedEntity(entity_key=key)).disputes.append(d)

    # 5. Correlate Ledger Entries
    for l in ledger_entries:
        if l.transaction_id and l.transaction_id in correlated:
            correlated[l.transaction_id].ledger_entries.append(l)

    # 6. Correlate Control Findings
    if control_results:
        for ctrl in control_results:
            for rec_id in ctrl.affected_record_ids:
                if rec_id in correlated:
                    correlated[rec_id].control_results.append(ctrl)

    return correlated
