"""Post-Remediation Verification Engine orchestrator for Nodal Sentinel."""
from datetime import datetime, timezone
import json
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import (
    RemediationStatus,
    ExceptionState,
    TransitionActorType,
    VerificationStatus,
    VerificationMode,
    VerificationResultStatus,
    ExceptionType,
)
from backend.models.exceptions import ExceptionRecord
from backend.models.remediation import RemediationAction
from backend.models.verification import VerificationRecord
from backend.models.audit import AuditEvent
from backend.services.repositories.verification_repository import VerificationRepository
from backend.services.repositories.audit_repository import AuditRepository
from backend.controls.state_machine import transition_exception_state
from backend.verification.config import VerificationConfig, DEFAULT_VERIFICATION_CONFIG
from backend.verification.models import (
    VerificationEvidenceItem,
    VerificationRecordResponse,
    VerificationDryRunResponse,
)
from backend.verification.checks import VerificationChecksRunner
from backend.verification.lifecycle import (
    VerificationLifecycleManager,
    get_remediation_lock,
)


class PostRemediationVerifier:
    """Independent deterministic post-remediation verification engine."""

    def __init__(self, config: Optional[VerificationConfig] = None):
        self.config = config or DEFAULT_VERIFICATION_CONFIG
        self.lifecycle = VerificationLifecycleManager(config=self.config)

    def verify(
        self,
        session: Session,
        remediation_id: str,
        dry_run: bool = False,
        actor_type: str = "SYSTEM",
        actor_id: str = "verifier_v1",
        attempt_number: int = 1,
    ) -> Any:
        """Executes full post-remediation verification.
        
        If dry_run=True: returns VerificationDryRunResponse without mutating state.
        If dry_run=False: persists VerificationRecord, updates exception lifecycle, logs audit trail.
        """
        lock = get_remediation_lock(remediation_id)
        acquired = lock.acquire(blocking=True, timeout=10.0)
        if not acquired:
            raise RuntimeError(f"Concurrent verification already running for remediation '{remediation_id}'.")

        try:
            # 1. Fetch fresh remediation plan
            plan = session.scalars(
                select(RemediationAction).where(RemediationAction.action_id == remediation_id)
            ).first()
            if not plan:
                raise ValueError(f"Remediation plan '{remediation_id}' not found.")

            # 2. Fetch linked ExceptionRecord
            exception = session.scalars(
                select(ExceptionRecord).where(ExceptionRecord.exception_id == plan.exception_id)
            ).first()
            if not exception:
                raise ValueError(f"Exception '{plan.exception_id}' for remediation '{remediation_id}' not found.")

            # 3. Idempotency Check: if already VERIFIED, return existing verification
            ver_repo = VerificationRepository(session)
            existing_ver = ver_repo.get_latest_for_remediation(remediation_id)
            if existing_ver and existing_ver.verification_status == VerificationStatus.VERIFIED.value and not dry_run:
                return existing_ver

            # 4. Check 1: Remediation Execution Status Check
            ch1_pass, ev1 = VerificationChecksRunner.check_remediation_execution_status(plan)
            if not ch1_pass:
                if not dry_run:
                    raise ValueError(ev1.explanation)

            # 5. Check 2: Action Result Check
            ch2_pass, act_fail_reasons, ev2_list = VerificationChecksRunner.check_action_result(
                session=session, plan=plan, exception=exception
            )

            # 6. Check 3: Exposure Recalculation Check
            ch3_pass, rem_exp, red_amt, red_bps, ev3_list = VerificationChecksRunner.check_exposure_recalculation(
                session=session,
                exception=exception,
                plan=plan,
                tolerance=self.config.allowed_exposure_tolerance_minor_units,
            )

            # 7. Check 4: Financial Invariants Check
            ch4_pass, ev4_list = VerificationChecksRunner.check_financial_invariants(
                session=session, account_id=self.config.account_id
            )

            # 8. Check 5: Double-Entry Delta Check
            ch5_pass, ev5_list = VerificationChecksRunner.check_double_entry_delta(
                session=session, plan=plan, account_id=self.config.account_id
            )

            # 9. Check 6: Reconciliation Check
            ch6_pass, ev6_list = VerificationChecksRunner.check_reconciliation(
                session=session, exception=exception
            )

            # 10. Check 7: Legitimate Case Protection Check
            ch7_pass, ev7 = VerificationChecksRunner.check_legitimate_case_protection(
                exception=exception, plan=plan
            )

            # 11. Check 8: Stale State Protection Check
            ch8_pass, ev8 = VerificationChecksRunner.check_stale_state_protection(
                session=session, plan=plan, account_id=self.config.account_id
            )

            # Aggregate all evidence and check summaries
            all_evidence: List[VerificationEvidenceItem] = [
                ev1,
                *ev2_list,
                *ev3_list,
                *ev4_list,
                *ev5_list,
                *ev6_list,
                ev7,
                ev8,
            ]

            checks_passed: List[str] = []
            checks_failed: List[str] = []
            failure_reasons: List[str] = []

            for ev in all_evidence:
                if ev.result == "PASS":
                    checks_passed.append(ev.check_id)
                else:
                    checks_failed.append(ev.check_id)
                    failure_reasons.append(f"[{ev.check_id}] {ev.explanation}")

            for fr in act_fail_reasons:
                if fr not in failure_reasons:
                    failure_reasons.append(fr)

            # Evaluate 9 Closure Criteria
            # 1. remediation executed
            # 2. action-specific check passed
            # 3. deterministic controls pass
            # 4. reconciliation passes
            # 5. financial invariants pass
            # 6. remaining exposure = 0
            # 7. no unresolved linked exception
            # 8. verification record = VERIFIED
            # 9. policy allows closure
            is_legit_case = exception.exception_type in (
                ExceptionType.PARTIAL_SETTLEMENT.value,
                ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value,
            )

            all_checks_passed = (
                ch1_pass
                and ch2_pass
                and ch3_pass
                and ch4_pass
                and ch5_pass
                and ch6_pass
                and ch7_pass
                and ch8_pass
                and len(checks_failed) == 0
            )

            # Legitimate observations remain open / legitimate observations (do not artificially close as remediation)
            eligible_for_closure = all_checks_passed and not is_legit_case

            # Dry Run branch
            if dry_run:
                return VerificationDryRunResponse(
                    remediation_id=remediation_id,
                    exception_id=exception.exception_id,
                    projected_status=VerificationStatus.VERIFIED.value if all_checks_passed else VerificationStatus.FAILED.value,
                    original_exposure=int(exception.exposure or 0),
                    projected_remaining_exposure=rem_exp,
                    projected_reduction_bps=red_bps,
                    checks_passed=checks_passed,
                    checks_failed=checks_failed,
                    failure_reasons=failure_reasons,
                    evidence=[ev.model_dump() for ev in all_evidence],
                    eligible_for_closure=eligible_for_closure,
                    escalation_required=not all_checks_passed and (attempt_number >= self.config.max_retries),
                )

            # Live Verification: Build and save VerificationRecord
            now = datetime.now(timezone.utc)
            ver_id = f"ver_{uuid.uuid4().hex[:16]}"

            if all_checks_passed:
                final_status = VerificationStatus.VERIFIED.value
                final_result = VerificationResultStatus.PASSED.value
                escalation_required = False
            else:
                if attempt_number >= self.config.max_retries:
                    final_status = VerificationStatus.ESCALATED.value
                    final_result = VerificationResultStatus.FAILED.value
                    escalation_required = True
                else:
                    final_status = VerificationStatus.FAILED.value
                    final_result = VerificationResultStatus.FAILED.value
                    escalation_required = False

            expected_state = json.loads(plan.after_snapshot or "{}")
            actual_state = {
                "remaining_exposure": rem_exp,
                "exposure_reduction": red_amt,
                "checks_passed_count": len(checks_passed),
                "checks_failed_count": len(checks_failed),
            }

            record = VerificationRecord(
                verification_id=ver_id,
                remediation_id=remediation_id,
                exception_id=exception.exception_id,
                verification_status=final_status,
                verification_result=final_result,
                original_exposure=int(exception.exposure or 0),
                remaining_exposure=rem_exp,
                exposure_reduction=red_amt,
                exposure_reduction_bps=red_bps,
                expected_state=json.dumps(expected_state),
                actual_state=json.dumps(actual_state),
                invariant_status="PASSED" if (ch4_pass and ch5_pass) else "FAILED",
                reconciliation_status="PASSED" if ch6_pass else "FAILED",
                checks_passed=json.dumps(checks_passed),
                checks_failed=json.dumps(checks_failed),
                failure_reasons=json.dumps(failure_reasons),
                evidence=json.dumps([ev.model_dump() for ev in all_evidence]),
                verified_by=actor_id,
                verification_mode=VerificationMode.AUTOMATED.value if actor_type == "SYSTEM" else VerificationMode.HUMAN_ASSISTED.value,
                verification_version=self.config.verification_version,
                attempt_number=attempt_number,
                escalation_required=escalation_required,
                created_at=now,
                completed_at=now,
            )
            ver_repo.create_verification_record(record)

            # Audit Logging
            audit_repo = AuditRepository(session)
            actor_type_enum = TransitionActorType.SYSTEM if actor_type == "SYSTEM" else TransitionActorType.HUMAN

            # Audit: Started
            audit_repo.append_audit_event(
                AuditEvent(
                    audit_event_id=f"aud_{uuid.uuid4().hex[:16]}",
                    exception_id=exception.exception_id,
                    investigation_id=plan.investigation_id,
                    event_type="VERIFICATION_STARTED",
                    timestamp=now,
                    actor_type=actor_type_enum.value,
                    actor_id=actor_id,
                    event_summary=f"Started post-remediation verification '{ver_id}' for remediation '{plan.action_id}'",
                    event_payload=json.dumps({"verification_id": ver_id, "remediation_id": remediation_id, "attempt": attempt_number}),
                )
            )

            # Audit: Individual check passes/failures
            for ev in all_evidence:
                evt_type = "VERIFICATION_CHECK_PASSED" if ev.result == "PASS" else "VERIFICATION_CHECK_FAILED"
                audit_repo.append_audit_event(
                    AuditEvent(
                        audit_event_id=f"aud_{uuid.uuid4().hex[:16]}",
                        exception_id=exception.exception_id,
                        investigation_id=plan.investigation_id,
                        event_type=evt_type,
                        timestamp=now,
                        actor_type=actor_type_enum.value,
                        actor_id=actor_id,
                        event_summary=f"{ev.check_id}: {ev.result} - {ev.explanation}",
                        event_payload=json.dumps(ev.model_dump()),
                    )
                )

            # Audit & Lifecycle Transitions
            if final_status == VerificationStatus.VERIFIED.value:
                audit_repo.append_audit_event(
                    AuditEvent(
                        audit_event_id=f"aud_{uuid.uuid4().hex[:16]}",
                        exception_id=exception.exception_id,
                        investigation_id=plan.investigation_id,
                        event_type="VERIFICATION_COMPLETED",
                        timestamp=now,
                        actor_type=actor_type_enum.value,
                        actor_id=actor_id,
                        event_summary=f"Verification '{ver_id}' PASSED. Zero remaining exposure confirmed.",
                        event_payload=json.dumps({"verification_id": ver_id, "status": "VERIFIED"}),
                    )
                )

                # Transition exception state to VERIFIED_CLOSED only if closure requirements met and not legitimate observation
                if eligible_for_closure:
                    transition_exception_state(
                        session=session,
                        exception_id=exception.exception_id,
                        to_state=ExceptionState.VERIFIED_CLOSED,
                        reason=f"Verified closed: remediation '{remediation_id}' eliminated exposure with zero invariant violations.",
                        actor_type=actor_type_enum,
                        actor_id=actor_id,
                    )
                    audit_repo.append_audit_event(
                        AuditEvent(
                            audit_event_id=f"aud_{uuid.uuid4().hex[:16]}",
                            exception_id=exception.exception_id,
                            investigation_id=plan.investigation_id,
                            event_type="EXCEPTION_VERIFIED_CLOSED",
                            timestamp=now,
                            actor_type=actor_type_enum.value,
                            actor_id=actor_id,
                            event_summary=f"Exception '{exception.exception_id}' transitioned to VERIFIED_CLOSED.",
                            event_payload=json.dumps({"verification_id": ver_id, "final_state": "VERIFIED_CLOSED"}),
                        )
                    )

            elif final_status == VerificationStatus.ESCALATED.value:
                audit_repo.append_audit_event(
                    AuditEvent(
                        audit_event_id=f"aud_{uuid.uuid4().hex[:16]}",
                        exception_id=exception.exception_id,
                        investigation_id=plan.investigation_id,
                        event_type="VERIFICATION_ESCALATED",
                        timestamp=now,
                        actor_type=actor_type_enum.value,
                        actor_id=actor_id,
                        event_summary=f"Verification '{ver_id}' failed after {attempt_number} attempts; escalated to FAILED_ESCALATED.",
                        event_payload=json.dumps({"verification_id": ver_id, "reasons": failure_reasons}),
                    )
                )
                transition_exception_state(
                    session=session,
                    exception_id=exception.exception_id,
                    to_state=ExceptionState.FAILED_ESCALATED,
                    reason=f"Verification failed: {'; '.join(failure_reasons)}",
                    actor_type=actor_type_enum,
                    actor_id=actor_id,
                )

            else:  # FAILED but eligible for retry
                audit_repo.append_audit_event(
                    AuditEvent(
                        audit_event_id=f"aud_{uuid.uuid4().hex[:16]}",
                        exception_id=exception.exception_id,
                        investigation_id=plan.investigation_id,
                        event_type="VERIFICATION_FAILED",
                        timestamp=now,
                        actor_type=actor_type_enum.value,
                        actor_id=actor_id,
                        event_summary=f"Verification '{ver_id}' failed: {'; '.join(failure_reasons)}",
                        event_payload=json.dumps({"verification_id": ver_id, "reasons": failure_reasons}),
                    )
                )

            session.flush()
            return record

        finally:
            lock.release()
