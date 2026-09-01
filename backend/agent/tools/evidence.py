"""Evidence extraction and citation formatting tools."""
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.agent.tools.financial_records import lookup_payment, lookup_settlements, lookup_disputes, lookup_ledger
from backend.agent.tools.control_findings import lookup_control_findings
from backend.agent.tools.exception_details import lookup_exception_details


def extract_investigation_evidence(
    session: Session,
    exception_id: str,
    account_id: str = "nodal_escrow_main",
) -> Dict[str, Any]:
    """Gathers all correlated evidence across operational tables and control results for an exception."""
    exc = lookup_exception_details(session, exception_id)
    if not exc:
        return {"error": f"Exception '{exception_id}' not found."}

    payment_id = exc.get("primary_payment_id")
    affected = exc.get("affected_records", [])

    payment_info = lookup_payment(session, payment_id) if payment_id else None

    # Settlements
    settlements = []
    if payment_id:
        settlements = lookup_settlements(session, payment_id=payment_id)
    for aff in affected:
        if aff.get("record_type") == "settlement":
            settle_id = aff.get("record_identifier")
            if not any(s.get("settlement_id") == settle_id for s in settlements):
                settlements.extend(lookup_settlements(session, settlement_id=settle_id))

    # Disputes
    disputes = lookup_disputes(session, payment_id) if payment_id else []

    # Ledger
    ledger_entries = lookup_ledger(session, payment_id=payment_id, account_id=account_id)

    # Control findings
    control_findings = lookup_control_findings(session, payment_id=payment_id, account_id=account_id)

    return {
        "exception": exc,
        "payment": payment_info,
        "settlements": settlements,
        "disputes": disputes,
        "ledger_entries": ledger_entries,
        "control_findings": control_findings,
    }
