"""Canonical clean seed and startup initialization service for Nodexa demo database.

Ensures the canonical synthetic baseline is deterministically populated:
- 60 Gateway Transactions (50+ record synthetic batch requirement)
- 60 Merchant Orders, 62 Settlement Batches, 76 Ledger Entries, 14 Dispute Events
- 14 canonical detected exceptions
- Full finance-ops loop closed on eligible cases (1 verified closed, 13 honestly unresolved/escalated)
- 10 pattern clusters discovered by pattern miner
- Baseline benchmark evaluation run with real measured match rate
- Fully idempotent: checks existing counts to prevent duplicate records
- Robust PostgreSQL & SQLite compatibility with staged commits and savepoint isolation
"""
import sys
from typing import Dict, Any
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from backend.models.database import engine, SessionLocal, reset_db
from backend.models.enums import (
    ExceptionType,
    ExceptionState,
    PolicyActionType,
    RemediationStatus,
    VerificationStatus,
)
from backend.models.exceptions import ExceptionRecord, ExceptionStateTransition, ExceptionAffectedRecord
from backend.models.cluster import ExceptionCluster
from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.injected_cases import InjectedCase
from backend.models.financial_sources import (
    GatewayTransaction,
    MerchantOrder,
    BankSettlementBatch,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.evaluation import EvaluationRun, EvaluationCase
from backend.models.remediation import RemediationAction
from backend.models.verification import VerificationRecord
from backend.models.investigation import InvestigationRun
from backend.models.risk import RiskAssessment
from backend.models.policy import PolicyDecisionRecord
from backend.data.generator.service import generate_dataset
from backend.controls.engine import ControlEngine
from backend.exceptions.service import ExceptionDetectionService
from backend.agent.service import InvestigationService
from backend.exposure.service import RiskAssessmentService
from backend.policy.service import PolicyService
from backend.remediation.service import RemediationService
from backend.verification.service import VerificationService
from backend.patterns.miner import PatternMinerService
from backend.evaluation.service import BenchmarkEvaluationService
from backend.evaluation.models import EvaluationRunRequest
from backend.logging import logger


from backend.models.audit import AuditEvent
from backend.models.escalation import EscalationWebhookDelivery
from sqlalchemy import text


def clear_operational_data(db: Session) -> None:
    """Safely clears all operational and analytical tables without foreign key violations."""
    target_engine = db.get_bind()
    is_sqlite = str(target_engine.url).startswith("sqlite")
    if is_sqlite:
        for model in [
            EvaluationCase,
            EvaluationRun,
            VerificationRecord,
            RemediationAction,
            PolicyDecisionRecord,
            RiskAssessment,
            InvestigationRun,
            EscalationWebhookDelivery,
            AuditEvent,
            ExceptionStateTransition,
            ExceptionAffectedRecord,
            ExceptionRecord,
            ExceptionCluster,
            EvaluationGroundTruth,
            DisputeRefundEvent,
            BankSettlementBatch,
            MerchantOrder,
            NodalLedgerEntry,
            GatewayTransaction,
        ]:
            try:
                db.query(model).delete()
            except Exception:
                pass
        db.commit()
    else:
        # In PostgreSQL, TRUNCATE ... CASCADE cleanly empties all tables and dependents instantly
        try:
            db.execute(
                text(
                    "TRUNCATE TABLE "
                    "evaluation_cases, evaluation_runs, verification_records, remediation_actions, "
                    "policy_decisions, risk_assessments, investigation_runs, audit_events, "
                    "escalation_webhook_deliveries, exception_state_transitions, exception_affected_records, "
                    "exceptions, exception_clusters, evaluation_ground_truth, "
                    "dispute_refund_events, bank_settlement_batches, merchant_orders, nodal_ledger_entries, "
                    "gateway_transactions CASCADE;"
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            for table_name in [
                "evaluation_cases", "evaluation_runs", "verification_records", "remediation_actions",
                "policy_decisions", "risk_assessments", "investigation_runs", "audit_events",
                "escalation_webhook_deliveries", "exception_state_transitions", "exception_affected_records",
                "exceptions", "exception_clusters", "evaluation_ground_truth",
                "dispute_refund_events", "bank_settlement_batches", "merchant_orders", "nodal_ledger_entries",
                "gateway_transactions"
            ]:
                try:
                    with db.begin_nested():
                        db.execute(text(f"DELETE FROM {table_name}"))
                except Exception:
                    pass
            db.commit()


def ensure_canonical_seed(db: Session, force_reset: bool = False) -> Dict[str, Any]:
    """Idempotently ensures the canonical synthetic dataset is populated and processed.
    
    If the database already contains >= 50 transactions and >= 14 exceptions,
    it returns the existing operational summary without duplicating records.
    Otherwise, it populates Seed 42, executes controls, closes the loop, and persists.
    """
    if not force_reset:
        tx_count = db.scalar(select(func.count(GatewayTransaction.id))) or 0
        exc_count = db.scalar(select(func.count(ExceptionRecord.id))) or 0
        eval_count = db.scalar(select(func.count(EvaluationRun.id))) or 0
        resolved_count = db.scalar(
            select(func.count(ExceptionRecord.id)).where(ExceptionRecord.state == ExceptionState.VERIFIED_CLOSED.value)
        ) or 0

        if tx_count >= 50 and exc_count >= 14 and resolved_count >= 1 and eval_count > 0:
            logger.info(
                operation="STARTUP_SEED_CHECK",
                message="Canonical synthetic dataset already initialized with closed finance-ops loop. Skipping re-seed.",
                details={"gateway_transactions": tx_count, "exceptions": exc_count, "resolved": resolved_count, "evaluations": eval_count},
            )
            clusters_count = db.scalar(select(func.count(ExceptionCluster.id))) or 0
            gt_count = db.scalar(select(func.count(EvaluationGroundTruth.id))) or 0

            return {
                "status": "ALREADY_INITIALIZED",
                "gateway_transactions_count": tx_count,
                "exceptions_total": exc_count,
                "exceptions_resolved": resolved_count,
                "exceptions_unresolved": exc_count - resolved_count,
                "ground_truth_count": gt_count,
                "benchmark_available": eval_count > 0,
            }

    # Clear existing partial data to ensure clean foreign-key insertion without unique-key collisions
    logger.info(operation="CANONICAL_SEED_PREPARE", message="Purging partial/stale operational data before seeding...")
    clear_operational_data(db)

    # 1. Generate Canonical Synthetic Financial Dataset (Seed 42, 60 TXs)
    logger.info(operation="CANONICAL_SEED", message="Generating canonical synthetic dataset (Seed 42, 60 TXs)...")
    gen_result = generate_dataset(session=db, record_count=60, seed=42, reset_existing=False)
    dataset_id = gen_result["dataset_id"]
    db.commit()

    # 2. Deterministic Controls & Exception Detection
    control_engine = ControlEngine()
    control_engine.run_all_controls(session=db)
    db.commit()

    detection_service = ExceptionDetectionService()
    det_report = detection_service.detect_exceptions(session=db, dataset_id=dataset_id)
    db.commit()

    # 3. AI Investigation on Detected Exceptions (with savepoint isolation)
    agent_service = InvestigationService()
    for exc in det_report.exceptions:
        try:
            with db.begin_nested():
                agent_service.investigate_exception(session=db, exception_id=exc["exception_id"])
        except Exception as e:
            logger.warning(operation="INVESTIGATION_SKIP", message=f"Investigation skipped for {exc['exception_id']}: {e}")
    db.commit()

    # 4. Risk Assessment Prioritization
    risk_service = RiskAssessmentService()
    risk_service.assess_all_open_exceptions(session=db)
    db.commit()

    # 5. Policy Gating (with savepoint isolation)
    policy_service = PolicyService()
    for exc in det_report.exceptions:
        try:
            with db.begin_nested():
                policy_service.evaluate_policy(
                    session=db,
                    exception_id=exc["exception_id"],
                    requested_action="INVESTIGATE",
                )
        except Exception:
            pass
    db.commit()

    # 6. Close Finance-Ops Loop for 1 Eligible Exception (Remediation + Dual Approval + Verification)
    ghost_exc = next(
        (e for e in det_report.exceptions if e["exception_type"] == ExceptionType.GHOST_SETTLEMENT.value),
        None,
    )
    if ghost_exc:
        rem_service = RemediationService()
        ver_service = VerificationService()

        # Plan refund remediation
        plan = rem_service.create_remediation_plan(
            session=db,
            exception_id=ghost_exc["exception_id"],
            action=PolicyActionType.REFUND.value,
            parameters={
                "payment_id": ghost_exc["primary_payment_id"],
                "amount_minor_units": ghost_exc["exposure"],
                "reason": "Refund unauthorized ghost settlement credit",
            },
            requested_by="operator-alice",
        )
        db.commit()

        # Dual-controller approval (separation of duties: bob != alice)
        if plan.approval_required:
            rem_service.approve_remediation(
                session=db,
                action_id=plan.action_id,
                approved_by="controller-bob",
                decision="APPROVED",
                reason="Approved after ledger and bank reconciliation review",
            )
            db.commit()

        # Execute remediation
        rem_service.execute_remediation(session=db, action_id=plan.action_id)
        db.commit()

        # Independent post-remediation verification
        ver_service.verify_remediation(session=db, remediation_id=plan.action_id)
        db.commit()

    # 7. Pattern Miner
    miner = PatternMinerService(min_cluster_size=2)
    clusters = miner.mine_patterns(db, persist=True)
    db.commit()

    # 8. Baseline Benchmark Evaluation
    eval_service = BenchmarkEvaluationService()
    bench_result = eval_service.run_benchmark(
        session=db,
        request=EvaluationRunRequest(dataset_id=dataset_id, force_rerun=True),
    )
    db.commit()

    # Query final verification audit counts
    gt_count = db.scalar(select(func.count(EvaluationGroundTruth.id))) or 0
    exc_count = db.scalar(select(func.count(ExceptionRecord.id))) or 0
    tx_count = db.scalar(select(func.count(GatewayTransaction.id))) or 0
    resolved_count = db.scalar(
        select(func.count(ExceptionRecord.id)).where(ExceptionRecord.state == ExceptionState.VERIFIED_CLOSED.value)
    ) or 0
    unresolved_count = exc_count - resolved_count

    summary = {
        "dataset_id": dataset_id,
        "ground_truth_count": gt_count,
        "exceptions_total": exc_count,
        "exceptions_resolved": resolved_count,
        "exceptions_unresolved": unresolved_count,
        "gateway_transactions_count": tx_count,
        "clusters_count": len(clusters),
        "benchmark_precision": bench_result.run.precision,
        "benchmark_recall": bench_result.run.recall,
        "benchmark_f1": bench_result.run.f1_score,
        "overall_benchmark_score": bench_result.run.overall_score,
        "total_exposure_identified": bench_result.exposure_accuracy.total_predicted_exposure,
    }

    logger.info(
        operation="STARTUP_SEED_COMPLETE",
        message=f"Canonical baseline populated: {tx_count} TXs, {exc_count} exceptions ({resolved_count} resolved, {unresolved_count} unresolved), {len(clusters)} clusters",
        details=summary,
    )
    return summary


def seed_canonical_database() -> Dict[str, Any]:
    """Resets the demo database and deterministically populates the clean canonical baseline."""
    db = SessionLocal()
    try:
        return ensure_canonical_seed(db, force_reset=True)
    finally:
        db.close()


if __name__ == "__main__":
    try:
        res = seed_canonical_database()
        print("Demo database clean canonical initialization successful!")
        print(f"Summary: {res}")
    except Exception as e:
        print(f"Error seeding canonical database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
