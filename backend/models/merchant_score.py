"""Merchant Trust & Impact Score model."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    DateTime,
    Index,
)

from backend.models.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class MerchantScore(Base):
    """Deterministic, read-only analytics model summarizing merchant behavior."""
    __tablename__ = "merchant_scores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(String(64), unique=True, nullable=False, index=True)
    
    trust_score = Column(Integer, nullable=False)
    impact_score = Column(Integer, nullable=False)
    score_band = Column(String(32), nullable=False)  # EXCELLENT, HEALTHY, WATCH, HIGH_RISK, CRITICAL
    
    # Raw deterministic metrics
    exception_count = Column(Integer, nullable=False, default=0)
    actionable_exception_count = Column(Integer, nullable=False, default=0)
    legitimate_exception_count = Column(Integer, nullable=False, default=0)
    high_risk_exception_count = Column(Integer, nullable=False, default=0)
    total_exposure = Column(BigInteger, nullable=False, default=0)
    recurring_pattern_count = Column(Integer, nullable=False, default=0)
    
    # Source separation
    seeded_case_count = Column(Integer, nullable=False, default=0)
    live_injected_case_count = Column(Integer, nullable=False, default=0)
    
    # Overall transaction denominators where available
    total_transaction_count = Column(Integer, nullable=False, default=0)
    total_transaction_volume = Column(BigInteger, nullable=False, default=0)
    
    # Explainability
    scoring_version = Column(String(32), nullable=False)
    score_factors = Column(Text, nullable=False)  # JSON array of structured factor objects
    
    # Lifespan
    first_seen = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("idx_merchant_score_band", "score_band"),
    )
