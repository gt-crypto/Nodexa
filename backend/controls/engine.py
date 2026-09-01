"""Deterministic Control Engine Orchestrator for Nodal Sentinel.

Executes all financial invariants, reconciliation, settlement SLA, and balance controls,
producing structured, immutable facts and evidence for downstream consumption.
"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.controls.control_result import ControlResult, ControlStatus
from backend.controls.settlement_sla import SettlementSLAConfig
from backend.controls.nodal_health import (
    NodalHealthConfig,
    NodalHealthSummary,
    evaluate_nodal_health,
)
from backend.reconciliation.service import ReconciliationService
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)


@dataclass
class DeterministicControlReport:
    """Consolidated report containing all deterministic control findings and health status."""
    evaluated_at: datetime
    account_id: str
    nodal_health: NodalHealthSummary
    control_results: List[ControlResult]
    total_controls: int
    passed_count: int
    warning_count: int
    failed_count: int
    not_applicable_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evaluated_at": self.evaluated_at.isoformat(),
            "account_id": self.account_id,
            "nodal_health": self.nodal_health.to_dict(),
            "total_controls": self.total_controls,
            "passed_count": self.passed_count,
            "warning_count": self.warning_count,
            "failed_count": self.failed_count,
            "not_applicable_count": self.not_applicable_count,
            "control_results": [c.to_dict() for c in self.control_results],
        }


class ControlEngine:
    """Pure deterministic finance controller engine."""

    def __init__(
        self,
        sla_config: Optional[SettlementSLAConfig] = None,
        health_config: Optional[NodalHealthConfig] = None,
    ):
        self.sla_config = sla_config or SettlementSLAConfig()
        self.health_config = health_config or NodalHealthConfig()

    def run_all_controls(
        self,
        session: Session,
        account_id: str = "nodal_escrow_main",
        current_time: Optional[datetime] = None,
    ) -> DeterministicControlReport:
        """Executes all deterministic financial controls and invariants across the dataset."""
        recon_service = ReconciliationService(session=session, sla_config=self.sla_config)
        all_results: List[ControlResult] = []

        # 1. Account & Ledger Level Invariants & Reconciliations
        account_recon = recon_service.reconcile_account(account_id=account_id)
        all_results.extend(account_recon.control_results)

        # 2. Payment-Level Reconciliations & SLAs
        payments = list(session.scalars(select(GatewayTransaction)).all())
        for p in payments:
            pmt_recon = recon_service.reconcile_payment(p.payment_id, current_time=current_time)
            if pmt_recon:
                all_results.extend(pmt_recon.control_results)

        # 3. Unallocated Settlement Checks
        settlements = list(session.scalars(select(BankSettlementBatch)).all())
        for s in settlements:
            if not s.payment_id:
                settle_recon = recon_service.reconcile_settlement(s.settlement_id)
                if settle_recon:
                    all_results.extend(settle_recon.control_results)

        # Count statuses
        passed_count = sum(1 for c in all_results if c.status == ControlStatus.PASS)
        warning_count = sum(1 for c in all_results if c.status == ControlStatus.WARNING)
        failed_count = sum(1 for c in all_results if c.status == ControlStatus.FAIL)
        na_count = sum(1 for c in all_results if c.status == ControlStatus.NOT_APPLICABLE)
        critical_failures = sum(1 for c in all_results if c.status == ControlStatus.FAIL and c.severity == "CRITICAL")

        # 4. Evaluate Nodal Health
        health_summary = evaluate_nodal_health(
            session=session,
            account_id=account_id,
            config=self.health_config,
            critical_control_failures_count=critical_failures,
            warning_control_failures_count=warning_count,
        )

        now = datetime.now(timezone.utc)
        return DeterministicControlReport(
            evaluated_at=now,
            account_id=account_id,
            nodal_health=health_summary,
            control_results=all_results,
            total_controls=len(all_results),
            passed_count=passed_count,
            warning_count=warning_count,
            failed_count=failed_count,
            not_applicable_count=na_count,
        )
