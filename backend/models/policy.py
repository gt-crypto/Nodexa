"""Policy decision models and audit records for Nodal Sentinel exceptions."""
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


def utc_now():
    return datetime.now(timezone.utc)


class PolicyDecisionRecord(Base):
    """Immutable, versioned policy gating and decision evaluation record."""
    __tablename__ = "policy_decisions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    decision_id = Column(String(64), unique=True, nullable=False, index=True)
    exception_id = Column(
        String(64),
        ForeignKey("exceptions.exception_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    requested_action = Column(String(64), nullable=False, index=True)
    decision = Column(String(32), nullable=False, index=True)  # ALLOW, REQUIRE_APPROVAL, BLOCK, etc.
    policy_version = Column(String(32), nullable=False, default="v1")

    # Action permissions
    allowed_actions = Column(Text, nullable=False)  # JSON array
    prohibited_actions = Column(Text, nullable=False)  # JSON array

    # Approval requirements
    approval_required = Column(Boolean, nullable=False, default=False)
    approval_role = Column(String(32), nullable=True)
    approval_reason = Column(Text, nullable=True)

    # Escalation requirements
    escalation_required = Column(Boolean, nullable=False, default=False)
    escalation_level = Column(String(32), nullable=True)
    escalation_reason = Column(Text, nullable=True)

    # Evidence and rule diagnostics
    evidence_requirements = Column(Text, nullable=True)  # JSON array
    rules_evaluated = Column(Text, nullable=True)  # JSON array
    violated_rules = Column(Text, nullable=True)  # JSON array
    rationale = Column(Text, nullable=False)

    # Risk context snapshot
    risk_score = Column(Integer, nullable=False, default=0)
    priority = Column(String(8), nullable=False, default="P4")
    materiality = Column(String(16), nullable=False, default="NONE")
    exposure = Column(BigInteger, nullable=False, default=0)

    evaluated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    exception_record = relationship(
        "ExceptionRecord",
        back_populates="policy_decisions",
    )

    __table_args__ = (
        Index("idx_policy_exc_action", "exception_id", "requested_action"),
        Index("idx_policy_decision_eval", "decision", "evaluated_at"),
    )
