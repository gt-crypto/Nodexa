"""Nodexa - Deployment Diagnostics API
Provides health, operational data volume, and finance-ops loop status for deployed instances.
"""
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from backend.models.database import get_db
from backend.models.financial_sources import (
    GatewayTransaction,
    MerchantOrder,
    BankSettlementBatch,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.exceptions import ExceptionRecord
from backend.models.cluster import ExceptionCluster
from backend.models.enums import ExceptionState
from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.evaluation import EvaluationRun
from backend.config import settings

router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])


@router.get("/deployment")
def get_deployment_diagnostics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Return diagnostic telemetry verifying the 50+ synthetic record finance-ops loop.
    
    Verifies that the deployed instance has loaded canonical synthetic operational records,
    detected exceptions, closed the eligible finance-ops loop, and generated benchmark results.
    """
    tx_count = db.scalar(select(func.count(GatewayTransaction.id))) or 0
    order_count = db.scalar(select(func.count(MerchantOrder.id))) or 0
    settlement_count = db.scalar(select(func.count(BankSettlementBatch.id))) or 0
    ledger_count = db.scalar(select(func.count(NodalLedgerEntry.id))) or 0
    dispute_count = db.scalar(select(func.count(DisputeRefundEvent.id))) or 0

    total_exceptions = db.scalar(select(func.count(ExceptionRecord.id))) or 0
    resolved_exceptions = db.scalar(
        select(func.count(ExceptionRecord.id)).where(
            ExceptionRecord.state == ExceptionState.VERIFIED_CLOSED.value
        )
    ) or 0
    unresolved_exceptions = total_exceptions - resolved_exceptions

    clusters_count = db.scalar(select(func.count(ExceptionCluster.id))) or 0
    gt_count = db.scalar(select(func.count(EvaluationGroundTruth.id))) or 0

    # Retrieve latest benchmark run
    latest_eval = db.query(EvaluationRun).order_by(EvaluationRun.created_at.desc()).first()
    benchmark_available = latest_eval is not None
    benchmark_metrics = None
    if latest_eval:
        benchmark_metrics = {
            "evaluation_run_id": latest_eval.evaluation_run_id,
            "overall_score": latest_eval.overall_score,
            "f1_score_pct": round(latest_eval.f1_score / 100.0, 2) if latest_eval.f1_score is not None else 0.0,
            "precision_pct": round(latest_eval.precision / 100.0, 2) if latest_eval.precision is not None else 0.0,
            "recall_pct": round(latest_eval.recall / 100.0, 2) if latest_eval.recall is not None else 0.0,
            "detection_score": latest_eval.detection_score,
            "policy_score": latest_eval.policy_score,
            "safety_score": latest_eval.safety_score,
            "status": latest_eval.status,
            "created_at": latest_eval.created_at.isoformat() if latest_eval.created_at else None,
        }

    operational_total = tx_count + order_count + settlement_count + ledger_count + dispute_count

    return {
        "status": "healthy" if tx_count >= 50 and total_exceptions >= 14 else "degraded",
        "service": "Nodexa AI Finance Controller",
        "environment": settings.environment,
        "database_type": "sqlite" if "sqlite" in settings.database_url else "postgresql",
        "operational_dataset": {
            "gateway_transactions": tx_count,
            "merchant_orders": order_count,
            "settlement_batches": settlement_count,
            "ledger_entries": ledger_count,
            "dispute_events": dispute_count,
            "total_records": operational_total,
            "meets_50_plus_requirement": tx_count >= 50,
        },
        "finance_ops_loop": {
            "total_exceptions_detected": total_exceptions,
            "resolved_verified_closed": resolved_exceptions,
            "unresolved_or_escalated": unresolved_exceptions,
            "closure_rate_pct": round((resolved_exceptions / total_exceptions * 100), 2) if total_exceptions > 0 else 0.0,
            "pattern_clusters_discovered": clusters_count,
        },
        "benchmark": {
            "available": benchmark_available,
            "ground_truth_cases": gt_count,
            "latest_run": benchmark_metrics,
        },
    }
