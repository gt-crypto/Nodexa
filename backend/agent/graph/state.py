"""Investigation state model tracking pipeline execution context and evidence."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid

from backend.agent.provider import StructuredInvestigationOutput


@dataclass
class InvestigationState:
    """Explicit state representation passed across investigation graph nodes."""
    exception_id: str
    investigation_id: str = field(default_factory=lambda: f"inv_{uuid.uuid4().hex[:16]}")
    current_stage: str = "START"
    exception_record: Optional[Dict[str, Any]] = None
    gathered_evidence: Dict[str, Any] = field(default_factory=dict)
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    contradictions: List[str] = field(default_factory=list)
    hypotheses: List[str] = field(default_factory=list)
    structured_output: Optional[StructuredInvestigationOutput] = None
    tool_call_count: int = 0
    status: str = "CREATED"
    error_message: Optional[str] = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "investigation_id": self.investigation_id,
            "exception_id": self.exception_id,
            "current_stage": self.current_stage,
            "status": self.status,
            "error_message": self.error_message,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "structured_output": self.structured_output.model_dump() if self.structured_output else None,
        }
