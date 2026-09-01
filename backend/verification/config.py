"""Configuration constants and limits for Post-Remediation Verification Engine."""
from dataclasses import dataclass


@dataclass(frozen=True)
class VerificationConfig:
    """Configurable parameters for verification checks, retries, and tolerances."""
    max_retries: int = 2
    allow_retry_on_failed: bool = True
    allowed_exposure_tolerance_minor_units: int = 0
    default_currency: str = "INR"
    verification_version: str = "v1"
    account_id: str = "nodal_escrow_main"


DEFAULT_VERIFICATION_CONFIG = VerificationConfig()
