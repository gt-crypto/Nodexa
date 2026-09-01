"""FastAPI REST endpoints for Post-Remediation Verification."""
from typing import Any, Dict, List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.database import get_db
from backend.models.remediation import RemediationAction
from backend.models.verification import VerificationRecord
from backend.verification.models import (
    VerificationRecordResponse,
    VerificationDryRunResponse,
    VerificationRetryRequest,
)
from backend.verification.service import VerificationService

router = APIRouter(tags=["Post-Remediation Verification"])


@router.post(
    "/remediations/{remediation_id}/verify",
    response_model=Union[VerificationRecordResponse, VerificationDryRunResponse],
)
def post_verify_remediation(
    remediation_id: str,
    dry_run: bool = Query(False, description="Simulate verification without persisting records or transitioning state"),
    actor_type: str = Query("SYSTEM", description="SYSTEM or HUMAN"),
    actor_id: str = Query("verifier-v1", description="Identifier of the verifying actor or service"),
    db: Session = Depends(get_db),
) -> Any:
    """Deterministically verifies an executed remediation plan against live financial invariants and controls."""
    service = VerificationService()
    try:
        result = service.verify_remediation(
            session=db,
            remediation_id=remediation_id,
            dry_run=dry_run,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        if dry_run:
            return result
        
        db.commit()
        return VerificationService.to_response_model(result, session=db)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/remediations/{remediation_id}/verification",
    response_model=VerificationRecordResponse,
)
def get_latest_remediation_verification(
    remediation_id: str,
    db: Session = Depends(get_db),
) -> VerificationRecordResponse:
    """Retrieves the latest verification record for a remediation plan."""
    service = VerificationService()
    record = service.get_latest_verification_for_remediation(session=db, remediation_id=remediation_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"No verification found for remediation '{remediation_id}'.")
    return VerificationService.to_response_model(record, session=db)


@router.get(
    "/verifications/{verification_id}",
    response_model=VerificationRecordResponse,
)
def get_verification_by_id(
    verification_id: str,
    db: Session = Depends(get_db),
) -> VerificationRecordResponse:
    """Retrieves a full verification record including all check assertions and structured evidence."""
    service = VerificationService()
    record = service.get_verification(session=db, verification_id=verification_id)
    if not record:
        raise HTTPException(status_code=404, detail=f"Verification record '{verification_id}' not found.")
    return VerificationService.to_response_model(record, session=db)


@router.post(
    "/verifications/{verification_id}/retry",
    response_model=VerificationRecordResponse,
)
def post_retry_verification(
    verification_id: str,
    req: VerificationRetryRequest = VerificationRetryRequest(),
    db: Session = Depends(get_db),
) -> VerificationRecordResponse:
    """Retries a previously failed verification if permitted by policy limits."""
    service = VerificationService()
    try:
        record = service.retry_verification(
            session=db,
            verification_id=verification_id,
            actor_type="HUMAN" if "operator" in req.requested_by else "SYSTEM",
            actor_id=req.requested_by,
        )
        db.commit()
        return VerificationService.to_response_model(record, session=db)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/exceptions/{exception_id}/verifications",
    response_model=List[VerificationRecordResponse],
)
def get_exception_verifications(
    exception_id: str,
    db: Session = Depends(get_db),
) -> List[VerificationRecordResponse]:
    """Retrieves all verification records for an exception."""
    service = VerificationService()
    records = service.list_verifications_for_exception(session=db, exception_id=exception_id)
    return [VerificationService.to_response_model(r, session=db) for r in records]
