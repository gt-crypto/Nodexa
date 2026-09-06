"""FastAPI REST endpoints for Remediation Planning, Approval, and Controlled Execution."""
import json
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.database import get_db
from backend.models.exceptions import ExceptionRecord
from backend.models.remediation import RemediationAction
from backend.models.verification import VerificationRecord
from backend.remediation.models import (
    RemediationPlanCreateRequest,
    RemediationApprovalRequest,
    RemediationApprovalResponse,
    RemediationPlanResponse,
    RemediationExecutionResponse,
    RemediationDryRunResponse,
    EligibleRemediationItem,
)
from backend.remediation.service import RemediationService

router = APIRouter(tags=["Controlled Remediation Workflow"])


def _to_plan_response(rec) -> RemediationPlanResponse:
    return RemediationPlanResponse(
        remediation_id=rec.action_id,
        exception_id=rec.exception_id,
        action=rec.action_type,
        parameters=json.loads(rec.action_payload or "{}"),
        policy_decision_id=rec.policy_decision_id,
        risk_assessment_id=rec.risk_assessment_id,
        investigation_id=rec.investigation_id,
        deterministic_exposure=rec.deterministic_exposure or 0,
        requested_by=rec.requested_by,
        approved_by=rec.approved_by,
        status=rec.status,
        approval_required=rec.approval_required,
        approval_role=rec.approval_role,
        verification_required=rec.verification_required,
        before_snapshot=json.loads(rec.before_snapshot) if rec.before_snapshot else None,
        after_snapshot=json.loads(rec.after_snapshot) if rec.after_snapshot else None,
        result_summary=rec.result_summary,
        error_reason=rec.error_reason,
        policy_version=rec.policy_version,
        remediation_version=rec.remediation_version,
        requested_at=rec.requested_at.isoformat() if rec.requested_at else "",
        approved_at=rec.approved_at.isoformat() if rec.approved_at else None,
        executed_at=rec.executed_at.isoformat() if rec.executed_at else None,
        created_at=rec.created_at.isoformat() if rec.created_at else "",
        updated_at=rec.updated_at.isoformat() if rec.updated_at else "",
    )


@router.post("/exceptions/{exception_id}/remediation-plan", response_model=RemediationPlanResponse)
def post_create_remediation_plan(
    exception_id: str,
    req: RemediationPlanCreateRequest,
    db: Session = Depends(get_db),
) -> RemediationPlanResponse:
    """Creates a structured, policy-gated remediation plan for a diagnosed exception."""
    service = RemediationService()
    try:
        plan = service.create_remediation_plan(
            session=db,
            exception_id=exception_id,
            action=req.action,
            parameters=req.parameters,
            requested_by=req.requested_by,
        )
        db.commit()
        return _to_plan_response(plan)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/exceptions/{exception_id}/remediations", response_model=List[RemediationPlanResponse])
def get_exception_remediations(
    exception_id: str,
    db: Session = Depends(get_db),
) -> List[RemediationPlanResponse]:
    """Retrieves all remediation plans linked to an exception."""
    exc = db.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)).first()
    if not exc:
        raise HTTPException(status_code=404, detail=f"Exception '{exception_id}' not found.")

    service = RemediationService()
    plans = service.list_remediations_for_exception(session=db, exception_id=exception_id)
    return [_to_plan_response(p) for p in plans]


@router.get("/remediations/eligible-for-verification", response_model=List[EligibleRemediationItem])
@router.get("/remediation/eligible-for-verification", response_model=List[EligibleRemediationItem])
def get_eligible_remediations(
    status: Optional[str] = Query(None, description="Optional status filter"),
    db: Session = Depends(get_db),
) -> List[EligibleRemediationItem]:
    """Retrieves real remediation plans/actions eligible for post-remediation verification."""
    stmt = select(RemediationAction).order_by(RemediationAction.created_at.desc())
    actions = db.scalars(stmt).all()

    results: List[EligibleRemediationItem] = []
    for action in actions:
        payload = {}
        try:
            payload = json.loads(action.action_payload or "{}")
        except Exception:
            pass

        # Linked verification records
        ver_stmt = (
            select(VerificationRecord)
            .where(VerificationRecord.remediation_id == action.action_id)
            .order_by(VerificationRecord.created_at.desc())
        )
        latest_ver = db.scalars(ver_stmt).first()

        already_verified = latest_ver is not None and latest_ver.verification_status == "VERIFIED"
        eligible = action.status in ("EXECUTED", "AWAITING_VERIFICATION")

        if status:
            if status.upper() == "ELIGIBLE" and not eligible:
                continue
            elif status.upper() == "VERIFIED" and not already_verified:
                continue
            elif status.upper() not in ("ELIGIBLE", "VERIFIED") and action.status != status:
                continue

        amt_minor = payload.get("amount_minor_units") or action.deterministic_exposure or 0
        amt_inr = round(amt_minor / 100.0, 2)
        payment_id = payload.get("payment_id")

        desc = f"{action.action_type} for {action.exception_id}"
        if payment_id:
            desc += f" (Payment: {payment_id})"
        desc += f" — ₹{amt_inr:,.2f}"

        results.append(
            EligibleRemediationItem(
                id=action.action_id,
                remediation_id=action.action_id,
                exception_id=action.exception_id,
                payment_id=payment_id,
                action_type=action.action_type,
                status=action.status,
                amount_minor_units=amt_minor,
                amount_inr=amt_inr,
                created_at=action.created_at.isoformat() if action.created_at else "",
                executed_at=action.executed_at.isoformat() if action.executed_at else None,
                eligible_for_verification=eligible,
                already_verified=already_verified,
                verification_status=latest_ver.verification_status if latest_ver else None,
                verification_id=latest_ver.verification_id if latest_ver else None,
                description=desc,
            )
        )

    return results


