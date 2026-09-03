"""Predictive Nodal Drift Radar persistence model."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Index,
)
from backend.models.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class DriftPrediction(Base):
    """Persisted snapshot of deterministic nodal operational drift predictions."""
    __tablename__ = "drift_predictions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prediction_id = Column(String(64), unique=True, nullable=False, index=True)
    nodal_account_id = Column(String(64), nullable=False, default="nodal_escrow_main", index=True)
    prediction_timestamp = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    observation_window = Column(Text, nullable=False)  # JSON: baseline_start, baseline_end, current_start, current_end
    horizon = Column(String(32), nullable=False, default="NEXT_SETTLEMENT_CYCLE")
    drift_score = Column(Integer, nullable=False)  # 0 to 100
    risk_band = Column(String(32), nullable=False)  # STABLE, WATCH, ELEVATED, HIGH_DRIFT
    direction = Column(String(32), nullable=False)  # IMPROVING, STABLE, DETERIORATING, INSUFFICIENT_DATA
    confidence = Column(String(32), nullable=False)  # LOW, MEDIUM, HIGH
    predicted_dimension = Column(String(64), nullable=False, default="OPERATIONAL_HEALTH")
    
    contributing_signals = Column(Text, nullable=False, default="[]")  # JSON: list of signals with contribution, delta
    baseline_metrics = Column(Text, nullable=False, default="{}")  # JSON: baseline counts, exposure, etc.
    current_metrics = Column(Text, nullable=False, default="{}")  # JSON: current counts, exposure, etc.
    delta_metrics = Column(Text, nullable=False, default="{}")  # JSON: differences and percentages
    evidence_ids = Column(Text, nullable=False, default="[]")  # JSON: list of exception_ids cited
    source_metadata = Column(Text, nullable=False, default="{}")  # JSON: seeded_count, live_injected_count
    scoring_version = Column(String(32), nullable=False, default="v1.0.0")
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("idx_drift_account_time", "nodal_account_id", "prediction_timestamp"),
        Index("idx_drift_risk_band", "risk_band"),
    )
