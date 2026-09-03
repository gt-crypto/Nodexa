"""Escalation Webhook database model for tracking outbound notifications."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
)
from backend.models.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class EscalationWebhookDelivery(Base):
    """Tracks idempotent delivery state of outbound escalation webhook notifications."""

    __tablename__ = "escalation_webhook_deliveries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    delivery_id = Column(String(64), unique=True, nullable=False, index=True)
    event_id = Column(String(64), nullable=False, index=True)
    exception_id = Column(
        String(64),
        ForeignKey("exceptions.exception_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(64), nullable=False, default="EXCEPTION_ESCALATED", index=True)
    payload_hash = Column(String(64), nullable=False)
    destination_url = Column(String(256), nullable=True)
    delivery_status = Column(String(32), nullable=False, default="PENDING", index=True)  # PENDING, DELIVERED, FAILED, DISABLED
    attempt_count = Column(Integer, nullable=False, default=0)
    response_status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    
    first_attempt_at = Column(DateTime(timezone=True), nullable=True)
    last_attempt_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    
    source_flag = Column(String(32), nullable=False, default="seeded", index=True)
    request_id = Column(String(64), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    __table_args__ = (
        Index("idx_esc_delivery_status", "delivery_status", "created_at"),
        Index("idx_esc_event_exc", "event_id", "exception_id"),
    )
