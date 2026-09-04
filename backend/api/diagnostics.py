"""Nodexa - Deployment Diagnostics API
Provides health, operational data volume, and finance-ops loop status for deployed instances.
Includes on-demand self-healing seed initialization and complete diagnostic error exposure.
"""
import traceback
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, Query
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
from backend.data.seed_clean import ensure_canonical_seed
from backend.config import settings
from backend.logging import logger

router = APIRouter(prefix="/diagnostics", tags=["Diagnostics"])


@router.get("/deployment")
def get_deployment_diagnostics(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Return diagnostic telemetry verifying the 50+ synthetic record finance-ops loop.
    
    Verifies that the deployed instance has loaded canonical synthetic operational records,
    detected exceptions, closed the eligible finance-ops loop, and generated benchmark results.
    If the operational database is empty on cold start, it automatically executes the canonical
    seeder and self-heals before returning.
    """
    from backend.main import get_startup_error

    initialization_error: Optional[Dict[str, Any]] = get_startup_error()

    try:
        tx_count = db.scalar(select(func.count(GatewayTransaction.id))) or 0
        total_exceptions = db.scalar(select(func.count(ExceptionRecord.id))) or 0

        # Self-healing on-demand seed trigger: if operational tables are empty, initialize them now!
        if tx_count < 50 or total_exceptions < 14:
            try:
                logger.info(
                    operation="DIAGNOSTIC_SELF_HEAL",
                    message="Operational records below threshold. Executing canonical synthetic seed...",
                    details={"existing_tx": tx_count, "existing_exceptions": total_exceptions},
                )
                seed_summary = ensure_canonical_seed(db)
                db.commit()
                logger.info(
                    operation="DIAGNOSTIC_SELF_HEAL_SUCCESS",
                    message="Canonical seed self-healing complete.",
                    details=seed_summary,
                )
                initialization_error = None
            except Exception as seed_err:
                db.rollback()
                tb = traceback.format_exc()
                logger.error(
                    operation="DIAGNOSTIC_SELF_HEAL_FAILED",
                    message=f"On-demand seed failed: {str(seed_err)}",
                    details={"error": str(seed_err), "traceback": tb},
                )
                initialization_error = {
                    "error": str(seed_err),
                    "type": type(seed_err).__name__,
                    "traceback": tb,
                }

        # Query latest operational state
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
        is_healthy = tx_count >= 50 and total_exceptions >= 14 and resolved_exceptions >= 1 and benchmark_available

        payload: Dict[str, Any] = {
            "status": "healthy" if is_healthy else "degraded",
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

        if initialization_error:
            payload["initialization_error"] = initialization_error

        return payload

    except Exception as exc:
        db.rollback()
        tb = traceback.format_exc()
        return {
            "status": "degraded",
            "service": "Nodexa AI Finance Controller",
            "environment": settings.environment,
            "database_type": "sqlite" if "sqlite" in settings.database_url else "postgresql",
            "operational_dataset": {
                "gateway_transactions": 0,
                "merchant_orders": 0,
                "settlement_batches": 0,
                "ledger_entries": 0,
                "dispute_events": 0,
                "total_records": 0,
                "meets_50_plus_requirement": False,
            },
            "finance_ops_loop": {
                "total_exceptions_detected": 0,
                "resolved_verified_closed": 0,
                "unresolved_or_escalated": 0,
                "closure_rate_pct": 0.0,
                "pattern_clusters_discovered": 0,
            },
            "benchmark": {
                "available": False,
                "ground_truth_cases": 0,
                "latest_run": None,
            },
            "initialization_error": {
                "error": str(exc),
                "type": type(exc).__name__,
                "traceback": tb,
            },
        }

    return payload


@router.post("/seed")
def trigger_canonical_seed(
    force_reset: bool = Query(False, description="Whether to purge and re-seed the canonical dataset"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Explicit endpoint to trigger or force-reinitialize the canonical synthetic seed."""
    try:
        summary = ensure_canonical_seed(db, force_reset=force_reset)
        db.commit()
        return {
            "status": "SUCCESS",
            "message": "Canonical dataset successfully seeded and processed.",
            "summary": summary,
        }
    except Exception as e:
        db.rollback()
        tb = traceback.format_exc()
        logger.error(
            operation="MANUAL_SEED_ERROR",
            message=f"Manual seed trigger failed: {str(e)}",
            details={"error": str(e), "traceback": tb},
        )
        return {
            "status": "FAILED",
            "error": str(e),
            "type": type(e).__name__,
            "traceback": tb,
        }
