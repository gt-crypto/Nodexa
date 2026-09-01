"""Abstract base handler for safe remediation execution."""
from abc import ABC, abstractmethod
from typing import Any, Dict, Tuple
from sqlalchemy.orm import Session

from backend.models.remediation import RemediationAction


class BaseActionHandler(ABC):
    """Base interface for dedicated remediation action handlers."""

    @abstractmethod
    def execute(
        self,
        session: Session,
        plan: RemediationAction,
        parameters: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
        """Executes the remediation action transactionally, returning (before_state, after_state, summary)."""
        pass

    @abstractmethod
    def dry_run(
        self,
        session: Session,
        plan: RemediationAction,
        parameters: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Simulates action execution without committing database mutations."""
        pass
