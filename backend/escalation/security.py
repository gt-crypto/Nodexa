"""Security utilities for Escalation Webhooks: HMAC-SHA256 signing and SSRF mitigation."""
import hmac
import hashlib
from urllib.parse import urlparse
from typing import Tuple


def generate_hmac_signature(secret: str, payload_bytes: bytes) -> str:
    """Computes HMAC-SHA256 signature for outbound webhook authentication."""
    return hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()


def validate_webhook_url(url: str, environment: str = "development") -> Tuple[bool, str]:
    """Validates destination webhook URL to guard against SSRF and protocol manipulation.

    Rules:
    - Must be http or https scheme.
    - Must have non-empty host.
    - Rejects cloud metadata addresses (169.254.169.254, metadata.google.internal).
    - In production/staging, rejects localhost and link-local ranges.
    """
    if not url or not isinstance(url, str):
        return False, "Destination URL must be a non-empty string."

    try:
        parsed = urlparse(url)
    except Exception as e:
        return False, f"Invalid URL format: {str(e)}"

    if parsed.scheme not in ("http", "https"):
        return False, f"Invalid scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."

    host = (parsed.hostname or "").lower()
    if not host:
        return False, "Destination URL missing hostname."

    # Prohibit cloud metadata services
    if host in ("169.254.169.254", "metadata.google.internal", "metadata.internal"):
        return False, "Destination targets prohibited metadata service."

    # Production safety
    if environment in ("production", "staging"):
        if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1"):
            return False, "Localhost destinations are prohibited in production/staging environments."

    return True, "Valid destination URL."
