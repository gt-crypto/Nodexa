"""Deterministic Exception Detection & Lifecycle Engine for Nodal Sentinel."""
from backend.exceptions.exposure import calculate_exception_exposure
from backend.exceptions.severity import assign_exception_severity, SeverityConfig
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
from backend.exceptions.detector import (
    DetectedExceptionCandidate,
    detect_exception_candidates,
    build_deduplication_key,
)
from backend.exceptions.lifecycle import persist_detected_exception
from backend.exceptions.service import ExceptionDetectionService, DetectionReport

__all__ = [
    "calculate_exception_exposure",
    "assign_exception_severity",
    "SeverityConfig",
    "CorrelatedEntity",
    "correlate_operational_entities",
    "ExceptionClassification",
    "classify_ghost_settlement",
    "classify_refund_chargeback_double_dip",
    "classify_settlement_sla_breach",
    "classify_legitimate_partial_settlement",
    "classify_missing_settlement",
    "classify_unallocated_settlement",
    "classify_legitimate_timing_exception",
    "DetectedExceptionCandidate",
    "detect_exception_candidates",
    "build_deduplication_key",
    "persist_detected_exception",
    "ExceptionDetectionService",
    "DetectionReport",
]
