"""Synthetic financial dataset generation service for Nodal Sentinel."""
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from backend.data.generator.config import GeneratorConfig
from backend.data.generator.context import GenerationContext
from backend.data.generator.normal_transactions import generate_normal_transactions
from backend.data.scenarios.ghost_settlement import generate_ghost_settlement_scenario
from backend.data.scenarios.refund_chargeback import generate_refund_chargeback_scenario
from backend.data.scenarios.sla_breach import generate_sla_breach_scenario
from backend.data.scenarios.partial_settlement import generate_partial_settlement_scenario
from backend.data.scenarios.missing_unallocated import (
    generate_missing_settlement_scenario,
    generate_unallocated_settlement_scenario,
)
from backend.data.scenarios.timing_exception import generate_timing_exception_scenario

from backend.models.dataset import DatasetMetadata
from backend.services.repositories import (
    FinancialSourceRepository,
    GroundTruthRepository,
    DatasetRepository,
)


def generate_dataset(
    session: Session,
    record_count: int = 60,
    seed: int = 42,
    config: Optional[GeneratorConfig] = None,
    reset_existing: bool = True,
) -> Dict[str, Any]:
    """Deterministically generates and persists a synthetic financial dataset with planted anomalies.
    
    Returns structured metadata and scenario breakdown.
    """
    if reset_existing:
        # Clean operational tables in reverse foreign-key dependency order
        from backend.models.financial_sources import (
            DisputeRefundEvent,
            BankSettlementBatch,
            MerchantOrder,
            NodalLedgerEntry,
            GatewayTransaction,
        )
        from backend.models.ground_truth import EvaluationGroundTruth
        
        session.query(DisputeRefundEvent).delete()
        session.query(BankSettlementBatch).delete()
        session.query(MerchantOrder).delete()
        session.query(NodalLedgerEntry).delete()
        session.query(GatewayTransaction).delete()
        session.query(EvaluationGroundTruth).delete()
        session.flush()

    gen_config = config or GeneratorConfig(total_target_records=record_count)
    gen_config.total_target_records = record_count
    
    ctx = GenerationContext(seed=seed, config=gen_config)

    # 1. Generate Planted Scenarios
    for i in range(gen_config.ghost_settlement_count):
        generate_ghost_settlement_scenario(ctx, index=i)

    for i in range(gen_config.refund_chargeback_count):
        generate_refund_chargeback_scenario(ctx, index=i)

    for i in range(gen_config.sla_breach_count):
        generate_sla_breach_scenario(ctx, index=i)

    for i in range(gen_config.partial_settlement_count):
        generate_partial_settlement_scenario(ctx, index=i)

    for i in range(gen_config.missing_settlement_count):
        generate_missing_settlement_scenario(ctx, index=i)

    for i in range(gen_config.unallocated_settlement_count):
        generate_unallocated_settlement_scenario(ctx, index=i)

    for i in range(gen_config.timing_exception_count):
        generate_timing_exception_scenario(ctx, index=i)

    # 2. Calculate remaining required normal transactions
    scenario_tx_count = len(ctx.gateway_transactions)
    normal_count = max(10, record_count - scenario_tx_count)
    generate_normal_transactions(ctx, count=normal_count)

    # 3. Persist Operational Records via Repository
    fin_repo = FinancialSourceRepository(session)
    for tx in ctx.gateway_transactions:
        fin_repo.add_gateway_transaction(tx)

    for order in ctx.merchant_orders:
        fin_repo.add_merchant_order(order)

    for settlement in ctx.settlement_batches:
        fin_repo.add_settlement_batch(settlement)

    for event in ctx.dispute_events:
        fin_repo.add_dispute_event(event)

    for ledger in ctx.ledger_entries:
        fin_repo.add_ledger_entry(ledger)

    # 4. Persist Ground Truth Records (Isolated Repository)
    gt_repo = GroundTruthRepository(session)
    for gt in ctx.ground_truth_cases:
        gt_repo.save_ground_truth(gt)

    # 5. Persist Dataset Metadata
    dataset_id = f"ds_seed{seed}_{uuid.uuid4().hex[:12]}"
    total_records = (
        len(ctx.gateway_transactions)
        + len(ctx.merchant_orders)
        + len(ctx.settlement_batches)
        + len(ctx.dispute_events)
        + len(ctx.ledger_entries)
    )

    metadata = DatasetMetadata(
        dataset_id=dataset_id,
        dataset_version=gen_config.dataset_version,
        seed=seed,
        record_count=total_records,
        generated_at=datetime.now(timezone.utc),
        description=(
            f"Deterministic synthetic financial dataset. "
            f"Seed: {seed}, Version: {gen_config.dataset_version}, "
            f"Gateway TXs: {len(ctx.gateway_transactions)}, "
            f"Ground Truth Anomalies: {len(ctx.ground_truth_cases)}"
        ),
    )
    dataset_repo = DatasetRepository(session)
    dataset_repo.save_dataset_metadata(metadata)

    session.flush()

    return {
        "dataset_id": dataset_id,
        "dataset_version": gen_config.dataset_version,
        "seed": seed,
        "total_financial_records": total_records,
        "counts": {
            "gateway_transactions": len(ctx.gateway_transactions),
            "merchant_orders": len(ctx.merchant_orders),
            "bank_settlement_batches": len(ctx.settlement_batches),
            "dispute_refund_events": len(ctx.dispute_events),
            "nodal_ledger_entries": len(ctx.ledger_entries),
            "ground_truth_cases": len(ctx.ground_truth_cases),
        },
        "scenario_breakdown": {
            "ghost_settlements": gen_config.ghost_settlement_count,
            "refund_chargeback_double_dips": gen_config.refund_chargeback_count,
            "settlement_sla_breaches": gen_config.sla_breach_count,
            "partial_settlements": gen_config.partial_settlement_count,
            "missing_settlements": gen_config.missing_settlement_count,
            "unallocated_settlements": gen_config.unallocated_settlement_count,
            "legitimate_timing_exceptions": gen_config.timing_exception_count,
            "normal_transactions": normal_count,
        },
    }
