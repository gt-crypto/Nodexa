"""Investigation run model establishing persistence foundation for AI investigations."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    Numeric,
    String,
    Text,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from backend.models.database import Base
from backend.models.enums import InvestigationStatus


def utc_now():
    return datetime.now(timezone.utc)


class InvestigationRun(Base):
    """Represents an execution run of the AI investigation state machine."""
    __tablename__ = "investigation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    investigation_id = Column(String(64), unique=True, nullable=False, index=True)
    exception_id = Column(
        String(64),
        ForeignKey("exceptions.exception_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(32), nullable=False, default=InvestigationStatus.CREATED.value, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    agent_version = Column(String(32), nullable=True)
    final_classification = Column(String(128), nullable=True)
    root_cause = Column(Text, nullable=True)
    confidence = Column(Numeric(5, 4), nullable=True)
    recommended_action = Column(String(512), nullable=True)
    human_approval_required = Column(Boolean, nullable=False, default=False)
    error_info = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    exception_record = relationship(
        "ExceptionRecord",
        back_populates="investigation_runs",
    )

    __table_args__ = (
        Index("idx_inv_status_created", "status", "created_at"),
    )
