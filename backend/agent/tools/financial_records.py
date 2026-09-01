"""Read-only financial records lookup tools for AI investigator."""
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)


def lookup_payment(session: Session, payment_id: str) -> Optional[Dict[str, Any]]:
    """Looks up gateway transaction and associated merchant order details."""
    tx = session.scalars(select(GatewayTransaction).where(GatewayTransaction.payment_id == payment_id)).first()
    if not tx:
        return None

    orders = list(session.scalars(select(MerchantOrder).where(MerchantOrder.payment_id_reference == payment_id)).all())
    order_data = [
        {
            "order_id": o.order_id,
            "fulfillment_status": o.fulfillment_status,
            "order_amount": o.order_amount,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]

    return {
        "source": "gateway_transactions",
        "payment_id": tx.payment_id,
        "merchant_id": tx.merchant_id,
        "amount": tx.amount,
        "currency": tx.currency,
        "status": tx.status,
        "method": tx.method,
        "created_at": tx.created_at.isoformat() if tx.created_at else None,
        "associated_orders": order_data,
    }


def lookup_settlements(
    session: Session,
    payment_id: Optional[str] = None,
    settlement_id: Optional[str] = None,
    utr: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Looks up bank settlement batch records by payment_id, settlement_id, or UTR."""
    stmt = select(BankSettlementBatch)
    if settlement_id:
        stmt = stmt.where(BankSettlementBatch.settlement_id == settlement_id)
    elif utr:
        stmt = stmt.where(BankSettlementBatch.utr_number == utr)
    elif payment_id:
        stmt = stmt.where(BankSettlementBatch.payment_id == payment_id)

    batches = list(session.scalars(stmt).all())
    return [
        {
            "source": "bank_settlement_batches",
            "settlement_id": b.settlement_id,
            "payment_id": b.payment_id,
            "acquirer_id": b.acquirer_id,
            "utr_number": b.utr_number,
            "net_amount": b.net_amount,
            "interchange_fee_deducted": b.interchange_fee_deducted,
            "tax_deducted": b.tax_deducted,
            "clearing_timestamp": b.clearing_timestamp.isoformat() if b.clearing_timestamp else None,
            "raw_payment_reference": b.raw_payment_reference,
        }
        for b in batches
    ]


def lookup_disputes(session: Session, payment_id: str) -> List[Dict[str, Any]]:
    """Looks up refund and chargeback dispute events for a payment."""
    stmt = select(DisputeRefundEvent).where(DisputeRefundEvent.payment_id == payment_id).order_by(DisputeRefundEvent.timestamp.asc())
    events = list(session.scalars(stmt).all())
    return [
        {
            "source": "dispute_refund_events",
            "event_id": d.event_id,
            "payment_id": d.payment_id,
            "event_type": d.event_type,
            "amount": d.amount,
            "timestamp": d.timestamp.isoformat() if d.timestamp else None,
            "reason_code": d.reason_code,
        }
        for d in events
    ]


def lookup_ledger(
    session: Session,
    payment_id: Optional[str] = None,
    account_id: str = "nodal_escrow_main",
) -> List[Dict[str, Any]]:
    """Looks up nodal ledger entries for an account and optional payment_id."""
    stmt = select(NodalLedgerEntry).where(NodalLedgerEntry.account_id == account_id)
    if payment_id:
        stmt = stmt.where(NodalLedgerEntry.transaction_id == payment_id)
    stmt = stmt.order_by(NodalLedgerEntry.timestamp.asc())

    entries = list(session.scalars(stmt).all())
    return [
        {
            "source": "nodal_ledger",
            "ledger_id": l.ledger_id,
            "transaction_id": l.transaction_id,
            "account_id": l.account_id,
            "entry_type": l.entry_type,
            "debit": l.debit,
            "credit": l.credit,
            "balance_after": l.balance_after,
            "timestamp": l.timestamp.isoformat() if l.timestamp else None,
        }
        for l in entries
    ]
