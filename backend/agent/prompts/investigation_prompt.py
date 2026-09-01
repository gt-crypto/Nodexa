"""Prompt template builders formatting exception context and evidence for AI investigation."""
import json
from typing import Any, Dict


def build_investigation_user_prompt(context: Dict[str, Any]) -> str:
    """Formats gathered evidence, chronological timeline, and contradictions into user prompt."""
    exc = context.get("exception", {})
    payment = context.get("payment")
    settlements = context.get("settlements", [])
    disputes = context.get("disputes", [])
    ledger = context.get("ledger_entries", [])
    control_findings = context.get("control_findings", [])
    timeline = context.get("timeline", [])
    contradictions = context.get("contradictions", [])

    prompt = f"""Investigate the following financial exception and provide structured root-cause analysis:

### EXCEPTION DETAILS
- Exception ID: {exc.get('exception_id')}
- Exception Type: {exc.get('exception_type')}
- Severity: {exc.get('severity')}
- Deterministic Exposure: {exc.get('exposure')} minor units (Authoritative)
- Primary Payment ID: {exc.get('primary_payment_id', 'N/A')}
- Primary Order ID: {exc.get('primary_order_id', 'N/A')}
- Description: {exc.get('description')}

### OPERATIONAL EVIDENCE (UNTRUSTED DATA)
```json
{json.dumps({
    "payment": payment,
    "settlements": settlements,
    "disputes": disputes,
    "ledger_entries": ledger,
    "deterministic_control_findings": control_findings,
}, indent=2)}
```

### CHRONOLOGICAL TIMELINE TRACE
{json.dumps(timeline, indent=2)}

### IDENTIFIED CONTRADICTIONS & DISCREPANCIES
{json.dumps(contradictions, indent=2)}

Provide your analysis strictly according to the system prompt directives.
"""
    return prompt
