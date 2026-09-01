"""Audit event model providing append-only, tamper-evident audit logging."""
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
from sqlalchemy.orm import relationship

from backend.models.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class AuditEvent(Base):
    """Immutable audit record logging detections, investigations, policy decisions, and remediations."""
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    audit_event_id = Column(String(64), unique=True, nullable=False, index=True)
    exception_id = Column(
        String(64),
        ForeignKey("exceptions.exception_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    investigation_id = Column(String(64), nullable=True, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    actor_type = Column(String(32), nullable=False)  # SYSTEM, AI_AGENT, FINANCE_CONTROLLER
    actor_id = Column(String(64), nullable=True)
    event_summary = Column(String(255), nullable=False)
    event_payload = Column(Text, nullable=False)  # JSON-encoded payload
    
    # Hash chain support for provenance
    previous_event_hash = Column(String(64), nullable=True)
    event_hash = Column(String(64), nullable=True)

    exception_record = relationship(
        "ExceptionRecord",
        back_populates="audit_events",
    )

    __table_args__ = (
        Index("idx_audit_type_timestamp", "event_type", "timestamp"),
        Index("idx_audit_actor_timestamp", "actor_type", "timestamp"),
    )
