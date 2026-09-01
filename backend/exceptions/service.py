"""Deterministic Exception Detection Service orchestrating control execution, candidate detection, and persistence."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.controls.engine import ControlEngine
from backend.models.dataset import DatasetMetadata
from backend.exceptions.detector import detect_exception_candidates, DetectedExceptionCandidate
from backend.exceptions.lifecycle import persist_detected_exception
from backend.exceptions.severity import SeverityConfig


@dataclass
class DetectionReport:
    """Consolidated report output from an exception detection run."""
    dataset_id: Optional[str]
    evaluated_at: datetime
    controls_run_count: int
    findings_count: int
    total_detected_count: int
    new_exception_count: int
    existing_exception_count: int
    legitimate_case_count: int
    total_exposure: int
    severity_breakdown: Dict[str, int]
    exception_type_breakdown: Dict[str, int]
    exceptions: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "evaluated_at": self.evaluated_at.isoformat(),
            "controls_run_count": self.controls_run_count,
            "findings_count": self.findings_count,
            "total_detected_count": self.total_detected_count,
            "new_exception_count": self.new_exception_count,
            "existing_exception_count": self.existing_exception_count,
            "legitimate_case_count": self.legitimate_case_count,
            "total_exposure": self.total_exposure,
            "severity_breakdown": self.severity_breakdown,
            "exception_type_breakdown": self.exception_type_breakdown,
            "exceptions": self.exceptions,
        }


class ExceptionDetectionService:
    """High-level service managing deterministic exception detection and lifecycle persistence."""

    def __init__(self, severity_config: Optional[SeverityConfig] = None):
        self.severity_config = severity_config or SeverityConfig()
        self.control_engine = ControlEngine()

    def detect_exceptions(
        self,
        session: Session,
        account_id: str = "nodal_escrow_main",
        dataset_id: Optional[str] = None,
    ) -> DetectionReport:
        """Executes full deterministic detection workflow across operational records and persists findings."""
        # Retrieve latest dataset_id if not provided
        if not dataset_id:
            latest_ds = session.scalars(select(DatasetMetadata).order_by(DatasetMetadata.generated_at.desc())).first()
            if latest_ds:
                dataset_id = latest_ds.dataset_id

        # 1. Run deterministic controls
        control_report = self.control_engine.run_all_controls(session, account_id=account_id)

        # 2. Detect exception candidates
        candidates = detect_exception_candidates(
            session=session,
            control_results=control_report.control_results,
            severity_config=self.severity_config,
            account_id=account_id,
        )

        new_count = 0
        existing_count = 0
        legitimate_count = 0
        total_exposure = 0
        severity_counts: Dict[str, int] = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        type_counts: Dict[str, int] = {}
        persisted_summaries: List[Dict[str, Any]] = []

        # 3. Persist each candidate deterministically
        for cand in candidates:
            rec, is_new = persist_detected_exception(session, cand)
            if is_new:
                new_count += 1
            else:
                existing_count += 1

            if cand.is_legitimate_observation:
                legitimate_count += 1

            total_exposure += cand.exposure
            severity_counts[cand.severity.value] = severity_counts.get(cand.severity.value, 0) + 1
            type_counts[cand.exception_type.value] = type_counts.get(cand.exception_type.value, 0) + 1

            persisted_summaries.append({
                "exception_id": rec.exception_id,
                "exception_type": rec.exception_type,
                "sub_type": cand.sub_type,
                "severity": rec.severity,
                "state": rec.state,
                "exposure": rec.exposure,
                "is_legitimate_observation": cand.is_legitimate_observation,
                "primary_payment_id": rec.primary_payment_id,
                "primary_order_id": rec.primary_order_id,
                "description": rec.description,
                "affected_records": cand.affected_records,
                "evidence": [e.to_dict() for e in cand.evidence_items],
                "detected_at": rec.detected_at.isoformat() if rec.detected_at else None,
            })

        session.flush()

        now = datetime.now(timezone.utc)
        return DetectionReport(
            dataset_id=dataset_id,
            evaluated_at=now,
            controls_run_count=control_report.total_controls,
            findings_count=control_report.failed_count + control_report.warning_count,
            total_detected_count=len(candidates),
            new_exception_count=new_count,
            existing_exception_count=existing_count,
            legitimate_case_count=legitimate_count,
            total_exposure=total_exposure,
            severity_breakdown=severity_counts,
            exception_type_breakdown=type_counts,
            exceptions=persisted_summaries,
        )
