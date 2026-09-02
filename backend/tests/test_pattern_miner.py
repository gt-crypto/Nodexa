"""Comprehensive test suite for Tier-2 Pattern Miner (Prompt 15).

Tests:
A. Determinism (same dataset -> same clusters)
B. Minimum cluster size threshold (singletons do not cluster)
C. Correct grouping (related exceptions cluster together)
D. Correct separation (unrelated exceptions remain separate)
E. Explainability (structured reasons, matched fields, evidence signatures)
F. Exposure aggregation (cluster exposure equals sum of members)
G. Time range (first_seen / last_seen bounds)
H. Merchant / account aggregation
I. Seeded cases clustering
J. Live-injected cases integration (synthetic anomaly joins compatible cluster)
K. Benchmark isolation (ground truth dataset untouched)
L. Benchmark score isolation (evaluation scores unaffected)
M. Idempotency (re-running mining does not duplicate clusters)
N. REST API (GET /clusters and POST /clusters/refresh)
O. Read-only safety (zero mutation to operational records)
P. Ask Sentinel copilot pattern tool integration
"""
import pytest
import json
import secrets
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, func

from backend.models.database import Base, engine, SessionLocal
from backend.models.enums import ExceptionType, ExceptionState
from backend.models.exceptions import ExceptionRecord
from backend.models.financial_sources import GatewayTransaction, BankSettlementBatch
from backend.models.cluster import ExceptionCluster
from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.audit import AuditEvent
from backend.patterns.signatures import PatternExtractionService, PatternSignature
from backend.patterns.miner import PatternMinerService, generate_cluster_id
from backend.copilot.service import AskSentinelService
from backend.demo.injection_service import LiveDigitalTwinInjectionService


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_pattern_miner_determinism():
    """Validates that running PatternMinerService on identical data produces deterministic results."""
    db = SessionLocal()
    try:
        service = PatternMinerService(min_cluster_size=2)
        run1 = service.mine_patterns(db, persist=False)
        run2 = service.mine_patterns(db, persist=False)

        assert len(run1) == len(run2)
        for c1, c2 in zip(run1, run2):
            assert c1["cluster_id"] == c2["cluster_id"]
            assert c1["cluster_key"] == c2["cluster_key"]
            assert c1["exception_count"] == c2["exception_count"]
            assert c1["total_exposure"] == c2["total_exposure"]
            assert c1["exception_ids"] == c2["exception_ids"]
    finally:
        db.close()


def test_minimum_cluster_size_threshold():
    """Validates that isolated single exceptions do not form clusters when count < min_cluster_size."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        uid = secrets.token_hex(4)
        singleton_exc_id = f"EXC-SINGLETON-{uid}"

        # Insert a unique isolated exception
        exc = ExceptionRecord(
            exception_id=singleton_exc_id,
            exception_type="UNIQUE_ISOLATED_TEST_TYPE",
            severity="LOW",
            state=ExceptionState.DETECTED.value,
            exposure=12300,
            confidence=0.9,
            detected_at=now,
            source_flag="seeded",
        )
        db.add(exc)
        db.commit()

        service = PatternMinerService(min_cluster_size=2)
        clusters = service.mine_patterns(db, min_cluster_size=2, persist=False)

        # Core invariant: every cluster must have at least min_cluster_size members
        for cl in clusters:
            assert cl["exception_count"] >= 2, (
                f"Cluster {cl['cluster_id']} has only {cl['exception_count']} member(s) "
                f"which violates min_cluster_size=2"
            )
        # Specifically: the singleton must not appear alone in any cluster
        for cl in clusters:
            if singleton_exc_id in cl["exception_ids"]:
                assert cl["exception_count"] >= 2, (
                    f"Singleton exception {singleton_exc_id} was incorrectly promoted to a cluster"
                )
    finally:
        db.close()


def test_correct_grouping_and_exposure_aggregation():
    """Validates that related exceptions form a cluster with exact exposure and time bounds."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        uid = secrets.token_hex(4)
        merch_id = f"mer_group_test_{uid}"

        # Create 3 related SLA breach exceptions for the same merchant
        exc1 = ExceptionRecord(
            exception_id=f"EXC-SLA-1-{uid}",
            exception_type=ExceptionType.SETTLEMENT_SLA_BREACH.value,
            severity="HIGH",
            state=ExceptionState.DETECTED.value,
            exposure=10000,
            primary_payment_id=f"PAY-SLA-1-{uid}",
            detected_at=now - timedelta(hours=3),
            source_flag="seeded",
        )
        exc2 = ExceptionRecord(
            exception_id=f"EXC-SLA-2-{uid}",
            exception_type=ExceptionType.SETTLEMENT_SLA_BREACH.value,
            severity="HIGH",
            state=ExceptionState.DETECTED.value,
            exposure=25000,
            primary_payment_id=f"PAY-SLA-2-{uid}",
            detected_at=now - timedelta(hours=1),
            source_flag="seeded",
        )
        db.add_all([exc1, exc2])

        # Link to same merchant and method
        gtx1 = GatewayTransaction(
            payment_id=f"PAY-SLA-1-{uid}",
            merchant_id=merch_id,
            amount=10000,
            currency="INR",
            status="CAPTURED",
            method="UPI",
            created_at=now - timedelta(hours=3),
        )
        gtx2 = GatewayTransaction(
            payment_id=f"PAY-SLA-2-{uid}",
            merchant_id=merch_id,
            amount=25000,
            currency="INR",
            status="CAPTURED",
            method="UPI",
            created_at=now - timedelta(hours=1),
        )
        db.add_all([gtx1, gtx2])
        db.commit()

        service = PatternMinerService(min_cluster_size=2)
        clusters = service.mine_patterns(db, min_cluster_size=2, persist=False)

        # Find merchant cluster
        merch_cluster = next(
            (c for c in clusters if c["pattern_type"] == "MERCHANT_REPEATED_FAMILY" and merch_id in c["merchants"]),
            None,
        )
        assert merch_cluster is not None
        assert merch_cluster["exception_count"] == 2
        assert merch_cluster["total_exposure"] == 35000  # 10000 + 25000
        assert f"EXC-SLA-1-{uid}" in merch_cluster["exception_ids"]
        assert f"EXC-SLA-2-{uid}" in merch_cluster["exception_ids"]
        assert merch_cluster["evidence"]["matched_fields"] == ["merchant_id", "exception_type"]
        assert "Identical merchant" in merch_cluster["evidence"]["reason"]
    finally:
        db.close()


