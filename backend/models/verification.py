"""Verification record and result models for post-remediation deterministic verification."""
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
from backend.models.enums import VerificationStatus, VerificationMode


def utc_now():
    return datetime.now(timezone.utc)


class VerificationRecord(Base):
    """Authoritative post-remediation deterministic verification record."""
    __tablename__ = "verification_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    verification_id = Column(String(64), unique=True, nullable=False, index=True)
    remediation_id = Column(
        String(64),
        ForeignKey("remediation_actions.action_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    exception_id = Column(
        String(64),
        ForeignKey("exceptions.exception_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    verification_status = Column(
        String(32),
        nullable=False,
        default=VerificationStatus.PENDING.value,
        index=True,
    )
    verification_result = Column(String(32), nullable=True)  # PASSED, FAILED

    # Exposure quantification
    original_exposure = Column(BigInteger, nullable=False, default=0)
    remaining_exposure = Column(BigInteger, nullable=False, default=0)
    exposure_reduction = Column(BigInteger, nullable=False, default=0)
    exposure_reduction_bps = Column(Integer, nullable=False, default=0)

    # State snapshots
    expected_state = Column(Text, nullable=True)  # JSON
    actual_state = Column(Text, nullable=True)    # JSON

    # Sub-system statuses
    invariant_status = Column(String(32), nullable=False, default="PENDING")
    reconciliation_status = Column(String(32), nullable=False, default="PENDING")

    # Check assertions & evidence
    checks_passed = Column(Text, nullable=True)     # JSON list of check IDs
    checks_failed = Column(Text, nullable=True)     # JSON list of check IDs
    failure_reasons = Column(Text, nullable=True)   # JSON list of strings
    evidence = Column(Text, nullable=True)          # JSON list of structured evidence items

    # Actor & execution metadata
    verified_by = Column(String(64), nullable=False, default="SYSTEM")
    verification_mode = Column(
        String(32),
        nullable=False,
        default=VerificationMode.AUTOMATED.value,
    )
    verification_version = Column(String(32), nullable=False, default="v1")
    attempt_number = Column(Integer, nullable=False, default=1)
    escalation_required = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    exception_record = relationship(
        "ExceptionRecord",
        back_populates="verification_records",
    )
    remediation_action = relationship(
        "RemediationAction",
        back_populates="verification_records",
    )

    __table_args__ = (
        Index("idx_ver_rec_status_created", "verification_status", "created_at"),
        Index("idx_ver_rec_rem_status", "remediation_id", "verification_status"),
    )


class VerificationResult(Base):
    """Legacy verification result model for backward compatibility."""
    __tablename__ = "verification_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    verification_id = Column(String(64), unique=True, nullable=False, index=True)
    exception_id = Column(
        String(64),
        ForeignKey("exceptions.exception_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    action_id = Column(
        String(128),
        ForeignKey("remediation_actions.action_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    started_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(32), nullable=False, default=VerificationStatus.PENDING.value, index=True)
    
    pre_action_state = Column(Text, nullable=True)   # JSON state before action
    post_action_state = Column(Text, nullable=True)  # JSON state after action
    expected_value = Column(String(255), nullable=True)
    actual_value = Column(String(255), nullable=True)
    controls_checked = Column(Text, nullable=True)   # JSON list of controls
    reconciliation_result = Column(Text, nullable=True)  # JSON summary
    failure_reason = Column(Text, nullable=True)

    exception_record = relationship(
        "ExceptionRecord",
        back_populates="verification_results",
    )
    remediation_action = relationship(
        "RemediationAction",
        back_populates="verification_results",
    )

    __table_args__ = (
        Index("idx_verif_status_started", "status", "started_at"),
    )
