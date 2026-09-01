"""Core financial source models for Nodal Sentinel."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from backend.models.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class GatewayTransaction(Base):
    """Represents a payment transaction recorded at the payment gateway."""
    __tablename__ = "gateway_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    payment_id = Column(String(64), unique=True, nullable=False, index=True)
    merchant_id = Column(String(64), nullable=False, index=True)
    # Monetary amounts stored strictly as BigInteger minor units (e.g., paisa/cents)
    amount = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    status = Column(String(32), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    method = Column(String(32), nullable=False)
    card_type = Column(String(32), nullable=True)
    auth_code = Column(String(64), nullable=True)
    error_code = Column(String(64), nullable=True)

    # Relationships
    settlement_batches = relationship(
        "BankSettlementBatch",
        back_populates="gateway_transaction",
        cascade="all, delete-orphan",
    )
    orders = relationship(
        "MerchantOrder",
        back_populates="gateway_transaction",
    )
    dispute_events = relationship(
        "DisputeRefundEvent",
        back_populates="gateway_transaction",
        cascade="all, delete-orphan",
    )
    ledger_entries = relationship(
        "NodalLedgerEntry",
        back_populates="gateway_transaction",
    )

    __table_args__ = (
        Index("idx_gw_merchant_created", "merchant_id", "created_at"),
        Index("idx_gw_status_created", "status", "created_at"),
    )


class BankSettlementBatch(Base):
    """Represents an acquirer/bank settlement clearing batch or individual settlement line."""
    __tablename__ = "bank_settlement_batches"

    id = Column(Integer, primary_key=True, autoincrement=True)
    settlement_id = Column(String(64), nullable=False, index=True)
    utr_number = Column(String(64), nullable=True, index=True)
    acquirer_id = Column(String(64), nullable=False, index=True)
    raw_payment_reference = Column(String(128), nullable=True, index=True)
    
    # Optional direct link to payment_id (supports many-to-one / partial settlements)
    payment_id = Column(
        String(64),
        ForeignKey("gateway_transactions.payment_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # Monetary amounts stored as BigInteger minor units
    net_amount = Column(BigInteger, nullable=False)
    interchange_fee_deducted = Column(BigInteger, nullable=False, default=0)
    tax_deducted = Column(BigInteger, nullable=False, default=0)
    clearing_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    gateway_transaction = relationship(
        "GatewayTransaction",
        back_populates="settlement_batches",
    )

    __table_args__ = (
        Index("idx_settle_acquirer_clearing", "acquirer_id", "clearing_timestamp"),
    )


class MerchantOrder(Base):
    """Represents merchant-side order records and fulfillment status."""
    __tablename__ = "merchant_orders"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_id = Column(String(64), unique=True, nullable=False, index=True)
    payment_id_reference = Column(
        String(64),
        ForeignKey("gateway_transactions.payment_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    customer_id = Column(String(64), nullable=True, index=True)
    fulfillment_status = Column(String(32), nullable=False, index=True)
    order_amount = Column(BigInteger, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    gateway_transaction = relationship(
        "GatewayTransaction",
        back_populates="orders",
    )

    __table_args__ = (
        Index("idx_order_fulfillment_created", "fulfillment_status", "created_at"),
    )


class DisputeRefundEvent(Base):
    """Represents refunds, chargebacks, reversals, and chargeback reversals."""
    __tablename__ = "dispute_refund_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), unique=True, nullable=False, index=True)
    payment_id = Column(
        String(64),
        ForeignKey("gateway_transactions.payment_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(32), nullable=False, index=True)
    amount = Column(BigInteger, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    reason_code = Column(String(64), nullable=True)

    gateway_transaction = relationship(
        "GatewayTransaction",
        back_populates="dispute_events",
    )

    __table_args__ = (
        Index("idx_dispute_payment_type", "payment_id", "event_type"),
    )


class NodalLedgerEntry(Base):
    """Represents double-entry nodal escrow ledger postings and balance history."""
    __tablename__ = "nodal_ledger"

    id = Column(Integer, primary_key=True, autoincrement=True)
    ledger_id = Column(String(64), unique=True, nullable=False, index=True)
    transaction_id = Column(
        String(64),
        ForeignKey("gateway_transactions.payment_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    account_id = Column(String(64), nullable=False, index=True)
    debit = Column(BigInteger, nullable=False, default=0)
    credit = Column(BigInteger, nullable=False, default=0)
    balance_after = Column(BigInteger, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    entry_type = Column(String(32), nullable=False, index=True)
    reference = Column(String(128), nullable=True)

    gateway_transaction = relationship(
        "GatewayTransaction",
        back_populates="ledger_entries",
    )

    __table_args__ = (
        Index("idx_ledger_account_timestamp", "account_id", "timestamp"),
    )
