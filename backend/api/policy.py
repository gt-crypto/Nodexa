"""FastAPI REST endpoints for Risk Policy Gating & Decisions."""
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.database import get_db
from backend.models.exceptions import ExceptionRecord
from backend.policy.models import (
    PolicyCheckRequest,
    PolicyDecisionResponse,
    PolicyConfigResponse,
)
from backend.policy.service import PolicyService

router = APIRouter(tags=["Risk Policy & Decisions"])


def _to_response(rec) -> PolicyDecisionResponse:
    return PolicyDecisionResponse(
        decision_id=rec.decision_id,
        exception_id=rec.exception_id,
        requested_action=rec.requested_action,
        decision=rec.decision,
        policy_version=rec.policy_version,
        allowed_actions=json.loads(rec.allowed_actions or "[]"),
        prohibited_actions=json.loads(rec.prohibited_actions or "[]"),
        approval_required=rec.approval_required,
        approval_role=rec.approval_role,
        approval_reason=rec.approval_reason,
        escalation_required=rec.escalation_required,
        escalation_level=rec.escalation_level,
        escalation_reason=rec.escalation_reason,
        evidence_requirements=json.loads(rec.evidence_requirements or "[]"),
        rules_evaluated=json.loads(rec.rules_evaluated or "[]"),
        violated_rules=json.loads(rec.violated_rules or "[]"),
        rationale=rec.rationale,
        risk_score=rec.risk_score,
        priority=rec.priority,
        materiality=rec.materiality,
        exposure=rec.exposure,
        evaluated_at=rec.evaluated_at.isoformat() if rec.evaluated_at else "",
    )


@router.post("/exceptions/{exception_id}/policy-check", response_model=PolicyDecisionResponse)
def post_policy_check(
    exception_id: str,
    req: PolicyCheckRequest,
    db: Session = Depends(get_db),
) -> PolicyDecisionResponse:
    """Evaluates risk policy gating and produces an authoritative decision for a requested action."""
    exc = db.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)).first()
    if not exc:
        raise HTTPException(status_code=404, detail=f"Exception '{exception_id}' not found.")

    service = PolicyService()
    try:
        decision_rec = service.evaluate_policy(
            session=db,
            exception_id=exception_id,
            requested_action=req.requested_action,
            simulation=req.simulation,
        )
        if not req.simulation:
            db.commit()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return _to_response(decision_rec)


@router.get("/exceptions/{exception_id}/policy-decisions", response_model=List[PolicyDecisionResponse])
def get_exception_policy_decisions(
    exception_id: str,
    db: Session = Depends(get_db),
) -> List[PolicyDecisionResponse]:
    """Retrieves all historical policy decisions evaluated for an exception."""
    exc = db.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)).first()
    if not exc:
        raise HTTPException(status_code=404, detail=f"Exception '{exception_id}' not found.")

    service = PolicyService()
    decisions = service.list_decisions_for_exception(session=db, exception_id=exception_id)
    return [_to_response(d) for d in decisions]


@router.get("/policy/decisions/{decision_id}", response_model=PolicyDecisionResponse)
def get_policy_decision_by_id(
    decision_id: str,
    db: Session = Depends(get_db),
) -> PolicyDecisionResponse:
    """Retrieves a single policy decision by decision_id."""
    service = PolicyService()
    dec = service.get_decision(session=db, decision_id=decision_id)
    if not dec:
        raise HTTPException(status_code=404, detail=f"Policy decision '{decision_id}' not found.")
    return _to_response(dec)


@router.get("/policy/config", response_model=PolicyConfigResponse)
def get_policy_config() -> PolicyConfigResponse:
    """Returns active policy gating configuration parameters and version."""
    service = PolicyService()
    cfg = service.get_policy_config()
    return PolicyConfigResponse(**cfg)
