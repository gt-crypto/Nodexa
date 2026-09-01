"""Read-only tool registry with security guards, execution limits, and injection sanitization."""
import re
from typing import Any, Callable, Dict, Optional
from sqlalchemy.orm import Session

from backend.agent.tools.financial_records import lookup_payment, lookup_settlements, lookup_disputes, lookup_ledger
from backend.agent.tools.control_findings import lookup_control_findings
from backend.agent.tools.exception_details import lookup_exception_details
from backend.agent.tools.evidence import extract_investigation_evidence


class AgentToolRegistry:
    """Read-only deterministic tool registry protecting operational database integrity."""

    def __init__(self, max_tool_calls: int = 25):
        self.max_tool_calls = max_tool_calls
        self.call_count = 0
        self._tools: Dict[str, Callable] = {
            "lookup_payment": lookup_payment,
            "lookup_settlements": lookup_settlements,
            "lookup_disputes": lookup_disputes,
            "lookup_ledger": lookup_ledger,
            "lookup_control_findings": lookup_control_findings,
            "lookup_exception_details": lookup_exception_details,
            "extract_investigation_evidence": extract_investigation_evidence,
        }

    def reset_call_counter(self):
        self.call_count = 0

    def sanitize_field_value(self, val: Any) -> Any:
        """Sanitizes text fields to neutralize prompt injection while preserving factual financial data."""
        if isinstance(val, str):
            # Strip control characters, excessive whitespace
            clean = val.replace("\r\n", " ").replace("\n", " ").strip()
            return clean
        elif isinstance(val, dict):
            return {k: self.sanitize_field_value(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [self.sanitize_field_value(item) for item in val]
        return val

    def execute_tool(self, tool_name: str, session: Session, **kwargs) -> Dict[str, Any]:
        """Executes a registered read-only tool within execution limits."""
        if self.call_count >= self.max_tool_calls:
            return {
                "error": f"Tool execution limit ({self.max_tool_calls}) exceeded for this investigation run."
            }

        if tool_name not in self._tools:
            return {
                "error": f"Tool '{tool_name}' is not a registered read-only tool."
            }

        self.call_count += 1
        fn = self._tools[tool_name]
        try:
            raw_result = fn(session=session, **kwargs)
            sanitized = self.sanitize_field_value(raw_result)
            return {
                "status": "success",
                "tool_name": tool_name,
                "data": sanitized,
            }
        except Exception as err:
            return {
                "status": "error",
                "tool_name": tool_name,
                "error": str(err),
            }
