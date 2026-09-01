"""Account-level risk aggregation and deterministic top-risk queue prioritization."""
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from backend.models.enums import ExceptionState, PriorityLevel, ExceptionSeverity
from backend.models.exceptions import ExceptionRecord
from backend.models.risk import RiskAssessment
from backend.models.investigation import InvestigationRun
from backend.exposure.models import (
    RiskQueueItemResponse,
    AccountRiskSummaryResponse,
    TopExposureItem,
    TopRiskItem,
)


PRIORITY_RANK = {
    PriorityLevel.P1.value: 4,
    PriorityLevel.P2.value: 3,
    PriorityLevel.P3.value: 2,
    PriorityLevel.P4.value: 1,
}

SEVERITY_RANK = {
    ExceptionSeverity.CRITICAL.value: 4,
    ExceptionSeverity.HIGH.value: 3,
    ExceptionSeverity.MEDIUM.value: 2,
    ExceptionSeverity.LOW.value: 1,
}


def get_prioritized_risk_queue(
    session: Session,
    priority: Optional[str] = None,
    severity: Optional[str] = None,
    materiality: Optional[str] = None,
    exception_type: Optional[str] = None,
    min_exposure: Optional[int] = None,
    max_exposure: Optional[int] = None,
    escalation: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> Tuple[List[RiskQueueItemResponse], int]:
    """Retrieves prioritized exception queue with explicit multi-level tie breaking."""
    stmt = (
        select(ExceptionRecord, RiskAssessment, InvestigationRun)
        .outerjoin(RiskAssessment, RiskAssessment.exception_id == ExceptionRecord.exception_id)
        .outerjoin(InvestigationRun, InvestigationRun.exception_id == ExceptionRecord.exception_id)
        .where(ExceptionRecord.state.notin_([ExceptionState.VERIFIED_CLOSED.value]))
    )

    if priority:
        stmt = stmt.where(RiskAssessment.priority == priority)
    if severity:
        stmt = stmt.where(ExceptionRecord.severity == severity)
    if materiality:
        stmt = stmt.where(RiskAssessment.materiality == materiality)
    if exception_type:
        stmt = stmt.where(ExceptionRecord.exception_type == exception_type)
    if min_exposure is not None:
        stmt = stmt.where(ExceptionRecord.exposure >= min_exposure)
    if max_exposure is not None:
        stmt = stmt.where(ExceptionRecord.exposure <= max_exposure)
    if escalation:
        stmt = stmt.where(RiskAssessment.escalation == escalation)

    rows = session.execute(stmt).all()

    # De-duplicate rows by exception_id (taking latest assessment/run)
    exc_map: Dict[str, Tuple[ExceptionRecord, Optional[RiskAssessment], Optional[InvestigationRun]]] = {}
    for exc, ra, inv in rows:
        if exc.exception_id not in exc_map or (ra and ra.calculated_at > (exc_map[exc.exception_id][1].calculated_at if exc_map[exc.exception_id][1] else exc.detected_at)):
            exc_map[exc.exception_id] = (exc, ra, inv)

    unique_items = list(exc_map.values())
    total_count = len(unique_items)

    # Deterministic 5-level tie breaking:
    # 1. priority (P1 > P2 > P3 > P4)
    # 2. risk_score DESC
    # 3. exposure DESC
    # 4. severity (CRITICAL > HIGH > MEDIUM > LOW)
    # 5. detected_at ASC (older first)
    def sort_key(item):
        exc, ra, _ = item
        p_val = ra.priority if ra else "P4"
        p_rank = PRIORITY_RANK.get(p_val, 1)
        r_score = ra.risk_score if ra else 0
        exp_val = exc.exposure or 0
        s_rank = SEVERITY_RANK.get(exc.severity, 1)
        det_ts = exc.detected_at.timestamp() if exc.detected_at else 0.0
        return (-p_rank, -r_score, -exp_val, -s_rank, det_ts)

    unique_items.sort(key=sort_key)

    paginated = unique_items[offset : offset + limit]

    result: List[RiskQueueItemResponse] = []
    for exc, ra, inv in paginated:
        result.append(
            RiskQueueItemResponse(
                exception_id=exc.exception_id,
                exception_type=exc.exception_type,
                severity=exc.severity,
                exposure=exc.exposure,
                materiality=ra.materiality if ra else "NONE",
                risk_score=ra.risk_score if ra else 0,
                priority=ra.priority if ra else "P4",
                escalation=ra.escalation if ra else "NO_ESCALATION",
                root_cause_category=inv.final_classification if inv else None,
                investigation_confidence=float(inv.confidence) if inv and inv.confidence else None,
                detected_at=exc.detected_at.isoformat() if exc.detected_at else "",
            )
        )

    return result, total_count


def get_account_risk_summary(
    session: Session,
    account_id: str = "nodal_escrow_main",
) -> AccountRiskSummaryResponse:
    """Aggregates account-level risk exposure, concentration, and priority counts."""
    queue_items, total_count = get_prioritized_risk_queue(session, limit=1000)

    total_open_exposure = sum(item.exposure for item in queue_items)
    total_material_exposure = sum(
        item.exposure for item in queue_items if item.materiality in ("HIGH", "MATERIAL", "SEVERE")
    )

    p1_cnt = sum(1 for item in queue_items if item.priority == PriorityLevel.P1.value)
    p2_cnt = sum(1 for item in queue_items if item.priority == PriorityLevel.P2.value)
    p3_cnt = sum(1 for item in queue_items if item.priority == PriorityLevel.P3.value)
    p4_cnt = sum(1 for item in queue_items if item.priority == PriorityLevel.P4.value)

    highest_risk_id = queue_items[0].exception_id if queue_items else None
    highest_risk_score = queue_items[0].risk_score if queue_items else 0

    # Top 5 by exposure
    sorted_by_exp = sorted(queue_items, key=lambda x: x.exposure, reverse=True)[:5]
    top_exposure = [
        TopExposureItem(
            exception_id=i.exception_id,
            exception_type=i.exception_type,
            exposure=i.exposure,
            priority=i.priority,
            risk_score=i.risk_score,
        )
        for i in sorted_by_exp
    ]

    # Top 5 by risk score
    sorted_by_risk = sorted(queue_items, key=lambda x: x.risk_score, reverse=True)[:5]
    top_risk = [
        TopRiskItem(
            exception_id=i.exception_id,
            exception_type=i.exception_type,
            risk_score=i.risk_score,
            priority=i.priority,
            exposure=i.exposure,
        )
        for i in sorted_by_risk
    ]

    # Concentration of top 3 exposures in basis points
    top3_sum = sum(i.exposure for i in sorted_by_exp[:3])
    concentration_bps = (top3_sum * 10000) // total_open_exposure if total_open_exposure > 0 else 0

    return AccountRiskSummaryResponse(
        account_id=account_id,
        total_open_exposure=total_open_exposure,
        total_material_exposure=total_material_exposure,
        total_exceptions_count=total_count,
        p1_count=p1_cnt,
        p2_count=p2_cnt,
        p3_count=p3_cnt,
        p4_count=p4_cnt,
        highest_risk_exception_id=highest_risk_id,
        highest_risk_score=highest_risk_score,
        top_exposure_exceptions=top_exposure,
        top_risk_exceptions=top_risk,
        exposure_concentration_top3_bps=min(10000, max(0, concentration_bps)),
    )
