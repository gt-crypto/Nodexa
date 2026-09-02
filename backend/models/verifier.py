"""Adversarial Verifier opinion database model."""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship

from backend.models.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class VerifierOpinion(Base):
    """Immutable audit record storing independent adversarial verifier opinions on exception decisions."""

    __tablename__ = "verifier_opinions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    opinion_id = Column(String(64), unique=True, nullable=False, index=True)
    exception_id = Column(
        String(64),
        ForeignKey("exceptions.exception_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    verdict = Column(String(32), nullable=False, index=True)  # AGREE, TIGHTEN, DISPUTE, ABSTAIN
    confidence = Column(String(16), nullable=False, default="HIGH")  # HIGH, MEDIUM, LOW
    reasoning_summary = Column(Text, nullable=False)
    evidence_refs = Column(Text, nullable=False, default="[]")  # JSON encoded list of evidence IDs
    recommended_action = Column(String(64), nullable=False)  # ALLOW_REMEDIATION, HUMAN_REVIEW, BLOCK, etc.
    original_policy_decision = Column(String(64), nullable=False)
    final_policy_decision = Column(String(64), nullable=False)
    verifier_version = Column(String(32), nullable=False, default="v2.0")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    # Relationships
    exception_record = relationship(
        "ExceptionRecord",
        back_populates="verifier_opinions",
    )

    __table_args__ = (
        Index("idx_verifier_exc_created", "exception_id", "created_at"),
        Index("idx_verifier_verdict", "verdict"),
    )
