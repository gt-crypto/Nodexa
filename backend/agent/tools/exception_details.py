"""Read-only exception record and lifecycle details lookup tool for AI investigator."""
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.services.repositories.exception_repository import ExceptionRepository


def lookup_exception_details(session: Session, exception_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves full details of an exception, including affected records and lifecycle state history."""
    repo = ExceptionRepository(session)
    exc = repo.get_exception(exception_id)
    if not exc:
        return None

    aff_records = repo.get_affected_records(exception_id)
    transitions = repo.get_state_transitions(exception_id)

    return {
        "source": "exceptions",
        "exception_id": exc.exception_id,
        "exception_type": exc.exception_type,
        "severity": exc.severity,
        "state": exc.state,
        "exposure": exc.exposure,
        "confidence": float(exc.confidence) if exc.confidence else 1.0,
        "description": exc.description,
        "primary_payment_id": exc.primary_payment_id,
        "primary_order_id": exc.primary_order_id,
        "detected_at": exc.detected_at.isoformat() if exc.detected_at else None,
        "affected_records": [
            {
                "record_type": a.record_type,
                "record_identifier": a.record_identifier,
            }
            for a in aff_records
        ],
        "state_transitions": [
            {
                "transition_id": t.transition_id,
                "from_state": t.from_state,
                "to_state": t.to_state,
                "timestamp": t.timestamp.isoformat() if t.timestamp else None,
                "actor_type": t.actor_type,
                "reason": t.reason,
            }
            for t in transitions
        ],
    }
