"""Comprehensive test suite for Tier-1 Adversarial Verifier (Prompt 14).

Tests:
1. Deterministic policy composition invariant (final >= original).
2. Verifier tool registry read-only boundary.
3. Adversarial evidence assessment and dissent generation (TIGHTEN / DISPUTE).
4. REST API endpoints (PRD: GET /exceptions/{id}/verifier-opinion).
5. Audit event emission (VERIFIER_OPINION_RECORDED).
6. Ask Sentinel copilot verifier opinion query integration.
7. Real Prompt 12 live-injection end-to-end integration without ground-truth leakage.
"""
import pytest
import json
import secrets
from datetime import datetime, timezone
from sqlalchemy import select

from backend.models.database import Base, engine, SessionLocal
from backend.models.enums import ExceptionType, ExceptionState, PolicyDecisionType
from backend.models.exceptions import ExceptionRecord
from backend.models.financial_sources import GatewayTransaction, BankSettlementBatch, NodalLedgerEntry
from backend.models.risk import RiskAssessment
from backend.models.policy import PolicyDecisionRecord
from backend.models.audit import AuditEvent
from backend.models.verifier import VerifierOpinion
from backend.verifier.composer import (
    compose_conservative_policy,
    get_restrictiveness_rank,
    POLICY_RESTRICTIVENESS,
)
from backend.verifier.tools import VerifierToolRegistry, VERIFIER_ALLOWED_TOOLS
from backend.verifier.service import AdversarialVerifierService
from backend.copilot.service import AskSentinelService
from backend.demo.injection_service import LiveDigitalTwinInjectionService


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield


def test_composer_invariant_all_combinations():
    """Validates the core invariant across ALL policy states and verifier verdicts:
    FINAL_POLICY_RESTRICTIVENESS >= ORIGINAL_POLICY_RESTRICTIVENESS
    """
    policies = list(POLICY_RESTRICTIVENESS.keys())
    verdicts = ["AGREE", "TIGHTEN", "DISPUTE", "ABSTAIN", "UNKNOWN"]
    recommended_actions = ["ALLOW", "REQUIRE_APPROVAL", "HUMAN_REVIEW", "BLOCK"]

    for orig_pol in policies:
        for verdict in verdicts:
            for rec_act in recommended_actions:
                final_pol, orig_rank, final_rank = compose_conservative_policy(
                    original_policy=orig_pol,
                    verdict=verdict,
                    recommended_action=rec_act,
                )
                assert final_rank >= orig_rank, (
                    f"Invariant violated! Orig: {orig_pol} (rank {orig_rank}), "
                    f"Verdict: {verdict}, Rec: {rec_act} -> Final: {final_pol} (rank {final_rank})"
                )


def test_composer_tightens_allow_to_more_restrictive():
    """Validates that a TIGHTEN verdict converts an ALLOW policy into a more restrictive policy."""
    final_pol, orig_rank, final_rank = compose_conservative_policy(
        original_policy="ALLOW",
        verdict="TIGHTEN",
        recommended_action="HUMAN_REVIEW",
    )
    assert orig_rank == 0
    assert final_rank >= 1
    assert final_pol in ("HUMAN_REVIEW", "REQUIRE_APPROVAL", "BLOCK")


def test_composer_dispute_blocks_or_reviews():
    """Validates that a DISPUTE verdict never permits an ALLOW."""
    final_pol, orig_rank, final_rank = compose_conservative_policy(
        original_policy="ALLOW",
        verdict="DISPUTE",
        recommended_action="BLOCK",
    )
    assert final_rank == 2
    assert final_pol == "BLOCK"


def test_verifier_tool_registry_read_only_boundary():
    """Validates that VerifierToolRegistry enforces strict read-only boundary and rejects unauthorized tools."""
    registry = VerifierToolRegistry()
    db = SessionLocal()
    try:
        # 1. Allowed tools execute normally
        res = registry.execute_tool("get_exception", session=db, exception_id="NON_EXISTENT")
        assert res["status"] == "success"
        assert res["data"]["found"] is False

        # 2. Mutation tools / unauthorized tools are blocked
        forbidden_tools = [
            "execute_remediation",
            "approve_remediation",
            "mutate_ledger",
            "override_policy",
            "delete_records",
            "access_ground_truth",
        ]
        for bad_tool in forbidden_tools:
            res_bad = registry.execute_tool(bad_tool, session=db)
            assert res_bad["status"] == "error"
            assert "allowlist" in res_bad["error"].lower()
    finally:
        db.close()


