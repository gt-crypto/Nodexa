"""FastAPI REST endpoint for Ask Sentinel Grounded Operational Copilot."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.copilot.service import AskSentinelService

router = APIRouter(prefix="/copilot", tags=["Ask Sentinel Copilot"])


class CopilotAskRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Operator question regarding Nodal Sentinel financial operational state",
    )
    exception_id: Optional[str] = Field(
        default=None,
        description="Optional exception identifier context",
    )


class CopilotAskResponse(BaseModel):
    query_id: str
    question: str
    answer: str
    evidence_refs: List[str] = []
    reasoning: str
    confidence: str = Field(..., description="Confidence rating: HIGH, MEDIUM, or LOW")
    abstained: bool = Field(..., description="True if copilot abstained due to missing evidence or safety boundary")
    limitations: Optional[str] = None
    tools_used: List[str] = []
    request_id: Optional[str] = None


@router.post("/ask", response_model=CopilotAskResponse)
def post_ask_sentinel(
    req: CopilotAskRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> CopilotAskResponse:
    """Processes natural language operational questions using grounded read-only evidence tools."""
    request_id = getattr(request.state, "request_id", None)
    service = AskSentinelService()

    try:
        res = service.ask(
            session=db,
            question=req.question,
            exception_id_context=req.exception_id,
            request_id=request_id,
        )

        return CopilotAskResponse(
            query_id=res["query_id"],
            question=res["question"],
            answer=res["answer"],
            evidence_refs=res.get("evidence_refs", []),
            reasoning=res["reasoning"],
            confidence=res["confidence"],
            abstained=res["abstained"],
            limitations=res.get("limitations"),
            tools_used=res.get("tools_used", []),
            request_id=res.get("request_id"),
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ask Sentinel copilot query processing failed: {str(e)}",
        )