@router.get("/remediations/{remediation_id}", response_model=RemediationPlanResponse)
def get_remediation_by_id(
    remediation_id: str,
    db: Session = Depends(get_db),
) -> RemediationPlanResponse:
    """Retrieves a single remediation plan by its remediation_id."""
    service = RemediationService()
    plan = service.get_remediation(session=db, action_id=remediation_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Remediation plan '{remediation_id}' not found.")
    return _to_plan_response(plan)


@router.post("/remediations/{remediation_id}/approve", response_model=RemediationApprovalResponse)
def post_approve_remediation(
    remediation_id: str,
    req: RemediationApprovalRequest,
    db: Session = Depends(get_db),
) -> RemediationApprovalResponse:
    """Records an approval decision for a remediation plan with separation of duties enforcement."""
    service = RemediationService()
    try:
        appr = service.approve_remediation(
            session=db,
            action_id=remediation_id,
            approved_by=req.approved_by,
            decision=req.decision,
            reason=req.reason,
        )
        db.commit()
        return RemediationApprovalResponse(
            approval_id=appr.approval_id,
            action_id=appr.action_id,
            required_role=appr.required_role,
            approved_by=appr.approved_by,
            decision=appr.decision,
            reason=appr.reason,
            timestamp=appr.timestamp.isoformat(),
            policy_version=appr.policy_version,
            expires_at=appr.expires_at.isoformat() if appr.expires_at else None,
        )
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/remediations/{remediation_id}/reject", response_model=RemediationPlanResponse)
def post_reject_remediation(
    remediation_id: str,
    req: RemediationApprovalRequest,
    db: Session = Depends(get_db),
) -> RemediationPlanResponse:
    """Rejects a remediation plan."""
    service = RemediationService()
    try:
        service.approve_remediation(
            session=db,
            action_id=remediation_id,
            approved_by=req.approved_by,
            decision="REJECTED",
            reason=req.reason,
        )
        plan = service.get_remediation(session=db, action_id=remediation_id)
        db.commit()
        return _to_plan_response(plan)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/remediations/{remediation_id}/execute", response_model=RemediationExecutionResponse)
def post_execute_remediation(
    remediation_id: str,
    executed_by: str = Query("service-executor", description="Actor executing the remediation"),
    db: Session = Depends(get_db),
) -> RemediationExecutionResponse:
    """Transactionally executes an approved remediation plan with double-entry invariant validation."""
    service = RemediationService()
    try:
        plan = service.execute_remediation(
            session=db,
            action_id=remediation_id,
            executed_by=executed_by,
        )
        db.commit()
        return RemediationExecutionResponse(
            remediation_id=plan.action_id,
            exception_id=plan.exception_id,
            action=plan.action_type,
            status=plan.status,
            result_summary=plan.result_summary,
            before_snapshot=json.loads(plan.before_snapshot) if plan.before_snapshot else None,
            after_snapshot=json.loads(plan.after_snapshot) if plan.after_snapshot else None,
            verification_required=plan.verification_required,
            executed_at=plan.executed_at.isoformat() if plan.executed_at else "",
        )
    except ValueError as e:
        db.commit()  # commit failed state record
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/remediations/{remediation_id}/cancel", response_model=RemediationPlanResponse)
def post_cancel_remediation(
    remediation_id: str,
    reason: str = Query("Cancelled by operator", description="Reason for cancellation"),
    db: Session = Depends(get_db),
) -> RemediationPlanResponse:
    """Cancels a pending remediation plan."""
    service = RemediationService()
    try:
        plan = service.cancel_remediation(session=db, action_id=remediation_id, reason=reason)
        db.commit()
        return _to_plan_response(plan)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/remediations/{remediation_id}/dry-run", response_model=RemediationDryRunResponse)
def post_dry_run_remediation(
    remediation_id: str,
    db: Session = Depends(get_db),
) -> RemediationDryRunResponse:
    """Simulates remediation without committing database mutations."""
    service = RemediationService()
    plan = service.get_remediation(session=db, action_id=remediation_id)
    if not plan:
        raise HTTPException(status_code=404, detail=f"Remediation plan '{remediation_id}' not found.")

    eligible, errors, before_st, after_st, status = service.dry_run_remediation(session=db, action_id=remediation_id)
    return RemediationDryRunResponse(
        remediation_id=remediation_id,
        exception_id=plan.exception_id,
        action=plan.action_type,
        eligible=eligible,
        validation_errors=errors,
        projected_before_state=before_st,
        projected_after_state=after_st,
        approval_status=status,
    )
