"""Remediation action and approval models for controlled operational workflow."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    Boolean,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from backend.models.database import Base
from backend.models.enums import RemediationStatus


def utc_now():
    return datetime.now(timezone.utc)


class RemediationAction(Base):
    """Represents a planned, approved, executed, or rejected controlled remediation action."""
    __tablename__ = "remediation_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    action_id = Column(String(128), unique=True, nullable=False, index=True)
    exception_id = Column(
        String(64),
        ForeignKey("exceptions.exception_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_type = Column(String(64), nullable=False, index=True)
    status = Column(String(32), nullable=False, default=RemediationStatus.PLANNED.value, index=True)
    
    # Financial and Policy context
    action_payload = Column(Text, nullable=False)  # JSON-encoded parameters
    policy_decision_id = Column(String(128), nullable=True, index=True)
    risk_assessment_id = Column(String(64), nullable=True, index=True)
    investigation_id = Column(String(64), nullable=True, index=True)
    deterministic_exposure = Column(BigInteger, nullable=True, default=0)

    # Actor and approval mandates
    requested_by = Column(String(64), nullable=True)
    approved_by = Column(String(64), nullable=True)
    approval_required = Column(Boolean, nullable=False, default=False)
    approval_role = Column(String(32), nullable=True)
    verification_required = Column(Boolean, nullable=False, default=True)

    # State snapshots
    before_snapshot = Column(Text, nullable=True)  # JSON snapshot
    after_snapshot = Column(Text, nullable=True)   # JSON snapshot
    result_summary = Column(Text, nullable=True)
    error_reason = Column(Text, nullable=True)

    # Version tracking
    policy_version = Column(String(32), nullable=False, default="v1")
    remediation_version = Column(String(32), nullable=False, default="v1")

    # Timestamps
    requested_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    executed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    @property
    def remediation_id(self) -> str:
        """Alias for action_id to match PRD naming."""
        return self.action_id

    # Relationships
    exception_record = relationship(
        "ExceptionRecord",
        back_populates="remediation_actions",
    )
    verification_results = relationship(
        "VerificationResult",
        back_populates="remediation_action",
        cascade="all, delete-orphan",
    )
    verification_records = relationship(
        "VerificationRecord",
        back_populates="remediation_action",
        cascade="all, delete-orphan",
        order_by="VerificationRecord.created_at.desc()",
    )
    approvals = relationship(
        "RemediationApproval",
        back_populates="remediation_action",
        cascade="all, delete-orphan",
        order_by="RemediationApproval.timestamp.desc()",
    )

    __table_args__ = (
        Index("idx_rem_type_status", "action_type", "status"),
        Index("idx_rem_exc_created", "exception_id", "created_at"),
    )


class RemediationApproval(Base):
    """Immutable audit record of human role approval or rejection for a remediation plan."""
    __tablename__ = "remediation_approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    approval_id = Column(String(64), unique=True, nullable=False, index=True)
    action_id = Column(
        String(128),
        ForeignKey("remediation_actions.action_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    required_role = Column(String(32), nullable=False)
    approved_by = Column(String(64), nullable=False)
    decision = Column(String(32), nullable=False)  # APPROVED / REJECTED
    reason = Column(Text, nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    policy_version = Column(String(32), nullable=False, default="v1")
    expires_at = Column(DateTime(timezone=True), nullable=True)

    remediation_action = relationship(
        "RemediationAction",
        back_populates="approvals",
    )

    __table_args__ = (
        Index("idx_appr_action_time", "action_id", "timestamp"),
    )
