"""Evaluation ground truth model.

CRITICAL: Ground truth is logically separated from operational financial source data.
The future AI investigator must NEVER receive direct access to this table.
This table exists solely for benchmark evaluation and automated accuracy scoring.
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    DateTime,
    Index,
)

from backend.models.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class EvaluationGroundTruth(Base):
    """Ground truth benchmark cases for evaluating AI investigation accuracy."""
    __tablename__ = "evaluation_ground_truth"

    id = Column(Integer, primary_key=True, autoincrement=True)
    case_id = Column(String(64), unique=True, nullable=False, index=True)
    anomaly_type = Column(String(64), nullable=False, index=True)
    expected_root_cause = Column(String(512), nullable=False, index=True)
    
    # Expected exposure stored as integer minor units
    expected_exposure = Column(BigInteger, nullable=False)
    expected_resolution_class = Column(String(128), nullable=False)
    expected_verification_state = Column(String(128), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    __table_args__ = (
        Index("idx_gt_anomaly_root_cause", "anomaly_type", "expected_root_cause"),
    )
