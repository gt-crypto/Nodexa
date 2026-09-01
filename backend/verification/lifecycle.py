"""Verification lifecycle state machine, concurrency locking, and retry management."""
import threading
from typing import Optional, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import VerificationStatus
from backend.models.verification import VerificationRecord
from backend.verification.config import DEFAULT_VERIFICATION_CONFIG, VerificationConfig

# In-process lock for atomic worker concurrency control
_WORKER_LOCKS: dict[str, threading.Lock] = {}
_GLOBAL_LOCK = threading.Lock()


def get_remediation_lock(remediation_id: str) -> threading.Lock:
    """Gets or creates an in-memory lock for atomic remediation verification."""
    with _GLOBAL_LOCK:
        if remediation_id not in _WORKER_LOCKS:
            _WORKER_LOCKS[remediation_id] = threading.Lock()
        return _WORKER_LOCKS[remediation_id]


ALLOWED_VERIFICATION_TRANSITIONS: dict[str, Set[str]] = {
    VerificationStatus.PENDING.value: {
        VerificationStatus.RUNNING.value,
        VerificationStatus.FAILED.value,
    },
    VerificationStatus.RUNNING.value: {
        VerificationStatus.VERIFIED.value,
        VerificationStatus.FAILED.value,
        VerificationStatus.ESCALATED.value,
    },
    VerificationStatus.FAILED.value: {
        VerificationStatus.RUNNING.value,  # Allowed on explicit retry
        VerificationStatus.ESCALATED.value,
    },
    VerificationStatus.VERIFIED.value: set(),  # Terminal
    VerificationStatus.ESCALATED.value: set(), # Terminal
}


class VerificationLifecycleManager:
    """Manages atomic verification state transitions, retries, and escalation rules."""

    def __init__(self, config: Optional[VerificationConfig] = None):
        self.config = config or DEFAULT_VERIFICATION_CONFIG

    @staticmethod
    def is_valid_transition(from_status: str, to_status: str) -> bool:
        """Validates whether a lifecycle state transition is permissible."""
        allowed = ALLOWED_VERIFICATION_TRANSITIONS.get(from_status, set())
        return to_status in allowed

    def can_retry(self, record: VerificationRecord) -> Tuple[bool, str]:
        """Determines if a verification record is eligible for controlled retry."""
        if record.verification_status != VerificationStatus.FAILED.value:
            return False, f"Cannot retry verification with status '{record.verification_status}' (must be FAILED)."

        if record.attempt_number >= self.config.max_retries:
            return False, f"Maximum verification retries ({self.config.max_retries}) exceeded."

        if not self.config.allow_retry_on_failed:
            return False, "Verification retry is disabled by configuration policy."

        return True, "Retry permitted."

    def should_escalate(self, record: VerificationRecord) -> bool:
        """Determines if a failed verification should automatically escalate."""
        return record.attempt_number >= self.config.max_retries
