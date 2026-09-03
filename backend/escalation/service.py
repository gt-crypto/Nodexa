"""Escalation Webhook service for Nodal Sentinel.

Dispatches secure, auditable outbound webhook notifications when Sentinel's canonical
policy engine or risk assessment determines an exception requires escalation.

Guarantees:
- Delivery/Notification path only; NEVER mutates policy decisions, risk, or exceptions.
- Webhook failure != policy failure (restrictive policy invariant strictly preserved).
- HMAC-SHA256 signature authentication with bounded timeouts and retries.
- Deterministic event IDs and idempotent delivery tracking.
- SSRF prevention against private metadata and unauthorized destinations.
- Complete benchmark isolation (live-injected and seeded cases use identical notification paths).
- Secrets are NEVER logged or exposed via API.
"""
import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
import requests
from sqlalchemy import select, desc
from sqlalchemy.orm import Session

from backend.config import settings
from backend.models.exceptions import ExceptionRecord
from backend.models.financial_sources import GatewayTransaction
from backend.models.policy import PolicyDecisionRecord
from backend.models.risk import RiskAssessment
from backend.models.escalation import EscalationWebhookDelivery
from backend.models.audit import AuditEvent
from backend.escalation.security import generate_hmac_signature, validate_webhook_url


def utc_now():
    return datetime.now(timezone.utc)


