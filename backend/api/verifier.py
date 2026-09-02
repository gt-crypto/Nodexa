"""FastAPI REST router for Adversarial Verifier endpoints."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.verifier.service import AdversarialVerifierService

router = APIRouter(prefix="/verifier", tags=["Adversarial Verifier"])


class VerifierOpinionResponse(BaseModel):
    opinion_id: str
    exception_id: str
    verdict: str
    confidence: str
    reasoning_summary: str
    evidence_refs: List[str]
    recommended_action: str
    original_policy_decision: str
    final_policy_decision: str
    verifier_version: str
    created_at: str


@router.get("/opinion/{exception_id}", response_model=VerifierOpinionResponse)
def get_verifier_opinion(
    exception_id: str,
    db: Session = Depends(get_db),
) -> VerifierOpinionResponse:
    """Retrieves existing or computes initial verifier second opinion for an exception."""
    service = AdversarialVerifierService()
    opinion = service.get_opinion(db, exception_id)
    if not opinion:
        opinion = service.evaluate_exception(db, exception_id)
        db.commit()

    if not opinion:
        raise HTTPException(status_code=404, detail=f"Exception '{exception_id}' not found.")

    return VerifierOpinionResponse(**opinion)


@router.post("/evaluate/{exception_id}", response_model=VerifierOpinionResponse)
def evaluate_verifier_opinion(
    exception_id: str,
    db: Session = Depends(get_db),
) -> VerifierOpinionResponse:
    """Executes fresh independent adversarial evaluation for an exception."""
    service = AdversarialVerifierService()
    opinion = service.evaluate_exception(db, exception_id)
    db.commit()
    return VerifierOpinionResponse(**opinion)
