"""Confidence calibration database model for tracking empirical calibration snapshots."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    Float,
    String,
    Text,
    DateTime,
    Boolean,
    Index,
)
from backend.models.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ConfidenceCalibrationSnapshot(Base):
    """Stores immutable, deterministic snapshots of confidence calibration evaluations."""

    __tablename__ = "confidence_calibration_snapshots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    snapshot_id = Column(String(64), unique=True, nullable=False, index=True)
    prediction_type_filter = Column(String(64), nullable=True, index=True)
    source_filter = Column(String(32), nullable=True, index=True)
    status = Column(String(32), nullable=False, index=True)  # CALIBRATED, PARTIALLY_CALIBRATED, INSUFFICIENT_DATA, NOT_CALIBRATABLE
    
    total_predictions = Column(Integer, nullable=False, default=0)
    evaluated_predictions = Column(Integer, nullable=False, default=0)
    unevaluated_predictions = Column(Integer, nullable=False, default=0)
    correct_predictions = Column(Integer, nullable=False, default=0)
    
    coverage = Column(Float, nullable=True)
    correctness_rate = Column(Float, nullable=True)
    
    # JSON strings
    confidence_buckets = Column(Text, nullable=False)  # HIGH, MEDIUM, LOW bucket metrics
    numerical_metrics = Column(Text, nullable=True)  # Brier score, ECE, reliability bins (or null with reason)
    source_breakdown = Column(Text, nullable=False)  # seeded vs live-injected counts
    insufficiency_reasons = Column(Text, nullable=True)  # list of reasons if INSUFFICIENT_DATA
    
    methodology_version = Column(String(32), nullable=False, default="v1.0.0")
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    __table_args__ = (
        Index("idx_calib_status_created", "status", "created_at"),
        Index("idx_calib_pred_type", "prediction_type_filter", "created_at"),
    )
