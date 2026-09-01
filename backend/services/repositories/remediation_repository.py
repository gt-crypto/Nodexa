"""Repository for Remediation Actions."""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.remediation import RemediationAction


class RemediationRepository:
    """Provides structured data access for remediation actions."""

    def __init__(self, session: Session):
        self.session = session

    def create_action(self, action: RemediationAction) -> RemediationAction:
        """Proposes a new remediation action."""
        self.session.add(action)
        self.session.flush()
        return action

    def get_action(self, action_id: str) -> Optional[RemediationAction]:
        """Retrieves a remediation action by its business action_id."""
        stmt = select(RemediationAction).where(RemediationAction.action_id == action_id)
        return self.session.scalars(stmt).first()

    def list_actions_for_exception(self, exception_id: str) -> List[RemediationAction]:
        """Retrieves all remediation actions linked to an exception."""
        stmt = select(RemediationAction).where(RemediationAction.exception_id == exception_id).order_by(RemediationAction.requested_at.desc())
        return list(self.session.scalars(stmt).all())
