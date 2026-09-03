"""FastAPI REST router for Escalation Webhook endpoints."""
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, Header, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.escalation.service import EscalationWebhookService

router = APIRouter(prefix="/escalations", tags=["Escalation Webhook"])
service = EscalationWebhookService()


class EscalationTriggerResponse(BaseModel):
    success: bool
    status: str
    delivery_id: Optional[str] = None
    event_id: Optional[str] = None
    attempt_count: Optional[int] = None
    response_status_code: Optional[int] = None
    delivered_at: Optional[str] = None
    error_message: Optional[str] = None
    message: str


class EscalationDeliveryItem(BaseModel):
    delivery_id: str
    event_id: str
    exception_id: str
    event_type: str
    delivery_status: str
    destination_url: Optional[str] = None
    attempt_count: int
    response_status_code: Optional[int] = None
    error_message: Optional[str] = None
    first_attempt_at: Optional[str] = None
    last_attempt_at: Optional[str] = None
    delivered_at: Optional[str] = None
    source_flag: str
    created_at: str


class EscalationConfigResponse(BaseModel):
    enabled: bool
    configured: bool
    destination_url: str
    has_signing_secret: bool
    timeout_seconds: int
    max_retries: int
    authentication_method: str


@router.post("/{exception_id}/webhook", response_model=EscalationTriggerResponse, summary="Trigger Escalation Webhook")
def trigger_escalation_webhook(
    exception_id: str,
    force: bool = Query(default=False, description="Bypass eligibility check if manual test"),
    db: Session = Depends(get_db),
    x_request_id: Optional[str] = Header(None),
    x_actor_id: Optional[str] = Header("operator"),
) -> EscalationTriggerResponse:
    """Dispatches an outbound escalation webhook for an eligible exception.

    Guarantees:
    - Pure notification/delivery path; NEVER mutates policy or exception state.
    - Webhook failure != policy failure (conservative policy remains enforced).
    - Idempotent: repeated calls with same event do not create uncontrolled deliveries.
    - Destination URL is strictly configuration-driven to prevent SSRF.
    """
    res = service.trigger_escalation(
        session=db,
        exception_id=exception_id,
        request_id=x_request_id,
        actor_id=x_actor_id or "operator",
        force=force,
    )
    if res.get("status") == "NOT_FOUND":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=res["message"])

    return EscalationTriggerResponse(**res)


@router.get("/deliveries", response_model=List[EscalationDeliveryItem], summary="List Recent Escalation Deliveries")
def list_escalation_deliveries(
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
) -> List[EscalationDeliveryItem]:
    """Lists recent escalation webhook delivery attempts and statuses."""
    items = service.get_recent_deliveries(session=db, limit=limit)
    return [EscalationDeliveryItem(**item) for item in items]


@router.get("/config", response_model=EscalationConfigResponse, summary="Get Escalation Webhook Configuration")
def get_escalation_config() -> EscalationConfigResponse:
    """Returns safe, masked escalation webhook configuration (never returns secrets)."""
    cfg = service.get_webhook_configuration()
    return EscalationConfigResponse(**cfg)
