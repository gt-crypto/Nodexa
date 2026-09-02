"""Database model for tracking live digital-twin synthetic anomaly injections."""
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


class InjectedCase(Base):
    """Immutable log of runtime synthetic anomaly injections into operational data."""
    __tablename__ = "injected_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    injection_id = Column(String(64), unique=True, nullable=False, index=True)
    exception_family = Column(String(64), nullable=False, index=True)
    triggered_by = Column(String(64), nullable=False)
    triggered_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    source_flag = Column(String(32), nullable=False, default="live-injected", index=True)
    
    # Linked to the ExceptionRecord discovered by the downstream detection engine
    linked_exception_id = Column(
        String(64),
        ForeignKey("exceptions.exception_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    
    # Idempotency and operational tracking
    idempotency_key = Column(String(128), unique=True, nullable=True, index=True)
    status = Column(String(32), nullable=False, default="COMPLETED")
    generated_identifiers = Column(Text, nullable=True)  # JSON-encoded dictionary of generated IDs
    details_json = Column(Text, nullable=True)  # JSON-encoded scenario metadata and results

    exception_record = relationship(
        "ExceptionRecord",
        back_populates="injected_cases",
    )

    __table_args__ = (
        Index("idx_inj_family_time", "exception_family", "triggered_at"),
        Index("idx_inj_source_time", "source_flag", "triggered_at"),
    )