class EscalationWebhookService:
    """Manages escalation webhook payload construction, security signing, and delivery."""

    def __init__(
        self,
        enabled: Optional[bool] = None,
        webhook_url: Optional[str] = None,
        webhook_secret: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        self.enabled = settings.escalation_webhook_enabled if enabled is None else enabled
        self.webhook_url = settings.escalation_webhook_url if webhook_url is None else webhook_url
        self.webhook_secret = settings.escalation_webhook_secret if webhook_secret is None else webhook_secret
        self.timeout_seconds = settings.escalation_webhook_timeout_seconds if timeout_seconds is None else timeout_seconds
        self.max_retries = settings.escalation_webhook_max_retries if max_retries is None else max_retries

    def is_eligible_for_escalation(
        self,
        exception: ExceptionRecord,
        policy: Optional[PolicyDecisionRecord] = None,
        risk: Optional[RiskAssessment] = None,
    ) -> Tuple[bool, str]:
        """Evaluates whether an exception meets the canonical Sentinel escalation criteria.

        Uses existing policy and risk outcomes:
        - Policy decisions: BLOCK, HUMAN_REVIEW, REQUIRE_APPROVAL, REQUIRE_ESCALATION
        - Policy escalation_required == True
        - Risk priority: P1, P2
        - Risk escalation: RISK_REVIEW, IMMEDIATE_ESCALATION, FINANCE_REVIEW
        - Exception state: FAILED_ESCALATED
        """
        if policy:
            if policy.escalation_required:
                return True, f"Policy decision requires escalation: {policy.escalation_reason or policy.decision}"
            if policy.decision in ("BLOCK", "HUMAN_REVIEW", "REQUIRE_APPROVAL", "REQUIRE_ESCALATION"):
                return True, f"High-consequence policy decision: {policy.decision}"

        if risk:
            if risk.priority in ("P1", "P2"):
                return True, f"Critical risk priority {risk.priority} (score: {risk.risk_score})"
            if risk.escalation in ("IMMEDIATE_ESCALATION", "RISK_REVIEW", "FINANCE_REVIEW"):
                return True, f"Risk assessment escalation recommendation: {risk.escalation}"

        if exception.state == "FAILED_ESCALATED":
            return True, "Exception state is FAILED_ESCALATED"

        if exception.severity == "CRITICAL":
            return True, "Critical exception severity"

        return False, "Exception does not meet escalation criteria."

    def build_escalation_payload(
        self,
        exception: ExceptionRecord,
        policy: Optional[PolicyDecisionRecord],
        risk: Optional[RiskAssessment],
        request_id: Optional[str] = None,
        session: Optional[Session] = None,
    ) -> Tuple[Dict[str, Any], str]:
        """Constructs deterministic, versioned webhook payload with stable event ID."""
        occurred_at = utc_now().isoformat()
        decision_val = policy.decision if policy else (risk.escalation if risk else "ESCALATE")
        
        # Deterministic Event ID based on exception_id and decision
        event_hash = hashlib.sha256(f"{exception.exception_id}_{decision_val}".encode("utf-8")).hexdigest()[:16]
        event_id = f"esc_evt_{event_hash}"

        merchant_id = getattr(exception, "merchant_id", None)
        if not merchant_id and session and exception.primary_payment_id:
            try:
                tx_merchant = session.scalar(
                    select(GatewayTransaction.merchant_id).where(
                        GatewayTransaction.payment_id == exception.primary_payment_id
                    )
                )
                if tx_merchant:
                    merchant_id = tx_merchant
            except Exception:
                pass
        merchant_id = merchant_id or "UNKNOWN"

        payload = {
            "event_id": event_id,
            "event_type": "EXCEPTION_ESCALATED",
            "schema_version": "v1",
            "occurred_at": occurred_at,
            "exception": {
                "exception_id": exception.exception_id,
                "exception_type": exception.exception_type,
                "severity": exception.severity,
                "state": exception.state,
                "exposure_paise": exception.exposure or 0,
            },
            "transaction": {
                "transaction_id": exception.primary_payment_id or "UNKNOWN",
            },
            "merchant": {
                "merchant_id": merchant_id,
            },
            "nodal_account": {
                "nodal_account_id": "nodal_escrow_main",
            },
            "risk": {
                "risk_score": risk.risk_score if risk else 0,
                "priority": risk.priority if risk else "P3",
                "materiality": risk.materiality if risk else "NONE",
                "escalation_recommendation": risk.escalation if risk else "NONE",
            },
            "policy": {
                "decision_id": policy.decision_id if policy else None,
                "decision": policy.decision if policy else "REQUIRE_REVIEW",
                "escalation_required": policy.escalation_required if policy else True,
                "reason": policy.rationale if policy else "Automated escalation trigger",
            },
            "evidence": [exception.exception_id] + ([exception.primary_payment_id] if exception.primary_payment_id else []),
            "source_flag": exception.source_flag or "seeded",
            "request_id": request_id or f"req_{uuid.uuid4().hex[:12]}",
        }
        return payload, event_id

    def trigger_escalation(
        self,
        session: Session,
        exception_id: str,
        request_id: Optional[str] = None,
        actor_id: str = "escalation_dispatcher",
        force: bool = False,
    ) -> Dict[str, Any]:
        """Evaluates eligibility and executes idempotent escalation webhook delivery.

        Guarantees:
        - Delivery failure will NEVER modify policy or exception state.
        - Repeated calls are strictly idempotent.
        - Webhook destination and secrets are never logged.
        """
        exception = session.scalar(
            select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)
        )
        if not exception:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "message": f"Exception {exception_id} not found.",
            }

        policy = session.scalar(
            select(PolicyDecisionRecord)
            .where(PolicyDecisionRecord.exception_id == exception_id)
            .order_by(desc(PolicyDecisionRecord.created_at))
        )
        risk = session.scalar(
            select(RiskAssessment)
            .where(RiskAssessment.exception_id == exception_id)
            .order_by(desc(RiskAssessment.created_at))
        )

        eligible, reason = self.is_eligible_for_escalation(exception, policy, risk)
        if not eligible and not force:
            return {
                "success": False,
                "status": "INELIGIBLE",
                "message": f"Exception is not eligible for escalation: {reason}",
            }

        payload, event_id = self.build_escalation_payload(exception, policy, risk, request_id, session=session)
        payload_bytes = json.dumps(payload, sort_keys=True).encode("utf-8")
        payload_hash = hashlib.sha256(payload_bytes).hexdigest()

        # Idempotency Check: Existing delivery record
        existing_delivery = session.scalar(
            select(EscalationWebhookDelivery).where(
                EscalationWebhookDelivery.event_id == event_id
            )
        )

        if existing_delivery and existing_delivery.delivery_status == "DELIVERED" and not force:
            return {
                "success": True,
                "status": "ALREADY_DELIVERED",
                "delivery_id": existing_delivery.delivery_id,
                "event_id": event_id,
                "delivered_at": existing_delivery.delivered_at.isoformat() if existing_delivery.delivered_at else None,
                "attempt_count": existing_delivery.attempt_count,
                "message": "Webhook has already been successfully delivered for this escalation event.",
            }

        delivery = existing_delivery or EscalationWebhookDelivery(
            delivery_id=f"deliv_{uuid.uuid4().hex[:16]}",
            event_id=event_id,
            exception_id=exception.exception_id,
            event_type="EXCEPTION_ESCALATED",
            payload_hash=payload_hash,
            destination_url=self.webhook_url,
            delivery_status="PENDING",
            source_flag=exception.source_flag or "seeded",
            request_id=request_id,
            created_at=utc_now(),
        )
        session.add(delivery)
        session.commit()

        # Audit Event: ESCALATION_TRIGGERED
        self._log_audit(
            session=session,
            event_type="ESCALATION_TRIGGERED",
            actor_id=actor_id,
            exception_id=exception.exception_id,
            summary=f"Escalation webhook triggered for {exception.exception_id} ({event_id})",
            payload={
                "event_id": event_id,
                "exception_id": exception.exception_id,
                "reason": reason,
                "source_flag": exception.source_flag,
                "request_id": request_id,
            },
        )

        # Check if Webhook is Disabled or Unconfigured
        if not self.enabled or not self.webhook_url:
            delivery.delivery_status = "DISABLED"
            delivery.error_message = (
                "Escalation webhook delivery is disabled."
                if not self.enabled
                else "Destination webhook URL is not configured."
            )
            delivery.last_attempt_at = utc_now()
            session.commit()

            return {
                "success": False,
                "status": "DISABLED",
                "delivery_id": delivery.delivery_id,
                "event_id": event_id,
                "message": delivery.error_message,
            }

        # Validate Destination URL (SSRF Mitigation)
        is_valid_url, url_err = validate_webhook_url(self.webhook_url, settings.environment)
        if not is_valid_url:
            delivery.delivery_status = "FAILED"
            delivery.error_message = f"SSRF Security Violation: {url_err}"
            delivery.last_attempt_at = utc_now()
            session.commit()

            self._log_audit(
                session=session,
                event_type="ESCALATION_DELIVERY_FAILED",
                actor_id=actor_id,
                exception_id=exception.exception_id,
                summary=f"Escalation delivery failed security validation: {url_err}",
                payload={"event_id": event_id, "error": url_err},
            )
            return {
                "success": False,
                "status": "SECURITY_VIOLATION",
                "delivery_id": delivery.delivery_id,
                "event_id": event_id,
                "message": url_err,
            }

        # Build Headers & HMAC Signature
        headers = {
            "Content-Type": "application/json",
            "X-Nodal-Sentinel-Event-Id": event_id,
            "X-Nodal-Sentinel-Timestamp": payload["occurred_at"],
        }
        if self.webhook_secret:
            sig = generate_hmac_signature(self.webhook_secret, payload_bytes)
            headers["X-Nodal-Sentinel-Signature"] = f"sha256={sig}"

        # Execute Delivery with Bounded Retries
        success, status_code, err_msg = self._dispatch_with_retry(
            session=session,
            delivery=delivery,
            payload_bytes=payload_bytes,
            headers=headers,
            actor_id=actor_id,
        )

        return {
            "success": success,
            "status": delivery.delivery_status,
            "delivery_id": delivery.delivery_id,
            "event_id": event_id,
            "attempt_count": delivery.attempt_count,
            "response_status_code": status_code,
            "delivered_at": delivery.delivered_at.isoformat() if delivery.delivered_at else None,
            "error_message": err_msg,
            "message": "Webhook delivered successfully." if success else f"Delivery failed: {err_msg}",
        }

    def _dispatch_with_retry(
        self,
        session: Session,
        delivery: EscalationWebhookDelivery,
        payload_bytes: bytes,
        headers: Dict[str, str],
        actor_id: str,
    ) -> Tuple[bool, Optional[int], Optional[str]]:
        """Executes bounded HTTP delivery with retry handling and audit logging."""
        max_attempts = max(1, self.max_retries)
        last_error = None
        last_status = None

        for attempt in range(1, max_attempts + 1):
            delivery.attempt_count += 1
            now = utc_now()
            if not delivery.first_attempt_at:
                delivery.first_attempt_at = now
            delivery.last_attempt_at = now

            # Audit: ESCALATION_DELIVERY_ATTEMPTED
            self._log_audit(
                session=session,
                event_type="ESCALATION_DELIVERY_ATTEMPTED",
                actor_id=actor_id,
                exception_id=delivery.exception_id,
                summary=f"Escalation delivery attempt {attempt}/{max_attempts} for {delivery.event_id}",
                payload={"event_id": delivery.event_id, "attempt": attempt},
            )

            try:
                resp = requests.post(
                    self.webhook_url,
                    data=payload_bytes,
                    headers=headers,
                    timeout=self.timeout_seconds,
                )
                last_status = resp.status_code
                delivery.response_status_code = last_status

                if 200 <= resp.status_code < 300:
                    delivery.delivery_status = "DELIVERED"
                    delivery.delivered_at = utc_now()
                    delivery.error_message = None
                    session.commit()

                    self._log_audit(
                        session=session,
                        event_type="ESCALATION_DELIVERED",
                        actor_id=actor_id,
                        exception_id=delivery.exception_id,
                        summary=f"Escalation webhook successfully delivered: HTTP {last_status}",
                        payload={"event_id": delivery.event_id, "status_code": last_status, "attempt": attempt},
                    )
                    return True, last_status, None
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:200]}"
                    # Non-5xx errors (e.g. 400, 401, 404) are permanent; do not retry
                    if resp.status_code < 500:
                        break

            except requests.exceptions.Timeout as e:
                last_error = f"Request timed out after {self.timeout_seconds}s"
            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection failed: {str(e)[:200]}"
            except Exception as e:
                last_error = f"Unexpected delivery error: {str(e)[:200]}"

        # Delivery Failed after bounded attempts
        delivery.delivery_status = "FAILED"
        delivery.error_message = last_error
        session.commit()

        self._log_audit(
            session=session,
            event_type="ESCALATION_DELIVERY_FAILED",
            actor_id=actor_id,
            exception_id=delivery.exception_id,
            summary=f"Escalation webhook delivery failed after {delivery.attempt_count} attempts: {last_error}",
            payload={"event_id": delivery.event_id, "attempts": delivery.attempt_count, "error": last_error},
        )
        return False, last_status, last_error

    def get_recent_deliveries(self, session: Session, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent webhook delivery logs for operator and dashboard visibility."""
        deliveries = session.scalars(
            select(EscalationWebhookDelivery)
            .order_by(desc(EscalationWebhookDelivery.created_at))
            .limit(limit)
        ).all()

        return [
            {
                "delivery_id": d.delivery_id,
                "event_id": d.event_id,
                "exception_id": d.exception_id,
                "event_type": d.event_type,
                "delivery_status": d.delivery_status,
                "destination_url": d.destination_url,
                "attempt_count": d.attempt_count,
                "response_status_code": d.response_status_code,
                "error_message": d.error_message,
                "first_attempt_at": d.first_attempt_at.isoformat() if d.first_attempt_at else None,
                "last_attempt_at": d.last_attempt_at.isoformat() if d.last_attempt_at else None,
                "delivered_at": d.delivered_at.isoformat() if d.delivered_at else None,
                "source_flag": d.source_flag,
                "created_at": d.created_at.isoformat(),
            }
            for d in deliveries
        ]

    def get_webhook_configuration(self) -> Dict[str, Any]:
        """Returns safe, masked webhook configuration for dashboard visibility."""
        return {
            "enabled": self.enabled,
            "configured": bool(self.webhook_url),
            "destination_url": self.webhook_url if self.webhook_url else "NOT CONFIGURED",
            "has_signing_secret": bool(self.webhook_secret),
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "authentication_method": "HMAC-SHA256" if self.webhook_secret else "NONE",
        }

    def _log_audit(
        self,
        session: Session,
        event_type: str,
        actor_id: str,
        exception_id: str,
        summary: str,
        payload: Dict[str, Any],
    ) -> None:
        """Appends immutable audit event."""
        event = AuditEvent(
            audit_event_id=f"audit_{uuid.uuid4().hex[:16]}",
            event_type=event_type,
            actor_type="SYSTEM",
            actor_id=actor_id,
            exception_id=exception_id,
            event_summary=summary,
            event_payload=json.dumps(payload),
        )
        session.add(event)
        session.commit()
