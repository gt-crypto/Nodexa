"""Repository for Evaluation Ground Truth.

CRITICAL: Logically isolated from operational financial repositories.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.ground_truth import EvaluationGroundTruth


class GroundTruthRepository:
    """Provides isolated data access for evaluation ground truth benchmark cases."""

    def __init__(self, session: Session):
        self.session = session

    def save_ground_truth(self, case: EvaluationGroundTruth) -> EvaluationGroundTruth:
        """Stores a ground truth evaluation benchmark case."""
        self.session.add(case)
        self.session.flush()
        return case

    def get_ground_truth(self, case_id: str) -> Optional[EvaluationGroundTruth]:
        """Retrieves a ground truth case by its case_id."""
        stmt = select(EvaluationGroundTruth).where(EvaluationGroundTruth.case_id == case_id)
        return self.session.scalars(stmt).first()

    def list_cases(self, anomaly_type: Optional[str] = None, limit: int = 100) -> List[EvaluationGroundTruth]:
        """Lists ground truth cases with optional anomaly type filtering."""
        stmt = select(EvaluationGroundTruth)
        if anomaly_type:
            stmt = stmt.where(EvaluationGroundTruth.anomaly_type == anomaly_type)
        stmt = stmt.order_by(EvaluationGroundTruth.created_at.asc()).limit(limit)
        return list(self.session.scalars(stmt).all())
