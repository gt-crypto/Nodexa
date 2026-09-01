"""Structured internal representation for deterministic control results and evidence."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ControlStatus(str, Enum):
    """Possible evaluation statuses for deterministic controls."""
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    NOT_APPLICABLE = "NOT_APPLICABLE"


@dataclass
class EvidenceItem:
    """Individual piece of structured operational evidence supporting a control finding."""
    source: str  # e.g., 'gateway_transactions', 'bank_settlement_batches', 'nodal_ledger'
    record_id: Optional[str] = None  # e.g., 'PAY-000001', 'SET-000001'
    field: str = ""  # e.g., 'amount', 'status', 'clearing_timestamp'
    value: Any = None  # e.g., 1000000, 'CAPTURED'
    comparison: Optional[str] = None  # e.g., 'expected 1000000 == actual 1000000'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "record_id": self.record_id,
            "field": self.field,
            "value": self.value,
            "comparison": self.comparison,
        }


@dataclass
class ControlResult:
    """Standardized deterministic control evaluation result."""
    control_id: str
    control_name: str
    status: ControlStatus
    severity: Optional[str] = None  # LOW, MEDIUM, HIGH, CRITICAL, or None
    affected_record_ids: List[str] = field(default_factory=list)
    calculated_values: Dict[str, Any] = field(default_factory=dict)
    expected_values: Dict[str, Any] = field(default_factory=dict)
    actual_values: Dict[str, Any] = field(default_factory=dict)
    evidence: List[EvidenceItem] = field(default_factory=list)
    rule: str = ""
    evaluated_at: datetime = field(default_factory=utc_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "control_id": self.control_id,
            "control_name": self.control_name,
            "status": self.status.value if isinstance(self.status, ControlStatus) else str(self.status),
            "severity": self.severity,
            "affected_record_ids": self.affected_record_ids,
            "calculated_values": self.calculated_values,
            "expected_values": self.expected_values,
            "actual_values": self.actual_values,
            "evidence": [e.to_dict() for e in self.evidence],
            "rule": self.rule,
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
        }
