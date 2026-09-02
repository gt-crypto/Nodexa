"""Copilot query audit persistence model for Ask Sentinel."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, Index
from backend.models.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class CopilotQuery(Base):
    """Stores audit records for operator questions processed by Ask Sentinel copilot."""

    __tablename__ = "copilot_queries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_id = Column(String(64), unique=True, nullable=False, index=True)
    question = Column(Text, nullable=False)
    request_id = Column(String(64), nullable=True, index=True)
    actor_id = Column(String(64), nullable=False, default="operator")
    tools_used = Column(Text, nullable=False, default="[]")  # JSON encoded list of tool names
    evidence_refs = Column(Text, nullable=False, default="[]")  # JSON encoded list of evidence IDs
    response_status = Column(String(32), nullable=False, default="SUCCESS")  # SUCCESS, ABSTAINED, ERROR
    abstained = Column(Boolean, nullable=False, default=False)
    confidence = Column(String(16), nullable=False, default="HIGH")  # HIGH, MEDIUM, LOW
    copilot_version = Column(String(32), nullable=False, default="v2.0")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    __table_args__ = (
        Index("idx_copilot_created", "created_at"),
        Index("idx_copilot_actor", "actor_id"),
    )
