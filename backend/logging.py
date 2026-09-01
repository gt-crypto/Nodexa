"""Structured JSON Logging with Request Correlation and Secret Redaction.

Provides standardized logging across all Sentinel modules with automatic
request_id linkage and security redaction for credentials and sensitive tokens.
"""
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from contextvars import ContextVar

# Context variable tracking current request_id across async coroutines
request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id_ctx", default=None)

SENSITIVE_KEYS = {
    "password",
    "secret",
    "api_key",
    "token",
    "authorization",
    "access_token",
    "refresh_token",
    "client_secret",
}


def get_current_request_id() -> str:
    """Retrieves the active request ID from context, or returns a fallback."""
    return request_id_ctx.get() or "req_system_internal"


def sanitize_payload(payload: Any) -> Any:
    """Recursively redacts sensitive keys from loggable dictionaries and payloads."""
    if isinstance(payload, dict):
        sanitized = {}
        for k, v in payload.items():
            if any(s in k.lower() for s in SENSITIVE_KEYS):
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = sanitize_payload(v)
        return sanitized
    elif isinstance(payload, list):
        return [sanitize_payload(item) for item in payload]
    return payload


class StructuredLogger:
    """Emits structured, machine-readable JSON log events."""

    def __init__(self, service_name: str = "nodal-sentinel"):
        self.service_name = service_name
        self._logger = logging.getLogger(service_name)
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)

    def log(
        self,
        level: str,
        operation: str,
        message: str,
        entity_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        details: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Constructs and emits a structured JSON log entry."""
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level.upper(),
            "service": self.service_name,
            "request_id": get_current_request_id(),
            "operation": operation,
            "message": message,
        }
        if entity_id:
            entry["entity_id"] = entity_id
        if duration_ms is not None:
            entry["duration_ms"] = round(duration_ms, 2)
        if details:
            entry["details"] = sanitize_payload(details)
        if error:
            entry["error"] = error

        log_json = json.dumps(entry)
        if level.lower() == "error":
            self._logger.error(log_json)
        elif level.lower() == "warning":
            self._logger.warning(log_json)
        else:
            self._logger.info(log_json)

    def info(self, operation: str, message: str, **kwargs: Any) -> None:
        self.log("INFO", operation, message, **kwargs)

    def warning(self, operation: str, message: str, **kwargs: Any) -> None:
        self.log("WARNING", operation, message, **kwargs)

    def error(self, operation: str, message: str, **kwargs: Any) -> None:
        self.log("ERROR", operation, message, **kwargs)


# Global structured logger
logger = StructuredLogger("nodal-sentinel")
