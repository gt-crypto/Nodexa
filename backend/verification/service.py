"""High-level VerificationService facade for Post-Remediation Verification."""
import json
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.verification import VerificationRecord
from backend.models.exceptions import ExceptionRecord
from backend.models.enums import VerificationStatus
from backend.services.repositories.verification_repository import VerificationRepository
from backend.verification.config import VerificationConfig, DEFAULT_VERIFICATION_CONFIG
from backend.verification.verifier import PostRemediationVerifier
from backend.verification.models import VerificationRecordResponse, VerificationDryRunResponse


class VerificationService:
    """High-level service coordinating verification runs, retries, and queries."""

    def __init__(self, config: Optional[VerificationConfig] = None):
        self.config = config or DEFAULT_VERIFICATION_CONFIG
        self.verifier = PostRemediationVerifier(config=self.config)

    def verify_remediation(
        self,
        session: Session,
        remediation_id: str,
        dry_run: bool = False,
        actor_type: str = "SYSTEM",
        actor_id: str = "verifier_v1",
    ) -> Any:
        """Executes verification or dry run for a remediation plan."""
        return self.verifier.verify(
            session=session,
            remediation_id=remediation_id,
            dry_run=dry_run,
            actor_type=actor_type,
            actor_id=actor_id,
            attempt_number=1,
        )

    def retry_verification(
        self,
        session: Session,
        verification_id: str,
        actor_type: str = "SYSTEM",
        actor_id: str = "verifier_v1",
    ) -> VerificationRecord:
        """Retries a previously failed verification if permitted by policy."""
        ver_repo = VerificationRepository(session)
        prev_record = ver_repo.get_verification_record(verification_id)
        if not prev_record:
            raise ValueError(f"Verification record '{verification_id}' not found.")

        can_retry, reason = self.verifier.lifecycle.can_retry(prev_record)
        if not can_retry:
            raise ValueError(f"Cannot retry verification: {reason}")

        next_attempt = prev_record.attempt_number + 1
        return self.verifier.verify(
            session=session,
            remediation_id=prev_record.remediation_id,
            dry_run=False,
            actor_type=actor_type,
            actor_id=actor_id,
            attempt_number=next_attempt,
        )

    def get_verification(
        self,
        session: Session,
        verification_id: str,
    ) -> Optional[VerificationRecord]:
        """Retrieves a verification record by its verification_id."""
        ver_repo = VerificationRepository(session)
        return ver_repo.get_verification_record(verification_id)

    def get_latest_verification_for_remediation(
        self,
        session: Session,
        remediation_id: str,
    ) -> Optional[VerificationRecord]:
        """Retrieves the latest verification record for a remediation plan."""
        ver_repo = VerificationRepository(session)
        return ver_repo.get_latest_for_remediation(remediation_id)

    def list_verifications_for_exception(
        self,
        session: Session,
        exception_id: str,
    ) -> List[VerificationRecord]:
        """Retrieves all verification records for an exception."""
        ver_repo = VerificationRepository(session)
        return ver_repo.list_records_for_exception(exception_id)

    @staticmethod
    def to_response_model(record: VerificationRecord, session: Optional[Session] = None) -> VerificationRecordResponse:
        """Transforms a DB VerificationRecord into a typed VerificationRecordResponse."""
        final_state: Optional[str] = None
        if session:
            exc = session.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == record.exception_id)).first()
            if exc:
                final_state = exc.state

        return VerificationRecordResponse(
            verification_id=record.verification_id,
            remediation_id=record.remediation_id,
            exception_id=record.exception_id,
            verification_status=record.verification_status,
            verification_result=record.verification_result,
            original_exposure=record.original_exposure or 0,
            remaining_exposure=record.remaining_exposure or 0,
            exposure_reduction=record.exposure_reduction or 0,
            exposure_reduction_bps=record.exposure_reduction_bps or 0,
            expected_state=json.loads(record.expected_state) if record.expected_state else None,
            actual_state=json.loads(record.actual_state) if record.actual_state else None,
            invariant_status=record.invariant_status or "PENDING",
            reconciliation_status=record.reconciliation_status or "PENDING",
            checks_passed=json.loads(record.checks_passed) if record.checks_passed else [],
            checks_failed=json.loads(record.checks_failed) if record.checks_failed else [],
            failure_reasons=json.loads(record.failure_reasons) if record.failure_reasons else [],
            evidence=json.loads(record.evidence) if record.evidence else [],
            verified_by=record.verified_by or "SYSTEM",
            verification_mode=record.verification_mode or "AUTOMATED",
            verification_version=record.verification_version or "v1",
            attempt_number=record.attempt_number or 1,
            escalation_required=record.escalation_required or False,
            final_exception_state=final_state,
            created_at=record.created_at.isoformat() if record.created_at else "",
            completed_at=record.completed_at.isoformat() if record.completed_at else None,
        )
