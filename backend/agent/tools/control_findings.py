"""Read-only control findings lookup tool for AI investigator."""
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.controls.engine import ControlEngine


def lookup_control_findings(
    session: Session,
    payment_id: Optional[str] = None,
    account_id: str = "nodal_escrow_main",
) -> List[Dict[str, Any]]:
    """Runs/retrieves deterministic financial controls and filters findings for the specific entity."""
    engine = ControlEngine()
    report = engine.run_all_controls(session, account_id=account_id)

    matching_findings = []
    for ctrl in report.control_results:
        if payment_id and payment_id in ctrl.affected_record_ids:
            matching_findings.append(ctrl.to_dict())
        elif not payment_id:
            matching_findings.append(ctrl.to_dict())

    return matching_findings