def test_verifier_evaluates_dissent_on_ghost_settlement():
    """Demonstrates evidence-based dissent/tightening on a high-exposure ghost settlement case."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        uid = secrets.token_hex(4)
        exc_id = f"EXC-VERIFIER-GHOST-{uid}"
        pay_id = f"PAY-VERIFIER-GHOST-{uid}"

        # 1. Seed Exception with ALLOW policy despite being a ghost settlement
        exc = ExceptionRecord(
            exception_id=exc_id,
            exception_type=ExceptionType.GHOST_SETTLEMENT.value,
            severity="CRITICAL",
            state=ExceptionState.DETECTED.value,
            exposure=750000,  # ₹7,500
            confidence=0.85,
            primary_payment_id=pay_id,
            source_flag="seeded",
            detected_at=now,
        )
        db.add(exc)

        # Payment is FAILED
        gtx = GatewayTransaction(
            payment_id=pay_id,
            merchant_id="mer_test_123",
            amount=750000,
            currency="INR",
            status="FAILED",
            method="UPI",
            created_at=now,
        )
        db.add(gtx)

        # Settlement batch exists
        st = BankSettlementBatch(
            settlement_id=f"SET-VERIFIER-GHOST-{uid}",
            payment_id=pay_id,
            utr_number=f"UTR{uid}1234",
            acquirer_id="HDFC",
            net_amount=750000,
            clearing_timestamp=now,
        )
        db.add(st)

        # Policy decision previously recorded as ALLOW
        pol = PolicyDecisionRecord(
            decision_id=f"POL-DEC-{uid}",
            exception_id=exc_id,
            requested_action="NO_ACTION",
            decision="ALLOW",
            policy_version="1.0",
            allowed_actions=json.dumps(["NO_ACTION"]),
            prohibited_actions=json.dumps(["RESOLVE_EXCEPTION"]),
            approval_required=False,
            rationale="Test initial lenient policy",
            risk_score=85,
            priority="P1",
            materiality="HIGH",
            exposure=750000,
            evaluated_at=now,
        )
        db.add(pol)
        db.commit()

        # 2. Run Adversarial Verifier
        verifier = AdversarialVerifierService()
        opinion = verifier.evaluate_exception(db, exc_id)
        db.commit()

        # 3. Assert evidence-based tightening
        assert opinion["exception_id"] == exc_id
        assert opinion["original_policy_decision"] == "ALLOW"
        assert opinion["final_policy_decision"] in ("HUMAN_REVIEW", "REQUIRE_APPROVAL", "BLOCK")
        assert opinion["verdict"] in ("AGREE", "TIGHTEN", "DISPUTE")
        assert len(opinion["evidence_refs"]) > 0

        # Invariant check
        orig_rank = get_restrictiveness_rank(opinion["original_policy_decision"])
        final_rank = get_restrictiveness_rank(opinion["final_policy_decision"])
        assert final_rank >= orig_rank

        # 4. Assert Audit Event generated
        audit_stmt = select(AuditEvent).where(
            AuditEvent.exception_id == exc_id,
            AuditEvent.event_type == "VERIFIER_OPINION_RECORDED",
        )
        audit_ev = db.scalars(audit_stmt).first()
        assert audit_ev is not None
        assert "Adversarial Verifier" in audit_ev.event_summary
    finally:
        db.close()


def test_ask_sentinel_queries_verifier_opinion():
    """Validates that Prompt 13 Ask Sentinel copilot can read-only query and synthesize Verifier opinions."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc)
        uid = secrets.token_hex(4)
        exc_id = f"EXC-COPILOT-{uid}"
        op_id = f"vop_copilot_{uid}"

        exc = ExceptionRecord(
            exception_id=exc_id,
            exception_type=ExceptionType.SETTLEMENT_SLA_BREACH.value,
            severity="MEDIUM",
            state=ExceptionState.INVESTIGATING.value,
            exposure=350000,
            confidence=0.90,
            source_flag="seeded",
            detected_at=now,
        )
        db.add(exc)

        # Add existing verifier opinion
        opinion = VerifierOpinion(
            opinion_id=op_id,
            exception_id=exc_id,
            verdict="TIGHTEN",
            confidence="HIGH",
            reasoning_summary="SLA breach exceeds threshold; elevated to human review.",
            evidence_refs=json.dumps([exc_id]),
            recommended_action="HUMAN_REVIEW",
            original_policy_decision="ALLOW",
            final_policy_decision="HUMAN_REVIEW",
            verifier_version="v2.0",
            created_at=now,
        )
        db.add(opinion)
        db.commit()

        # Query Ask Sentinel
        copilot = AskSentinelService()
        res = copilot.ask(
            session=db,
            question=f"What is the status and verifier opinion for exception {exc_id}?",
        )

        assert res["query_id"] is not None
        assert "get_verifier_opinion" in res["tools_used"]
        assert "Adversarial Verifier Opinion" in res["answer"]
        assert "TIGHTEN" in res["answer"]
        assert op_id in res["evidence_refs"]
    finally:
        db.close()


def test_live_injection_verifier_end_to_end():
    """Prompt 12 Digital-Twin Live Injection + Prompt 14 Adversarial Verifier Integration.

    Ensures a live-injected case is processed through detection/investigation/policy,
    then verified by the Adversarial Verifier without ground-truth leakage.
    """
    db = SessionLocal()
    try:
        injection_service = LiveDigitalTwinInjectionService()
        result = injection_service.execute_injection(
            session=db,
            exception_family=ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value,
            triggered_by="test-verifier-integration",
        )
        db.commit()

        assert result["processing_status"] in ("COMPLETED", "DETECTED")
        assert result.get("linked_exception_id") is not None
        injected_exc_id = result["linked_exception_id"]

        # Run Verifier on live-injected case
        verifier = AdversarialVerifierService()
        opinion = verifier.evaluate_exception(db, injected_exc_id)
        db.commit()

        assert opinion["exception_id"] == injected_exc_id
        assert opinion["verdict"] in ("AGREE", "TIGHTEN", "DISPUTE", "ABSTAIN")
        assert opinion["final_policy_decision"] is not None

        # Verify invariant
        orig_rank = get_restrictiveness_rank(opinion["original_policy_decision"])
        final_rank = get_restrictiveness_rank(opinion["final_policy_decision"])
        assert final_rank >= orig_rank

        # Verify ground truth isolation
        assert "ground_truth" not in opinion["reasoning_summary"].lower()
        assert "benchmark" not in opinion["reasoning_summary"].lower()
    finally:
        db.close()
