"""Tests for investigation runs, remediation actions, verification results, audit events, and dataset metadata."""
import json
from datetime import datetime, timezone

from backend.models.exceptions import ExceptionRecord
from backend.models.investigation import InvestigationRun
from backend.models.remediation import RemediationAction
from backend.models.verification import VerificationResult
from backend.models.audit import AuditEvent
from backend.models.dataset import DatasetMetadata
from backend.models.enums import (
    ExceptionState,
    ExceptionSeverity,
    ExceptionType,
    InvestigationStatus,
    RemediationActionType,
    RemediationStatus,
    VerificationStatus,
    TransitionActorType,
)
from backend.services.repositories import (
    ExceptionRepository,
    InvestigationRepository,
    RemediationRepository,
    VerificationRepository,
    AuditRepository,
    DatasetRepository,
)


def utc_now():
    return datetime.now(timezone.utc)


def test_investigation_run_persistence(db_session):
    """Verify persisting AI investigation runs linked to exceptions."""
    exc_repo = ExceptionRepository(db_session)
    inv_repo = InvestigationRepository(db_session)

    exc = ExceptionRecord(
        exception_id="exc_inv_test_01",
        exception_type=ExceptionType.GHOST_SETTLEMENT.value,
        severity=ExceptionSeverity.HIGH.value,
        state=ExceptionState.INVESTIGATING.value,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    run = InvestigationRun(
        investigation_id="inv_run_9001",
        exception_id="exc_inv_test_01",
        status=InvestigationStatus.COMPLETED.value,
        started_at=utc_now(),
        completed_at=utc_now(),
        agent_version="agent_sentinel_v1.0",
        final_classification=ExceptionType.GHOST_SETTLEMENT.value,
        root_cause="Acquirer cleared settlement for transaction never authorized by gateway.",
        confidence=0.9920,
        recommended_action=RemediationActionType.EVIDENCE_DISPUTE_PACKET.value,
        human_approval_required=True,
    )
    inv_repo.create_investigation_run(run)

    fetched = inv_repo.get_investigation_run("inv_run_9001")
    assert fetched is not None
    assert fetched.exception_id == "exc_inv_test_01"
    assert fetched.status == InvestigationStatus.COMPLETED.value
    assert fetched.confidence == 0.9920
    assert fetched.human_approval_required is True


def test_remediation_action_and_verification_cycle(db_session):
    """Verify creating remediation action proposals and subsequent verification results."""
    exc_repo = ExceptionRepository(db_session)
    rem_repo = RemediationRepository(db_session)
    ver_repo = VerificationRepository(db_session)

    exc = ExceptionRecord(
        exception_id="exc_rem_ver_01",
        exception_type=ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value,
        severity=ExceptionSeverity.CRITICAL.value,
        state=ExceptionState.AWAITING_ACTION.value,
        exposure=500000,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    action = RemediationAction(
        action_id="act_rem_001",
        exception_id="exc_rem_ver_01",
        action_type=RemediationActionType.LEDGER_ADJUSTMENT_PROPOSAL.value,
        status=RemediationStatus.APPROVED.value,
        requested_at=utc_now(),
        approved_at=utc_now(),
        requested_by="AI_AGENT",
        approved_by="FINANCE_CONTROLLER_VIKRAM",
        action_payload=json.dumps({"reversal_amount": 500000, "target_account": "nodal_escrow_main"}),
        result_summary="Authorized ₹5000.00 dispute reversal debit.",
    )
    rem_repo.create_action(action)

    verification = VerificationResult(
        verification_id="ver_res_001",
        exception_id="exc_rem_ver_01",
        action_id="act_rem_001",
        started_at=utc_now(),
        completed_at=utc_now(),
        status=VerificationStatus.PASSED.value,
        pre_action_state=json.dumps({"ledger_variance": 500000}),
        post_action_state=json.dumps({"ledger_variance": 0}),
        expected_value="0",
        actual_value="0",
        controls_checked=json.dumps(["DOUBLE_ENTRY_EQUILIBRIUM", "ZERO_VARIANCE_INVARIANT"]),
        reconciliation_result=json.dumps({"balance_verified": True}),
    )
    ver_repo.create_verification_result(verification)

    fetched_action = rem_repo.get_action("act_rem_001")
    assert fetched_action.status == RemediationStatus.APPROVED.value

    fetched_ver = ver_repo.get_verification_result("ver_res_001")
    assert fetched_ver.status == VerificationStatus.PASSED.value
    assert fetched_ver.expected_value == "0"


def test_audit_event_append_only_behavior(db_session):
    """Verify appending and querying immutable audit events."""
    exc_repo = ExceptionRepository(db_session)
    audit_repo = AuditRepository(db_session)

    exc = ExceptionRecord(
        exception_id="exc_audit_test_01",
        exception_type=ExceptionType.SETTLEMENT_SLA_BREACH.value,
        severity=ExceptionSeverity.MEDIUM.value,
        state=ExceptionState.DETECTED.value,
        detected_at=utc_now(),
    )
    exc_repo.create_exception(exc)

    evt1 = AuditEvent(
        audit_event_id="aud_evt_101",
        exception_id="exc_audit_test_01",
        event_type="EXCEPTION_DETECTED",
        timestamp=utc_now(),
        actor_type=TransitionActorType.SYSTEM.value,
        event_summary="Anomaly detector flagged SLA breach of 48 hours.",
        event_payload=json.dumps({"sla_limit_hours": 24, "actual_hours": 48.5}),
        previous_event_hash="0000000000000000000000000000000000000000000000000000000000000000",
        event_hash="a1b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef0",
    )
    evt2 = AuditEvent(
        audit_event_id="aud_evt_102",
        exception_id="exc_audit_test_01",
        event_type="AI_INVESTIGATION_COMPLETED",
        timestamp=utc_now(),
        actor_type=TransitionActorType.AI_AGENT.value,
        actor_id="sentinel_core_v1",
        event_summary="Investigation concluded: Bank clearance batch delayed by holiday.",
        event_payload=json.dumps({"classification": "LEGITIMATE_TIMING_EXCEPTION"}),
        previous_event_hash=evt1.event_hash,
        event_hash="b2c3d4e5f60718293a4b5c6d7e8f90123456789abcdef0123456789abcdef01a",
    )

    audit_repo.append_audit_event(evt1)
    audit_repo.append_audit_event(evt2)

    events = audit_repo.list_events_for_exception("exc_audit_test_01")
    assert len(events) == 2
    assert events[0].event_type == "EXCEPTION_DETECTED"
    assert events[1].previous_event_hash == events[0].event_hash


def test_dataset_metadata_reproducibility(db_session):
    """Verify recording and querying synthetic dataset generation metadata."""
    dataset_repo = DatasetRepository(db_session)

    metadata = DatasetMetadata(
        dataset_id="ds_synth_run_42",
        dataset_version="v0.1.0-synthetic-base",
        seed=133742,
        record_count=10000,
        generated_at=utc_now(),
        description="Standard 10k transaction baseline with 5 planted anomaly scenarios.",
    )
    dataset_repo.save_dataset_metadata(metadata)

    fetched = dataset_repo.get_dataset_metadata("ds_synth_run_42")
    assert fetched is not None
    assert fetched.seed == 133742
    assert fetched.record_count == 10000
    assert fetched.dataset_version == "v0.1.0-synthetic-base"
