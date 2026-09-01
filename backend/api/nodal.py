"""Nodal Account Health & Deterministic Financial Controls API."""
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from backend.models.database import get_db
from backend.models.exceptions import ExceptionRecord
from backend.models.financial_sources import GatewayTransaction, BankSettlementBatch
from backend.controls.engine import ControlEngine
from backend.controls.control_result import ControlStatus
from backend.controls.settlement_sla import SLATimingStatus, evaluate_settlement_sla

router = APIRouter(tags=["Nodal Health"])


class SettlementThroughputResponse(BaseModel):
    total_captured_payments_count: int
    total_captured_amount: int
    total_settled_payments_count: int
    total_settled_amount: int
    total_unsettled_payments_count: int
    total_unsettled_amount: int
    settlement_completion_ratio: float
    settlement_batches_count: int
    total_net_settlement_amount: int


class SettlementSLAHealthResponse(BaseModel):
    within_sla_count: int
    late_but_valid_count: int
    sla_breach_count: int
    not_applicable_count: int


class ControlsSummaryResponse(BaseModel):
    total_controls_evaluated: int
    passed_count: int
    warning_count: int
    failed_count: int
    not_applicable_count: int


class NodalHealthResponse(BaseModel):
    overall_status: str = Field(description="HEALTHY, WARNING, or CRITICAL")
    account_id: str
    expected_balance: int = Field(description="Expected balance in integer minor units (paisa)")
    actual_balance: int = Field(description="Actual balance in integer minor units (paisa)")
    variance: int = Field(description="Actual balance - Expected balance (minor units)")
    absolute_variance: int = Field(description="Absolute variance in integer minor units (paisa)")
    settlement_throughput: SettlementThroughputResponse
    settlement_sla_health: SettlementSLAHealthResponse
    open_exception_count: int = Field(
        description="Count of open exceptions in database (0 until exception engine is active)"
    )
    total_exposure: int = Field(
        description="Sum of exposure from database exceptions in minor units (0 until exception engine is active)"
    )
    controls_summary: ControlsSummaryResponse
    reasons: List[str] = Field(default_factory=list)
    evaluated_at: str


@router.get("/health/nodal", response_model=NodalHealthResponse)
def get_nodal_health(
    account_id: str = Query(default="nodal_escrow_main", description="Nodal account identifier"),
    db: Session = Depends(get_db),
) -> NodalHealthResponse:
    """Returns real-time deterministic nodal account health, balance variance, and SLA metrics."""
    engine = ControlEngine()
    report = engine.run_all_controls(session=db, account_id=account_id)

    # Calculate SLA health breakdown
    payments = list(db.scalars(select(GatewayTransaction)).all())
    settlements = list(db.scalars(select(BankSettlementBatch)).all())

    within_sla = 0
    late_valid = 0
    sla_breach = 0
    na_sla = 0

    for p in payments:
        sla_res = evaluate_settlement_sla(p, settlements, config=engine.sla_config)
        timing_status = sla_res.calculated_values.get("timing_status")
        if timing_status == SLATimingStatus.WITHIN_SLA.value:
            within_sla += 1
        elif timing_status == SLATimingStatus.LATE_BUT_VALID.value:
            late_valid += 1
        elif timing_status in (SLATimingStatus.SLA_BREACH.value, SLATimingStatus.MISSING.value):
            sla_breach += 1
        else:
            na_sla += 1

    # Query honest exceptions and exposure from database (Prompt 3 requirement: no fake numbers)
    open_exceptions_stmt = select(func.count(ExceptionRecord.id))
    total_exposure_stmt = select(func.coalesce(func.sum(ExceptionRecord.exposure), 0))
    
    open_exception_count = db.scalar(open_exceptions_stmt) or 0
    total_exposure = db.scalar(total_exposure_stmt) or 0

    return NodalHealthResponse(
        overall_status=report.nodal_health.overall_status.value,
        account_id=account_id,
        expected_balance=report.nodal_health.expected_balance,
        actual_balance=report.nodal_health.actual_balance,
        variance=report.nodal_health.variance,
        absolute_variance=report.nodal_health.absolute_variance,
        settlement_throughput=SettlementThroughputResponse(
            total_captured_payments_count=report.nodal_health.throughput.total_captured_payments_count,
            total_captured_amount=report.nodal_health.throughput.total_captured_amount,
            total_settled_payments_count=report.nodal_health.throughput.total_settled_payments_count,
            total_settled_amount=report.nodal_health.throughput.total_settled_amount,
            total_unsettled_payments_count=report.nodal_health.throughput.total_unsettled_payments_count,
            total_unsettled_amount=report.nodal_health.throughput.total_unsettled_amount,
            settlement_completion_ratio=report.nodal_health.throughput.settlement_completion_ratio,
            settlement_batches_count=report.nodal_health.throughput.settlement_batches_count,
            total_net_settlement_amount=report.nodal_health.throughput.total_net_settlement_amount,
        ),
        settlement_sla_health=SettlementSLAHealthResponse(
            within_sla_count=within_sla,
            late_but_valid_count=late_valid,
            sla_breach_count=sla_breach,
            not_applicable_count=na_sla,
        ),
        open_exception_count=open_exception_count,
        total_exposure=total_exposure,
        controls_summary=ControlsSummaryResponse(
            total_controls_evaluated=report.total_controls,
            passed_count=report.passed_count,
            warning_count=report.warning_count,
            failed_count=report.failed_count,
            not_applicable_count=report.not_applicable_count,
        ),
        reasons=report.nodal_health.reasons,
        evaluated_at=report.evaluated_at.isoformat(),
    )
