"""Ground Truth reader module for the benchmark evaluation layer.

CRITICAL: Only code inside backend/evaluation/ may import and use this module.
Operational components (controls, detection, investigation, risk, policy, remediation,
verification) MUST NEVER query or import this module.
"""
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.ground_truth import EvaluationGroundTruth


class GroundTruthReader:
    """Isolated read-only access layer for evaluation ground truth records."""

    @staticmethod
    def list_ground_truth_cases(session: Session) -> List[EvaluationGroundTruth]:
        """Retrieves all benchmark ground truth cases from the database."""
        stmt = select(EvaluationGroundTruth).order_by(EvaluationGroundTruth.id.asc())
        return list(session.scalars(stmt).all())

    @staticmethod
    def get_ground_truth_case(session: Session, case_id: str) -> Optional[EvaluationGroundTruth]:
        """Retrieves a single ground truth case by its case_id."""
        stmt = select(EvaluationGroundTruth).where(EvaluationGroundTruth.case_id == case_id)
        return session.scalars(stmt).first()

    @staticmethod
    def count_ground_truth_cases(session: Session) -> int:
        """Returns total count of ground truth cases."""
        cases = GroundTruthReader.list_ground_truth_cases(session)
        return len(cases)
