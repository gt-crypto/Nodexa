"""Tests for verification lifecycle transitions and state validation."""
import pytest

from backend.models.enums import VerificationStatus
from backend.verification.lifecycle import VerificationLifecycleManager


def test_valid_verification_lifecycle_transitions():
    """Verify standard happy path and failure escalation transitions."""
    mgr = VerificationLifecycleManager()

    assert mgr.is_valid_transition(VerificationStatus.PENDING.value, VerificationStatus.RUNNING.value) is True
    assert mgr.is_valid_transition(VerificationStatus.RUNNING.value, VerificationStatus.VERIFIED.value) is True
    assert mgr.is_valid_transition(VerificationStatus.RUNNING.value, VerificationStatus.FAILED.value) is True
    assert mgr.is_valid_transition(VerificationStatus.FAILED.value, VerificationStatus.RUNNING.value) is True
    assert mgr.is_valid_transition(VerificationStatus.FAILED.value, VerificationStatus.ESCALATED.value) is True


def test_invalid_verification_lifecycle_transitions():
    """Verify terminal state protection and illegal transitions are rejected."""
    mgr = VerificationLifecycleManager()

    # Terminal state VERIFIED cannot transition to RUNNING or FAILED
    assert mgr.is_valid_transition(VerificationStatus.VERIFIED.value, VerificationStatus.RUNNING.value) is False
    assert mgr.is_valid_transition(VerificationStatus.VERIFIED.value, VerificationStatus.FAILED.value) is False

    # Terminal state ESCALATED cannot transition to RUNNING or VERIFIED
    assert mgr.is_valid_transition(VerificationStatus.ESCALATED.value, VerificationStatus.RUNNING.value) is False
    assert mgr.is_valid_transition(VerificationStatus.ESCALATED.value, VerificationStatus.VERIFIED.value) is False

    # Cannot skip directly from PENDING to VERIFIED
    assert mgr.is_valid_transition(VerificationStatus.PENDING.value, VerificationStatus.VERIFIED.value) is False
