"""High-level AI Investigation Service managing exception analysis runs and history."""
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.models.investigation import InvestigationRun
from backend.services.repositories.investigation_repository import InvestigationRepository
from backend.agent.graph.investigator import InvestigationGraph
from backend.agent.provider import LLMProvider


class InvestigationService:
    """High-level service interface for orchestrating AI investigations."""

    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.graph = InvestigationGraph(llm_provider=llm_provider)

    def investigate_exception(
        self,
        session: Session,
        exception_id: str,
        reinvestigate: bool = False,
    ) -> Dict[str, Any]:
        """Runs the investigation graph on a specific exception and returns structured analysis."""
        state = self.graph.run(session=session, exception_id=exception_id, reinvestigate=reinvestigate)
        session.commit()
        return state.to_dict()

    def list_investigations_for_exception(
        self,
        session: Session,
        exception_id: str,
    ) -> List[InvestigationRun]:
        """Retrieves all past investigation runs for an exception."""
        repo = InvestigationRepository(session)
        return repo.list_runs_for_exception(exception_id)

    def get_investigation(
        self,
        session: Session,
        investigation_id: str,
    ) -> Optional[InvestigationRun]:
        """Retrieves a specific investigation run by ID."""
        repo = InvestigationRepository(session)
        return repo.get_investigation_run(investigation_id)
