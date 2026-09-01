"""Exception models and state transition tracking for Nodal Sentinel."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    Numeric,
    String,
    Text,
    DateTime,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from backend.models.database import Base
from backend.models.enums import ExceptionState


def utc_now():
    return datetime.now(timezone.utc)


class ExceptionRecord(Base):
    """Foundational exception record generated upon anomaly detection or reconciliation failure."""
    __tablename__ = "exceptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    exception_id = Column(String(64), unique=True, nullable=False, index=True)
    exception_type = Column(String(64), nullable=False, index=True)
    severity = Column(String(16), nullable=False, index=True)
    state = Column(String(32), nullable=False, default=ExceptionState.DETECTED.value, index=True)
    
    # Financial exposure in minor integer units
    exposure = Column(BigInteger, nullable=False, default=0)
    confidence = Column(Numeric(5, 4), nullable=False, default=1.0000)
    
    description = Column(Text, nullable=True)
    primary_payment_id = Column(String(64), nullable=True, index=True)
    primary_order_id = Column(String(64), nullable=True, index=True)
    
    detected_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    # Relationships
    transitions = relationship(
        "ExceptionStateTransition",
        back_populates="exception_record",
        cascade="all, delete-orphan",
        order_by="ExceptionStateTransition.timestamp",
    )
    affected_records = relationship(
        "ExceptionAffectedRecord",
        back_populates="exception_record",
        cascade="all, delete-orphan",
    )
    investigation_runs = relationship(
        "InvestigationRun",
        back_populates="exception_record",
        cascade="all, delete-orphan",
    )
    remediation_actions = relationship(
        "RemediationAction",
        back_populates="exception_record",
        cascade="all, delete-orphan",
    )
    verification_results = relationship(
        "VerificationResult",
        back_populates="exception_record",
        cascade="all, delete-orphan",
    )
    verification_records = relationship(
        "VerificationRecord",
        back_populates="exception_record",
        cascade="all, delete-orphan",
        order_by="VerificationRecord.created_at.desc()",
    )
    risk_assessments = relationship(
        "RiskAssessment",
        back_populates="exception_record",
        cascade="all, delete-orphan",
        order_by="RiskAssessment.calculated_at.desc()",
    )
    policy_decisions = relationship(
        "PolicyDecisionRecord",
        back_populates="exception_record",
        cascade="all, delete-orphan",
        order_by="PolicyDecisionRecord.evaluated_at.desc()",
    )
    audit_events = relationship(
        "AuditEvent",
        back_populates="exception_record",
    )

    __table_args__ = (
        Index("idx_exc_state_severity", "state", "severity"),
        Index("idx_exc_type_detected", "exception_type", "detected_at"),
    )


class ExceptionStateTransition(Base):
    """Immutable record of every lifecycle state transition for an exception."""
    __tablename__ = "exception_state_transitions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    transition_id = Column(String(64), unique=True, nullable=False, index=True)
    exception_id = Column(
        String(64),
        ForeignKey("exceptions.exception_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_state = Column(String(32), nullable=False)
    to_state = Column(String(32), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    reason = Column(Text, nullable=True)
    actor_type = Column(String(32), nullable=False)  # SYSTEM, AI_AGENT, FINANCE_CONTROLLER
    actor_id = Column(String(64), nullable=True)

    exception_record = relationship(
        "ExceptionRecord",
        back_populates="transitions",
    )


class ExceptionAffectedRecord(Base):
    """Links multiple affected financial records (payments, orders, settlements, disputes) to an exception."""
    __tablename__ = "exception_affected_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    exception_id = Column(
        String(64),
        ForeignKey("exceptions.exception_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    record_type = Column(String(32), nullable=False)  # payment, settlement, order, dispute, ledger
    record_identifier = Column(String(64), nullable=False, index=True)
    metadata_json = Column(Text, nullable=True)

    exception_record = relationship(
        "ExceptionRecord",
        back_populates="affected_records",
    )

    __table_args__ = (
        Index("idx_aff_exc_rec", "exception_id", "record_identifier"),
    )
