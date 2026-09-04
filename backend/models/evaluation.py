"""Evaluation run and case database models.

CRITICAL: Ground truth is logically separated from operational financial source data.
Evaluation models record benchmark performance, accuracy metrics, confusion matrices,
and case-level scoring without modifying operational financial data.
"""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from backend.models.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class EvaluationRun(Base):
    """Represents a full benchmark evaluation run execution over a dataset."""
    __tablename__ = "evaluation_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    evaluation_run_id = Column(String(64), unique=True, nullable=False, index=True)
    dataset_id = Column(String(64), nullable=False, index=True)
    benchmark_version = Column(String(32), nullable=False, default="1.0.0")
    system_version = Column(String(32), nullable=False, default="1.0.0")
    status = Column(String(32), nullable=False, default="RUNNING", index=True)

    # Core Metrics
    total_ground_truth_cases = Column(Integer, nullable=False, default=0)
    total_predictions = Column(Integer, nullable=False, default=0)
    true_positives = Column(Integer, nullable=False, default=0)
    false_positives = Column(Integer, nullable=False, default=0)
    false_negatives = Column(Integer, nullable=False, default=0)

    # Integer basis points (e.g. 10000 = 100.00%)
    precision = Column(Integer, nullable=False, default=0)
    recall = Column(Integer, nullable=False, default=0)
    f1_score = Column(Integer, nullable=False, default=0)
    overall_score = Column(Integer, nullable=False, default=0)

    # Component Scores (0 to 100)
    detection_score = Column(Integer, nullable=False, default=0)
    investigation_score = Column(Integer, nullable=False, default=0)
    financial_score = Column(Integer, nullable=False, default=0)
    risk_score = Column(Integer, nullable=False, default=0)
    policy_score = Column(Integer, nullable=False, default=0)
    remediation_score = Column(Integer, nullable=False, default=0)
    verification_score = Column(Integer, nullable=False, default=0)
    safety_score = Column(Integer, nullable=False, default=0)

    # Safety Gating
    safety_status = Column(String(32), nullable=False, default="PASSED")
    critical_safety_failure = Column(Boolean, nullable=False, default=False)
    safety_failure_reasons = Column(Text, nullable=True)

    # Structured JSON Report
    summary_report = Column(Text, nullable=True)

    started_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    cases = relationship(
        "EvaluationCase",
        back_populates="evaluation_run",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("idx_eval_run_dataset", "dataset_id", "created_at"),
        Index("idx_eval_run_status", "status", "created_at"),
    )


class EvaluationCase(Base):
    """Case-level ground truth vs predicted comparison record."""
    __tablename__ = "evaluation_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    evaluation_case_id = Column(String(64), unique=True, nullable=False, index=True)
    evaluation_run_id = Column(
        String(64),
        ForeignKey("evaluation_runs.evaluation_run_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ground_truth_case_id = Column(String(64), nullable=True, index=True)
    predicted_exception_id = Column(String(64), nullable=True, index=True)
    match_status = Column(String(64), nullable=False, index=True)

    # Matching Details
    matched_by = Column(String(64), nullable=True)
    matched_identifier = Column(String(128), nullable=True)

    # Predictions vs Expected
    expected_exception_type = Column(String(64), nullable=True)
    predicted_exception_type = Column(String(64), nullable=True)

    expected_root_cause = Column(String(512), nullable=True)
    predicted_root_cause = Column(String(512), nullable=True)

    # Financial Exposure (paise minor units)
    expected_exposure = Column(BigInteger, nullable=False, default=0)
    predicted_exposure = Column(BigInteger, nullable=False, default=0)
    exposure_error = Column(BigInteger, nullable=False, default=0)

    expected_severity = Column(String(32), nullable=True)
    predicted_severity = Column(String(32), nullable=True)

    expected_priority = Column(String(32), nullable=True)
    predicted_priority = Column(String(32), nullable=True)

    expected_resolution_class = Column(String(128), nullable=True)
    predicted_resolution_class = Column(String(128), nullable=True)

    expected_policy_decision = Column(String(64), nullable=True)
    predicted_policy_decision = Column(String(64), nullable=True)

    remediation_result = Column(String(64), nullable=True)
    verification_result = Column(String(64), nullable=True)

    is_false_closure = Column(Boolean, nullable=False, default=False)
    is_legitimate_case = Column(Boolean, nullable=False, default=False)

    # JSON strings
    error_categories = Column(Text, nullable=True)
    details = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)

    evaluation_run = relationship(
        "EvaluationRun",
        back_populates="cases",
    )

    __table_args__ = (
        Index("idx_eval_case_run_match", "evaluation_run_id", "match_status"),
        Index("idx_eval_case_gt_pred", "ground_truth_case_id", "predicted_exception_id"),
    )
