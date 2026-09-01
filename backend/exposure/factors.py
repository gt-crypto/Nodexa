"""Deterministic risk factor extraction from operational records, controls, and investigations."""
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.exceptions import ExceptionRecord, ExceptionAffectedRecord
from backend.models.investigation import InvestigationRun
from backend.models.enums import ExceptionType
from backend.exposure.models import RiskFactors


def extract_risk_factors(
    session: Session,
    exception: ExceptionRecord,
    investigation_run: Optional[InvestigationRun] = None,
) -> RiskFactors:
    """Extracts structured deterministic risk factors for an exception."""
    now = datetime.now(timezone.utc)
    
    # 1. Financial exposure & severity
    exposure_amount = exception.exposure or 0
    severity_level = exception.severity or "LOW"

    # 2. Affected records complexity
    aff_count = len(exception.affected_records) if exception.affected_records else (
        len(list(session.scalars(select(ExceptionAffectedRecord).where(ExceptionAffectedRecord.exception_id == exception.exception_id)).all()))
    )

    # 3. Investigation confidence
    confidence_str: Optional[str] = None
    if investigation_run:
        conf_val = float(investigation_run.confidence) if investigation_run.confidence else 1.0
        if conf_val >= 0.9:
            confidence_str = "HIGH"
        elif conf_val >= 0.6:
            confidence_str = "MEDIUM"
        else:
            confidence_str = "LOW"

    # 4. Domain specific indicators
    is_sla_breach = (exception.exception_type == ExceptionType.SETTLEMENT_SLA_BREACH.value)
    is_ghost = (exception.exception_type == ExceptionType.GHOST_SETTLEMENT.value)
    is_double_dip = (exception.exception_type == ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value)
    is_unallocated = ("UNALLOCATED" in exception.exception_id) or (exception.primary_payment_id is None)

    # 5. Control failure count proxy
    control_failure_count = 1
    if is_ghost or is_double_dip:
        control_failure_count = 2
    if is_unallocated:
        control_failure_count = 2

    # 6. Time elapsed since detection
    det_at = exception.detected_at
    if det_at.tzinfo is None:
        det_at = det_at.replace(tzinfo=timezone.utc)
    age_mins = max(0, int((now - det_at).total_seconds() // 60))

    return RiskFactors(
        exposure_amount=exposure_amount,
        severity_level=severity_level,
        control_failure_count=control_failure_count,
        investigation_confidence=confidence_str,
        affected_record_count=max(1, aff_count),
        sla_breached=is_sla_breach,
        ledger_contradiction=is_ghost,
        is_unallocated=is_unallocated,
        is_double_dip=is_double_dip,
        age_minutes=age_mins,
    )
