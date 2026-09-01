"""Repository for financial source records (Gateway, Bank Settlements, Orders, Disputes, Ledger).

Enforces append-only/insert-and-query access without casual update/delete operations.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)


class FinancialSourceRepository:
    """Provides structured, immutable data access for core financial source records."""

    def __init__(self, session: Session):
        self.session = session

    # --- Gateway Transactions ---
    def add_gateway_transaction(self, transaction: GatewayTransaction) -> GatewayTransaction:
        """Appends a new gateway transaction."""
        self.session.add(transaction)
        self.session.flush()
        return transaction

    def get_gateway_transaction(self, payment_id: str) -> Optional[GatewayTransaction]:
        """Retrieves a single gateway transaction by its business payment_id."""
        stmt = select(GatewayTransaction).where(GatewayTransaction.payment_id == payment_id)
        return self.session.scalars(stmt).first()

    def list_gateway_transactions(self, limit: int = 100, offset: int = 0) -> List[GatewayTransaction]:
        """Lists gateway transactions with pagination."""
        stmt = select(GatewayTransaction).order_by(GatewayTransaction.created_at.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    # --- Bank Settlement Batches ---
    def add_settlement_batch(self, batch: BankSettlementBatch) -> BankSettlementBatch:
        """Appends a bank settlement batch entry."""
        self.session.add(batch)
        self.session.flush()
        return batch

    def get_settlement_batch(self, settlement_id: str) -> Optional[BankSettlementBatch]:
        """Retrieves a settlement batch line by settlement_id."""
        stmt = select(BankSettlementBatch).where(BankSettlementBatch.settlement_id == settlement_id)
        return self.session.scalars(stmt).first()

    def list_settlements_for_payment(self, payment_id: str) -> List[BankSettlementBatch]:
        """Retrieves all settlement batches linked to a specific payment_id."""
        stmt = select(BankSettlementBatch).where(BankSettlementBatch.payment_id == payment_id).order_by(BankSettlementBatch.clearing_timestamp.asc())
        return list(self.session.scalars(stmt).all())

    def list_settlements_by_utr(self, utr_number: str) -> List[BankSettlementBatch]:
        """Retrieves settlement batches matching a UTR number."""
        stmt = select(BankSettlementBatch).where(BankSettlementBatch.utr_number == utr_number)
        return list(self.session.scalars(stmt).all())

    # --- Merchant Orders ---
    def add_merchant_order(self, order: MerchantOrder) -> MerchantOrder:
        """Appends a merchant order record."""
        self.session.add(order)
        self.session.flush()
        return order

    def get_merchant_order(self, order_id: str) -> Optional[MerchantOrder]:
        """Retrieves a merchant order by order_id."""
        stmt = select(MerchantOrder).where(MerchantOrder.order_id == order_id)
        return self.session.scalars(stmt).first()

    def list_orders_for_payment(self, payment_id: str) -> List[MerchantOrder]:
        """Retrieves merchant orders referencing a payment_id."""
        stmt = select(MerchantOrder).where(MerchantOrder.payment_id_reference == payment_id)
        return list(self.session.scalars(stmt).all())

    # --- Dispute & Refund Events ---
    def add_dispute_event(self, event: DisputeRefundEvent) -> DisputeRefundEvent:
        """Appends a dispute, refund, or chargeback event."""
        self.session.add(event)
        self.session.flush()
        return event

    def get_dispute_event(self, event_id: str) -> Optional[DisputeRefundEvent]:
        """Retrieves a dispute/refund event by event_id."""
        stmt = select(DisputeRefundEvent).where(DisputeRefundEvent.event_id == event_id)
        return self.session.scalars(stmt).first()

    def list_dispute_events_for_payment(self, payment_id: str) -> List[DisputeRefundEvent]:
        """Lists all dispute and refund events for a payment_id."""
        stmt = select(DisputeRefundEvent).where(DisputeRefundEvent.payment_id == payment_id).order_by(DisputeRefundEvent.timestamp.asc())
        return list(self.session.scalars(stmt).all())

    # --- Nodal Ledger ---
    def add_ledger_entry(self, entry: NodalLedgerEntry) -> NodalLedgerEntry:
        """Appends a double-entry ledger entry."""
        self.session.add(entry)
        self.session.flush()
        return entry

    def get_ledger_entry(self, ledger_id: str) -> Optional[NodalLedgerEntry]:
        """Retrieves a ledger entry by ledger_id."""
        stmt = select(NodalLedgerEntry).where(NodalLedgerEntry.ledger_id == ledger_id)
        return self.session.scalars(stmt).first()

    def list_ledger_entries_for_account(self, account_id: str, limit: int = 100) -> List[NodalLedgerEntry]:
        """Retrieves ledger entries for a nodal account ordered by timestamp."""
        stmt = select(NodalLedgerEntry).where(NodalLedgerEntry.account_id == account_id).order_by(NodalLedgerEntry.timestamp.asc()).limit(limit)
        return list(self.session.scalars(stmt).all())

    def list_ledger_entries_for_transaction(self, transaction_id: str) -> List[NodalLedgerEntry]:
        """Retrieves ledger entries associated with a transaction_id/payment_id."""
        stmt = select(NodalLedgerEntry).where(NodalLedgerEntry.transaction_id == transaction_id).order_by(NodalLedgerEntry.timestamp.asc())
        return list(self.session.scalars(stmt).all())
