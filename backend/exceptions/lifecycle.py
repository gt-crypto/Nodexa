"""Deterministic exception lifecycle, deduplication persistence, and audit logging."""
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import ExceptionState, TransitionActorType
from backend.models.exceptions import ExceptionRecord, ExceptionStateTransition, ExceptionAffectedRecord
from backend.models.audit import AuditEvent
from backend.services.repositories.audit_repository import AuditRepository
from backend.exceptions.detector import DetectedExceptionCandidate


def persist_detected_exception(
    session: Session,
    candidate: DetectedExceptionCandidate,
) -> Tuple[ExceptionRecord, bool]:
    """Persists a detected exception candidate with idempotency, state transitions, affected records, and audit logs.
    
    Returns:
    - (ExceptionRecord, is_new: bool)
    """
    stmt = select(ExceptionRecord).where(ExceptionRecord.exception_id == candidate.deduplication_key)
    existing = session.scalars(stmt).first()

    now = datetime.now(timezone.utc)

    if existing:
        # Idempotent update of existing exception record
        existing.exposure = candidate.exposure
        existing.severity = candidate.severity.value
        existing.description = candidate.description
        existing.updated_at = now
        session.flush()
        return existing, False

    # 1. Create New Exception Record
    new_record = ExceptionRecord(
        exception_id=candidate.deduplication_key,
        exception_type=candidate.exception_type.value,
        severity=candidate.severity.value,
        state=ExceptionState.DETECTED.value,
        exposure=candidate.exposure,
        confidence=Decimal("1.0000"),
        description=candidate.description,
        primary_payment_id=candidate.primary_payment_id,
        primary_order_id=candidate.primary_order_id,
        detected_at=candidate.detected_at,
        created_at=candidate.detected_at,
        updated_at=now,
    )
    session.add(new_record)
    session.flush()

    # 2. Persist Initial Lifecycle State Transition
    transition = ExceptionStateTransition(
        transition_id=f"trans_{uuid.uuid4().hex[:16]}",
        exception_id=new_record.exception_id,
        from_state="NONE",
        to_state=ExceptionState.DETECTED.value,
        timestamp=now,
        reason="Deterministic exception detected from operational controls.",
        actor_type=TransitionActorType.SYSTEM.value,
        actor_id="deterministic_detection_engine",
    )
    session.add(transition)

    # 3. Persist Affected Records Linkages
    for rec_type, rec_id in candidate.affected_records:
        aff = ExceptionAffectedRecord(
            exception_id=new_record.exception_id,
            record_type=rec_type,
            record_identifier=rec_id,
        )
        session.add(aff)

    # 4. Persist Audit Event
    audit_repo = AuditRepository(session)
    audit_payload = {
        "exception_id": new_record.exception_id,
        "exception_type": new_record.exception_type,
        "sub_type": candidate.sub_type,
        "severity": new_record.severity,
        "exposure": new_record.exposure,
        "is_legitimate_observation": candidate.is_legitimate_observation,
        "primary_payment_id": new_record.primary_payment_id,
        "evidence": [e.to_dict() for e in candidate.evidence_items],
    }
    audit_event = AuditEvent(
        audit_event_id=f"audit_{uuid.uuid4().hex[:16]}",
        exception_id=new_record.exception_id,
        event_type="EXCEPTION_DETECTED",
        timestamp=now,
        actor_type=TransitionActorType.SYSTEM.value,
        actor_id="deterministic_detection_engine",
        event_summary=f"Deterministic detection: {new_record.exception_type} on {new_record.primary_payment_id or new_record.exception_id}",
        event_payload=json.dumps(audit_payload),
    )
    audit_repo.append_audit_event(audit_event)

    session.flush()
    return new_record, True
