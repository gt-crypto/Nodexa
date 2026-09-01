"""Standard domain exception hierarchy for Nodal Sentinel."""
from typing import Any, Dict, Optional


class SentinelError(Exception):
    """Base exception for all Nodal Sentinel domain errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "INTERNAL_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


class ValidationError(SentinelError):
    """Raised when client input fails semantic or structural validation."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


class NotFoundError(SentinelError):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="NOT_FOUND",
            status_code=404,
            details=details,
        )


class ConflictError(SentinelError):
    """Raised when an operation conflicts with the current resource state."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="CONFLICT",
            status_code=409,
            details=details,
        )


class PolicyBlockedError(SentinelError):
    """Raised when a policy gate blocks an action."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="POLICY_BLOCKED",
            status_code=403,
            details=details,
        )


class ApprovalRequiredError(SentinelError):
    """Raised when an action requires explicit dual-controller approval."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="APPROVAL_REQUIRED",
            status_code=403,
            details=details,
        )


class VerificationFailedError(SentinelError):
    """Raised when post-remediation invariant verification fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="VERIFICATION_FAILED",
            status_code=422,
            details=details,
        )


class InternalError(SentinelError):
    """Raised when an unrecoverable system error occurs."""

    def __init__(self, message: str = "An unexpected internal error occurred.", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message,
            error_code="INTERNAL_ERROR",
            status_code=500,
            details=details,
        )
