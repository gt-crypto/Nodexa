"""Repository for AI Investigation Runs."""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.investigation import InvestigationRun


class InvestigationRepository:
    """Provides structured data access for AI investigation runs."""

    def __init__(self, session: Session):
        self.session = session

    def create_investigation_run(self, run: InvestigationRun) -> InvestigationRun:
        """Creates a new investigation run entry."""
        self.session.add(run)
        self.session.flush()
        return run

    def get_investigation_run(self, investigation_id: str) -> Optional[InvestigationRun]:
        """Retrieves an investigation run by its business investigation_id."""
        stmt = select(InvestigationRun).where(InvestigationRun.investigation_id == investigation_id)
        return self.session.scalars(stmt).first()

    def list_runs_for_exception(self, exception_id: str) -> List[InvestigationRun]:
        """Lists all investigation runs executed for a given exception."""
        stmt = select(InvestigationRun).where(InvestigationRun.exception_id == exception_id).order_by(InvestigationRun.created_at.desc())
        return list(self.session.scalars(stmt).all())
