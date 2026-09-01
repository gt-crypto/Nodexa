"""Deterministic exception candidate detection engine."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.models.enums import ExceptionType, ExceptionSeverity
from backend.controls.control_result import ControlResult, EvidenceItem
from backend.exceptions.correlator import CorrelatedEntity, correlate_operational_entities
from backend.exceptions.classifiers import (
    ExceptionClassification,
    classify_ghost_settlement,
    classify_refund_chargeback_double_dip,
    classify_settlement_sla_breach,
    classify_legitimate_partial_settlement,
    classify_missing_settlement,
    classify_unallocated_settlement,
    classify_legitimate_timing_exception,
)
from backend.exceptions.severity import SeverityConfig


@dataclass
class DetectedExceptionCandidate:
    """Standardized deterministic exception candidate ready for lifecycle persistence."""
    deduplication_key: str
    exception_type: ExceptionType
    sub_type: Optional[str] = None
    severity: ExceptionSeverity = ExceptionSeverity.LOW
    exposure: int = 0
    description: str = ""
    primary_payment_id: Optional[str] = None
    primary_order_id: Optional[str] = None
    is_legitimate_observation: bool = False
    affected_records: List[tuple[str, str]] = field(default_factory=list)
    evidence_items: List[EvidenceItem] = field(default_factory=list)
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "deduplication_key": self.deduplication_key,
            "exception_type": self.exception_type.value,
            "sub_type": self.sub_type,
            "severity": self.severity.value,
            "exposure": self.exposure,
            "description": self.description,
            "primary_payment_id": self.primary_payment_id,
            "primary_order_id": self.primary_order_id,
            "is_legitimate_observation": self.is_legitimate_observation,
            "affected_records": self.affected_records,
            "evidence_items": [e.to_dict() for e in self.evidence_items],
            "detected_at": self.detected_at.isoformat(),
        }


def build_deduplication_key(classification: ExceptionClassification, entity: CorrelatedEntity) -> str:
    """Generates a deterministic unique key for deduplication across detection runs."""
    type_code = classification.exception_type.value
    if classification.sub_type:
        type_code = classification.sub_type

    entity_id = entity.primary_payment_id or entity.entity_key
    return f"EXC-{type_code}-{entity_id}"


def detect_exception_candidates(
    session: Session,
    control_results: Optional[List[ControlResult]] = None,
    severity_config: Optional[SeverityConfig] = None,
    account_id: str = "nodal_escrow_main",
) -> List[DetectedExceptionCandidate]:
    """Inspects correlated operational records and control findings to detect exception candidates."""
    correlated_map = correlate_operational_entities(
        session=session,
        control_results=control_results,
        account_id=account_id,
    )

    candidates: List[DetectedExceptionCandidate] = []

    for entity_key, entity in correlated_map.items():
        # Evaluate each classifier in deterministic priority order
        cls_result: Optional[ExceptionClassification] = None

        # 1. Ghost Settlement
        cls_result = classify_ghost_settlement(entity, severity_config)

        # 2. Refund + Chargeback Double Dip
        if not cls_result:
            cls_result = classify_refund_chargeback_double_dip(entity, severity_config)

        # 3. Unallocated Settlement (Orphan Inflow)
        if not cls_result:
            cls_result = classify_unallocated_settlement(entity, severity_config)

        # 4. Legitimate Timing Exception (before SLA breach check)
        if not cls_result:
            cls_result = classify_legitimate_timing_exception(entity)

        # 5. Settlement SLA Breach
        if not cls_result:
            cls_result = classify_settlement_sla_breach(entity, severity_config)

        # 6. Legitimate Partial Settlement
        if not cls_result:
            cls_result = classify_legitimate_partial_settlement(entity)

        # 7. Missing Settlement
        if not cls_result:
            cls_result = classify_missing_settlement(entity, severity_config)

        if cls_result:
            dedup_key = build_deduplication_key(cls_result, entity)
            candidate = DetectedExceptionCandidate(
                deduplication_key=dedup_key,
                exception_type=cls_result.exception_type,
                sub_type=cls_result.sub_type,
                severity=cls_result.severity,
                exposure=cls_result.exposure,
                description=cls_result.description,
                primary_payment_id=entity.primary_payment_id,
                primary_order_id=entity.primary_order_id,
                is_legitimate_observation=cls_result.is_legitimate_observation,
                affected_records=entity.all_record_references,
                evidence_items=cls_result.evidence_items,
            )
            candidates.append(candidate)

    return candidates
