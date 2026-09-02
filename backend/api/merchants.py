"""Merchant API routes."""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any

from backend.models.database import get_db
from backend.models.merchant_score import MerchantScore
from backend.merchants.scoring import MerchantScoringService

router = APIRouter(prefix="/merchants", tags=["merchants"])
scoring_service = MerchantScoringService()


def _format_merchant_response(ms: MerchantScore) -> Dict[str, Any]:
    return {
        "merchant_id": ms.merchant_id,
        "trust_score": ms.trust_score,
        "impact_score": ms.impact_score,
        "score_band": ms.score_band,
        "metrics": {
            "exception_count": ms.exception_count,
            "actionable_exception_count": ms.actionable_exception_count,
            "legitimate_exception_count": ms.legitimate_exception_count,
            "high_risk_exception_count": ms.high_risk_exception_count,
            "total_exposure": ms.total_exposure,
            "recurring_pattern_count": ms.recurring_pattern_count,
            "seeded_case_count": ms.seeded_case_count,
            "live_injected_case_count": ms.live_injected_case_count,
            "total_transaction_count": ms.total_transaction_count,
            "total_transaction_volume": ms.total_transaction_volume,
        },
        "factors": json.loads(ms.score_factors) if ms.score_factors else [],
        "scoring_version": ms.scoring_version,
        "first_seen": ms.first_seen.isoformat() if ms.first_seen else None,
        "last_seen": ms.last_seen.isoformat() if ms.last_seen else None,
    }


@router.post("/scores/refresh")
def refresh_merchant_scores(db: Session = Depends(get_db)):
    """Idempotent endpoint to recalculate all merchant trust and impact scores."""
    scores = scoring_service.calculate_all_scores(db)
    return {
        "status": "success",
        "total_merchants_scored": len(scores)
    }


@router.get("/{merchant_id}/trust-score")
def get_merchant_trust_score(merchant_id: str, db: Session = Depends(get_db)):
    """Get the calculated trust and impact score for a specific merchant."""
    score = db.query(MerchantScore).filter(MerchantScore.merchant_id == merchant_id).first()
    
    # If not found, run refresh just in case data exists but wasn't materialized
    if not score:
        scoring_service.calculate_all_scores(db)
        score = db.query(MerchantScore).filter(MerchantScore.merchant_id == merchant_id).first()
        
    if not score:
        raise HTTPException(status_code=404, detail="Merchant score not found")
        
    return _format_merchant_response(score)


@router.get("/scores")
def list_merchant_scores(db: Session = Depends(get_db)):
    """List all merchant scores."""
    scores = db.query(MerchantScore).all()
    # Auto-refresh if empty (helpful for fresh demo DBs)
    if not scores:
        scores = scoring_service.calculate_all_scores(db)
        
    # Sort by impact_score desc, then trust_score asc
    scores.sort(key=lambda s: (-s.impact_score, s.trust_score))
    
    return [_format_merchant_response(s) for s in scores]