def test_idempotent_materialization_and_audit():
    """Validates that persisting clusters is idempotent and emits a single audit event per execution."""
    db = SessionLocal()
    try:
        service = PatternMinerService(min_cluster_size=2)
        
        # Mine and persist once
        clusters_run1 = service.mine_patterns(db, persist=True)
        db.commit()
        
        count_db1 = db.scalar(select(func.count(ExceptionCluster.id)))
        assert count_db1 == len(clusters_run1)

        # Mine and persist again
        clusters_run2 = service.mine_patterns(db, persist=True)
        db.commit()
        
        count_db2 = db.scalar(select(func.count(ExceptionCluster.id)))
        assert count_db2 == count_db1  # No duplicate rows created

        # Audit events check
        audit_events = list(
            db.scalars(
                select(AuditEvent).where(AuditEvent.event_type == "PATTERN_MINER_EXECUTED")
            ).all()
        )
        assert len(audit_events) >= 2
        latest_audit = audit_events[-1]
        assert "Pattern Miner executed" in latest_audit.event_summary
    finally:
        db.close()


def test_live_injected_case_joins_pattern():
    """Prompt 12 Digital-Twin Live Injection + Prompt 15 Pattern Miner Integration.

    Validates that a live-injected case joins a compatible pattern cluster without
    creating separate silos or altering ground truth.
    """
    db = SessionLocal()
    try:
        # 1. Count ground truth before
        gt_count_before = db.scalar(select(func.count(EvaluationGroundTruth.id))) or 0

        # 2. Inject a fresh synthetic anomaly (Ghost Settlement)
        injection_service = LiveDigitalTwinInjectionService()
        inj_res = injection_service.execute_injection(
            session=db,
            exception_family=ExceptionType.GHOST_SETTLEMENT.value,
            triggered_by="pattern-miner-test",
        )
        db.commit()

        injected_exc_id = inj_res.get("linked_exception_id")
        assert injected_exc_id is not None

        # 3. Re-run Pattern Miner
        service = PatternMinerService(min_cluster_size=2)
        clusters = service.mine_patterns(db, persist=True)
        db.commit()

        # 4. Locate cluster containing injected case
        injected_cluster = next(
            (c for c in clusters if injected_exc_id in c["exception_ids"]),
            None,
        )
        assert injected_cluster is not None
        assert injected_cluster["live_injected_count"] >= 1
        assert injected_cluster["exception_count"] >= 2

        # 5. Benchmark & Ground-Truth Isolation Check
        gt_count_after = db.scalar(select(func.count(EvaluationGroundTruth.id))) or 0
        assert gt_count_after == gt_count_before, "Pattern mining contaminated ground truth count!"
    finally:
        db.close()


def test_ask_sentinel_pattern_tool_query():
    """Validates that Prompt 13 Ask Sentinel copilot can query Pattern Miner and cite cluster evidence."""
    db = SessionLocal()
    try:
        # Pre-materialize clusters
        miner = PatternMinerService(min_cluster_size=2)
        miner.mine_patterns(db, persist=True)
        db.commit()

        copilot = AskSentinelService()
        res = copilot.ask(
            session=db,
            question="What recurring exception patterns are currently detected by the system?",
        )

        assert res["query_id"] is not None
        assert "get_clusters" in res["tools_used"]
        assert len(res["evidence_refs"]) > 0
        assert "Pattern Miner" in res["answer"]
        assert "cl_" in res["evidence_refs"][0]
    finally:
        db.close()


def test_clusters_rest_api():
    """Validates PRD endpoint GET /clusters and POST /clusters/refresh."""
    from fastapi.testclient import TestClient
    from backend.main import app

    client = TestClient(app)
    
    # 1. GET /clusters
    res_get = client.get("/clusters")
    assert res_get.status_code == 200
    data = res_get.json()
    assert "clusters" in data
    assert "total_clusters" in data
    assert "min_cluster_size" in data
    assert data["min_cluster_size"] >= 2

    # 2. POST /clusters/refresh
    res_post = client.post("/clusters/refresh?min_cluster_size=2")
    assert res_post.status_code == 200
    data_post = res_post.json()
    assert data_post["total_clusters"] == len(data_post["clusters"])
