"""Repository for Evaluation Runs and Evaluation Cases."""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.evaluation import EvaluationRun, EvaluationCase


class EvaluationRepository:
    """Provides structured data access for benchmark evaluation runs and cases."""

    def __init__(self, session: Session):
        self.session = session

    def create_evaluation_run(self, run: EvaluationRun) -> EvaluationRun:
        """Stores a new evaluation run record."""
        self.session.add(run)
        self.session.flush()
        return run

    def get_evaluation_run(self, evaluation_run_id: str) -> Optional[EvaluationRun]:
        """Retrieves an evaluation run by its unique evaluation_run_id."""
        stmt = select(EvaluationRun).where(EvaluationRun.evaluation_run_id == evaluation_run_id)
        return self.session.scalars(stmt).first()

    def get_latest_run_for_dataset(
        self,
        dataset_id: str,
        benchmark_version: Optional[str] = None,
    ) -> Optional[EvaluationRun]:
        """Retrieves the most recent completed evaluation run for a dataset."""
        stmt = (
            select(EvaluationRun)
            .where(EvaluationRun.dataset_id == dataset_id)
        )
        if benchmark_version:
            stmt = stmt.where(EvaluationRun.benchmark_version == benchmark_version)
        stmt = stmt.order_by(EvaluationRun.created_at.desc(), EvaluationRun.id.desc())
        return self.session.scalars(stmt).first()

    def get_latest_benchmark_run(self) -> Optional[EvaluationRun]:
        """Retrieves the most recent completed evaluation run in the entire system."""
        stmt = (
            select(EvaluationRun)
            .order_by(EvaluationRun.created_at.desc(), EvaluationRun.id.desc())
        )
        return self.session.scalars(stmt).first()

    def list_evaluation_runs(self, limit: int = 50, offset: int = 0) -> List[EvaluationRun]:
        """Retrieves a list of evaluation runs ordered by created_at descending."""
        stmt = (
            select(EvaluationRun)
            .order_by(EvaluationRun.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def save_cases(self, cases: List[EvaluationCase]) -> List[EvaluationCase]:
        """Bulk adds evaluation cases."""
        self.session.add_all(cases)
        self.session.flush()
        return cases

    def get_cases_for_run(
        self,
        evaluation_run_id: str,
        match_status: Optional[str] = None,
    ) -> List[EvaluationCase]:
        """Retrieves all cases associated with an evaluation run."""
        stmt = select(EvaluationCase).where(EvaluationCase.evaluation_run_id == evaluation_run_id)
        if match_status:
            stmt = stmt.where(EvaluationCase.match_status == match_status)
        stmt = stmt.order_by(EvaluationCase.id.asc())
        return list(self.session.scalars(stmt).all())
