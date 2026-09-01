"""Repository for Audit Events.

Enforces strictly append-only audit logging with no delete or update interfaces.
"""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.audit import AuditEvent


class AuditRepository:
    """Provides append-only data access for immutable audit logs."""

    def __init__(self, session: Session):
        self.session = session

    def append_audit_event(self, event: AuditEvent) -> AuditEvent:
        """Appends an immutable audit event to the audit trail."""
        self.session.add(event)
        self.session.flush()
        return event

    def get_audit_event(self, audit_event_id: str) -> Optional[AuditEvent]:
        """Retrieves a specific audit event by its audit_event_id."""
        stmt = select(AuditEvent).where(AuditEvent.audit_event_id == audit_event_id)
        return self.session.scalars(stmt).first()

    def list_events_for_exception(self, exception_id: str) -> List[AuditEvent]:
        """Retrieves all audit events associated with an exception."""
        stmt = select(AuditEvent).where(AuditEvent.exception_id == exception_id).order_by(AuditEvent.timestamp.asc())
        return list(self.session.scalars(stmt).all())

    def list_recent_events(self, limit: int = 100) -> List[AuditEvent]:
        """Lists the most recent audit events across the platform."""
        stmt = select(AuditEvent).order_by(AuditEvent.timestamp.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())
