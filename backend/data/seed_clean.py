"""Canonical clean seed script for Nodal Sentinel demo database.

Wipes old test artifacts and development injection history, then deterministically
rebuilds the pristine canonical baseline:
- 14 ground-truth benchmark cases in evaluation_ground_truth
- 14 canonical detected seeded exceptions in exceptions
- Baseline pattern clusters
- Baseline benchmark evaluation run
- 0 test-created artifacts
- 0 historical live-injected records
"""
import sys
from typing import Dict, Any
from sqlalchemy import select, func

from backend.models.database import engine, SessionLocal, reset_db
from backend.models.exceptions import ExceptionRecord
from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.injected_cases import InjectedCase
from backend.models.financial_sources import (
    GatewayTransaction,
    MerchantOrder,
    BankSettlementBatch,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.dataset import DatasetMetadata
from backend.data.generator.service import generate_dataset
from backend.exceptions.service import ExceptionDetectionService
from backend.patterns.miner import PatternMinerService
from backend.evaluation.service import BenchmarkEvaluationService
from backend.evaluation.models import EvaluationRunRequest


def seed_canonical_database() -> Dict[str, Any]:
    """Resets the demo database and deterministically populates the clean canonical baseline."""
    print("Step 1: Resetting database schema on nodal_sentinel.db...")
    reset_db(custom_engine=engine)

    db = SessionLocal()
    try:
        print("Step 2: Deterministically generating canonical synthetic dataset (Seed 42, 60 TXs)...")
        gen_result = generate_dataset(session=db, record_count=60, seed=42, reset_existing=False)
        dataset_id = gen_result["dataset_id"]
        print(f"   Generated dataset ID: {dataset_id}")
        print(f"   Financial records: {gen_result['total_financial_records']}")
        print(f"   Planted ground-truth cases: {gen_result['counts']['ground_truth_cases']}")

        print("Step 3: Running invariant control engine and exception detection...")
        detection_service = ExceptionDetectionService()
        det_report = detection_service.detect_exceptions(session=db, dataset_id=dataset_id)
        print(f"   Total exceptions detected: {det_report.total_detected_count}")
        print(f"   Total exposure surfaced: INR {det_report.total_exposure / 100:,.2f}")

        print("Step 4: Running Pattern Miner on clean baseline...")
        miner = PatternMinerService(min_cluster_size=2)
        clusters = miner.mine_patterns(db, persist=True)
        print(f"   Canonical recurring pattern clusters: {len(clusters)}")

        print("Step 5: Executing initial baseline benchmark evaluation...")
        eval_service = BenchmarkEvaluationService()
        bench_result = eval_service.run_benchmark(
            session=db,
            request=EvaluationRunRequest(dataset_id=dataset_id, force_rerun=True),
        )
        print(f"   Benchmark Precision: {bench_result.run.precision:.2%}")
        print(f"   Benchmark Recall: {bench_result.run.recall:.2%}")
        print(f"   Benchmark F1 Score: {bench_result.run.f1_score:.2%}")
        print(f"   Overall Score: {bench_result.run.overall_score:.2%}")

        db.commit()

        # Verification audit
        gt_count = db.scalar(select(func.count(EvaluationGroundTruth.id))) or 0
        exc_count = db.scalar(select(func.count(ExceptionRecord.id))) or 0
        inj_count = db.scalar(select(func.count(InjectedCase.id))) or 0
        tx_count = db.scalar(select(func.count(GatewayTransaction.id))) or 0

        # Check source flags
        seeded_count = db.scalar(
            select(func.count(ExceptionRecord.id)).where(ExceptionRecord.source_flag == "seeded")
        ) or 0
        live_count = db.scalar(
            select(func.count(ExceptionRecord.id)).where(ExceptionRecord.source_flag == "live-injected")
        ) or 0

        summary = {
            "dataset_id": dataset_id,
            "ground_truth_count": gt_count,
            "exceptions_total": exc_count,
            "exceptions_seeded": seeded_count,
            "exceptions_live_injected": live_count,
            "injected_cases_count": inj_count,
            "gateway_transactions_count": tx_count,
            "clusters_count": len(clusters),
            "benchmark_precision": bench_result.run.precision,
            "benchmark_recall": bench_result.run.recall,
            "benchmark_f1": bench_result.run.f1_score,
            "overall_benchmark_score": bench_result.run.overall_score,
            "total_exposure_identified": bench_result.exposure_accuracy.total_predicted_exposure,
        }

        print("\n--- CLEAN CANONICAL DATABASE STATE VERIFIED ---")
        print(f"   Ground Truth Cases:      {gt_count} (must be exactly 14)")
        print(f"   Total Exceptions:        {exc_count} (must be exactly 14)")
        print(f"   Seeded Exceptions:       {seeded_count} (must be exactly 14)")
        print(f"   Live Injected Cases:     {live_count} (must be exactly 0)")
        print(f"   Injected Cases Table:    {inj_count} (must be exactly 0)")
        print(f"   Gateway Transactions:    {tx_count}")
        print("------------------------------------------------\n")

        assert gt_count == 14, f"Expected 14 ground truth cases, found {gt_count}"
        assert exc_count == 14, f"Expected 14 exceptions, found {exc_count}"
        assert seeded_count == 14, f"Expected 14 seeded exceptions, found {seeded_count}"
        assert live_count == 0, f"Expected 0 live injected exceptions, found {live_count}"
        assert inj_count == 0, f"Expected 0 injected cases, found {inj_count}"

        return summary
    finally:
        db.close()


if __name__ == "__main__":
    try:
        seed_canonical_database()
        print("Demo database clean initialization successful!")
    except Exception as e:
        print(f"Error seeding canonical database: {e}")
        sys.exit(1)
