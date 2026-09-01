"""Risk and Materiality Assessment models for Nodal Sentinel exceptions."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
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


class RiskAssessment(Base):
    """Immutable, versioned risk and financial materiality assessment for an exception."""
    __tablename__ = "risk_assessments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    assessment_id = Column(String(64), unique=True, nullable=False, index=True)
    exception_id = Column(
        String(64),
        ForeignKey("exceptions.exception_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Financial Exposure (Minor integer units)
    deterministic_exposure = Column(BigInteger, nullable=False)
    currency = Column(String(3), nullable=False, default="INR")
    exposure_type = Column(String(32), nullable=False)
    gross_exposure = Column(BigInteger, nullable=False)
    recoverable_amount = Column(BigInteger, nullable=False, default=0)
    net_exposure = Column(BigInteger, nullable=False)

    # Risk & Prioritization metrics
    materiality = Column(String(16), nullable=False, index=True)
    risk_score = Column(Integer, nullable=False, index=True)  # 0 - 100
    score_breakdown = Column(Text, nullable=True)  # JSON string
    risk_factors = Column(Text, nullable=True)  # JSON string
    priority = Column(String(8), nullable=False, index=True)  # P1, P2, P3, P4
    escalation = Column(String(32), nullable=False, index=True)
    explanation = Column(Text, nullable=False)

    # Audit & Policy Tracking
    policy_version = Column(String(32), nullable=False, default="v1")
    scoring_version = Column(String(32), nullable=False, default="v1")
    threshold_version = Column(String(32), nullable=False, default="v1")

    calculated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    # Relationships
    exception_record = relationship(
        "ExceptionRecord",
        back_populates="risk_assessments",
    )

    __table_args__ = (
        Index("idx_risk_priority_score", "priority", "risk_score"),
        Index("idx_risk_exc_calc", "exception_id", "calculated_at"),
    )
