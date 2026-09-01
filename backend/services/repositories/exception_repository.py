"""Repository for Exception records, state transitions, and affected record associations."""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.exceptions import (
    ExceptionRecord,
    ExceptionStateTransition,
    ExceptionAffectedRecord,
)


class ExceptionRepository:
    """Provides structured data access for exception tracking."""

    def __init__(self, session: Session):
        self.session = session

    def create_exception(self, exception: ExceptionRecord) -> ExceptionRecord:
        """Creates a new exception record."""
        self.session.add(exception)
        self.session.flush()
        return exception

    def get_exception(self, exception_id: str) -> Optional[ExceptionRecord]:
        """Retrieves an exception record by its business exception_id."""
        stmt = select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)
        return self.session.scalars(stmt).first()

    def list_exceptions(
        self,
        state: Optional[str] = None,
        exception_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ExceptionRecord]:
        """Lists exception records with optional filters."""
        stmt = select(ExceptionRecord)
        if state:
            stmt = stmt.where(ExceptionRecord.state == state)
        if exception_type:
            stmt = stmt.where(ExceptionRecord.exception_type == exception_type)
        stmt = stmt.order_by(ExceptionRecord.detected_at.desc()).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    def add_affected_record(self, affected_record: ExceptionAffectedRecord) -> ExceptionAffectedRecord:
        """Links an affected financial record to an exception."""
        self.session.add(affected_record)
        self.session.flush()
        return affected_record

    def get_affected_records(self, exception_id: str) -> List[ExceptionAffectedRecord]:
        """Retrieves all affected financial records linked to an exception."""
        stmt = select(ExceptionAffectedRecord).where(ExceptionAffectedRecord.exception_id == exception_id)
        return list(self.session.scalars(stmt).all())

    def get_state_transitions(self, exception_id: str) -> List[ExceptionStateTransition]:
        """Retrieves the full immutable transition history of an exception."""
        stmt = select(ExceptionStateTransition).where(ExceptionStateTransition.exception_id == exception_id).order_by(ExceptionStateTransition.timestamp.asc())
        return list(self.session.scalars(stmt).all())
