"""Ask Sentinel read-only tool registry and permission boundary.

Enforces strict read-only access to operational financial repositories.
Zero mutation authority (no remediation execution, transaction creation,
ledger modification, policy override, or ground-truth access).
"""
import json
from typing import Any, Callable, Dict, List, Optional
from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.exceptions import ExceptionRecord, ExceptionStateTransition, ExceptionAffectedRecord
from backend.models.risk import RiskAssessment
from backend.models.policy import PolicyDecisionRecord
from backend.models.audit import AuditEvent
from backend.models.enums import PaymentStatus, DisputeEventType
from backend.agent.tools.control_findings import lookup_control_findings


class AskSentinelToolRegistry:
    """Explicit permission registry exposing strictly read-only operational tools for Ask Sentinel."""

    ASK_SENTINEL_ALLOWED_TOOLS = [
        "get_exception",
        "search_exceptions",
        "get_payment",
        "get_settlement",
        "get_ledger_entries",
        "get_merchant",
        "get_order",
        "get_control_findings",
        "get_risk_assessment",
        "get_policy_decision",
        "get_verifier_opinion",
        "get_clusters",
        "get_merchant_trust_score",
        "get_business_impact",
        "get_drift_prediction",
        "get_confidence_calibration",
        "get_escalation_status",
        "get_audit_events",
        "get_aggregate_summary",
        "get_merchant_discrepancies",
        "get_sales_summary",
        "get_refunds_summary",
        "get_transaction_metrics",
        "get_settlements_summary",
        "get_cross_source_reconciliation",
        "get_merchants_overview",
    ]

    def __init__(self, max_tool_calls: int = 15):
        self.max_tool_calls = max_tool_calls
        self.call_count = 0
        self._tools: Dict[str, Callable] = {
            "get_exception": self.get_exception,
            "search_exceptions": self.search_exceptions,
            "get_payment": self.get_payment,
            "get_settlement": self.get_settlement,
            "get_ledger_entries": self.get_ledger_entries,
            "get_merchant": self.get_merchant,
            "get_order": self.get_order,
            "get_control_findings": self.get_control_findings,
            "get_risk_assessment": self.get_risk_assessment,
            "get_policy_decision": self.get_policy_decision,
            "get_verifier_opinion": self.get_verifier_opinion,
            "get_clusters": self.get_clusters,
            "get_merchant_trust_score": self.get_merchant_trust_score,
            "get_business_impact": self.get_business_impact,
            "get_drift_prediction": self.get_drift_prediction,
            "get_confidence_calibration": self.get_confidence_calibration,
            "get_escalation_status": self.get_escalation_status,
            "get_audit_events": self.get_audit_events,
            "get_aggregate_summary": self.get_aggregate_summary,
            "get_merchant_discrepancies": self.get_merchant_discrepancies,
            "get_sales_summary": self.get_sales_summary,
            "get_refunds_summary": self.get_refunds_summary,
            "get_transaction_metrics": self.get_transaction_metrics,
            "get_settlements_summary": self.get_settlements_summary,
            "get_cross_source_reconciliation": self.get_cross_source_reconciliation,
            "get_merchants_overview": self.get_merchants_overview,
        }

    def reset_call_counter(self):
        self.call_count = 0

    def sanitize_field_value(self, val: Any) -> Any:
        """Sanitizes text fields to neutralize prompt injection while preserving factual operational data."""
        if isinstance(val, str):
            clean = val.replace("\r\n", " ").replace("\n", " ").strip()
            return clean
        elif isinstance(val, dict):
            return {k: self.sanitize_field_value(v) for k, v in val.items()}
        elif isinstance(val, list):
            return [self.sanitize_field_value(item) for item in val]
        return val

    def execute_tool(self, tool_name: str, session: Session, **kwargs) -> Dict[str, Any]:
        """Executes a registered read-only tool within execution and safety limits."""
        if tool_name not in self.ASK_SENTINEL_ALLOWED_TOOLS:
            return {
                "status": "error",
                "tool_name": tool_name,
                "error": f"Tool '{tool_name}' is not in Ask Sentinel read-only allowlist.",
            }

        if self.call_count >= self.max_tool_calls:
            return {
                "status": "error",
                "tool_name": tool_name,
                "error": f"Maximum copilot tool execution limit ({self.max_tool_calls}) reached.",
            }

        self.call_count += 1
        fn = self._tools[tool_name]
        try:
            raw_result = fn(session=session, **kwargs)
            sanitized = self.sanitize_field_value(raw_result)
            return {
                "status": "success",
                "tool_name": tool_name,
                "data": sanitized,
            }
        except Exception as err:
            return {
                "status": "error",
                "tool_name": tool_name,
                "error": str(err),
            }

    # --- Tool Implementations ---

    def get_exception(self, session: Session, exception_id: str) -> Dict[str, Any]:
        """Retrieves detailed operational exception record."""
        stmt = select(ExceptionRecord).where(
            or_(
                func.upper(ExceptionRecord.exception_id) == func.upper(exception_id),
                func.upper(ExceptionRecord.primary_payment_id) == func.upper(exception_id),
            )
        )
        rec = session.scalars(stmt).first()
        if not rec:
            return {"found": False, "message": f"Exception '{exception_id}' not found."}

        # Retrieve affected record links
        aff_stmt = select(ExceptionAffectedRecord).where(ExceptionAffectedRecord.exception_id == rec.exception_id)
        affected_records = [
            {"record_type": r.record_type, "record_id": r.record_identifier}
            for r in session.scalars(aff_stmt).all()
        ]

        return {
            "found": True,
            "exception_id": rec.exception_id,
            "exception_type": rec.exception_type,
            "severity": rec.severity,
            "state": rec.state,
            "exposure_minor_units": rec.exposure,
            "description": rec.description,
            "primary_payment_id": rec.primary_payment_id,
            "primary_order_id": rec.primary_order_id,
            "source_flag": rec.source_flag,
            "detected_at": rec.detected_at.isoformat() if rec.detected_at else None,
            "affected_records": affected_records,
        }

    def search_exceptions(
        self,
        session: Session,
        family: Optional[str] = None,
        state: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Searches open or historical exceptions by type, state, or limit."""
        stmt = select(ExceptionRecord)
        if family:
            stmt = stmt.where(ExceptionRecord.exception_type == family)
        if state:
            stmt = stmt.where(ExceptionRecord.state == state)

        stmt = stmt.order_by(ExceptionRecord.detected_at.desc()).limit(min(limit, 50))
        recs = session.scalars(stmt).all()

        return {
            "count": len(recs),
            "exceptions": [
                {
                    "exception_id": r.exception_id,
                    "type": r.exception_type,
                    "state": r.state,
                    "severity": r.severity,
                    "exposure_minor_units": r.exposure,
                    "primary_payment_id": r.primary_payment_id,
                    "source_flag": r.source_flag,
                    "detected_at": r.detected_at.isoformat() if r.detected_at else None,
                }
                for r in recs
            ],
        }

    def get_payment(self, session: Session, payment_id: str) -> Dict[str, Any]:
        """Retrieves gateway payment transaction details."""
        stmt = select(GatewayTransaction).where(GatewayTransaction.payment_id == payment_id)
        gtx = session.scalars(stmt).first()
        if not gtx:
            return {"found": False, "message": f"Payment transaction '{payment_id}' not found."}

        return {
            "found": True,
            "payment_id": gtx.payment_id,
            "merchant_id": gtx.merchant_id,
            "amount_minor_units": gtx.amount,
            "currency": gtx.currency,
            "status": gtx.status,
            "method": gtx.method,
            "card_type": gtx.card_type,
            "auth_code": gtx.auth_code,
            "error_code": gtx.error_code,
            "created_at": gtx.created_at.isoformat() if gtx.created_at else None,
        }

    def get_settlement(self, session: Session, settlement_id: str) -> Dict[str, Any]:
        """Retrieves bank settlement batch details by settlement_id or payment_id."""
        stmt = select(BankSettlementBatch).where(
            or_(
                BankSettlementBatch.settlement_id == settlement_id,
                BankSettlementBatch.payment_id == settlement_id,
            )
        )
        batches = session.scalars(stmt).all()
        if not batches:
            return {"found": False, "message": f"Settlement batch record for '{settlement_id}' not found."}

        return {
            "found": True,
            "count": len(batches),
            "settlements": [
                {
                    "settlement_id": b.settlement_id,
                    "payment_id": b.payment_id,
                    "utr_number": b.utr_number,
                    "acquirer_id": b.acquirer_id,
                    "net_amount_minor_units": b.net_amount,
                    "interchange_fee_deducted": b.interchange_fee_deducted,
                    "tax_deducted": b.tax_deducted,
                    "clearing_timestamp": b.clearing_timestamp.isoformat() if b.clearing_timestamp else None,
                }
                for b in batches
            ],
        }

    def get_ledger_entries(
        self,
        session: Session,
        payment_id: Optional[str] = None,
        account_id: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Retrieves nodal ledger double-entry audit records."""
        stmt = select(NodalLedgerEntry)
        if payment_id:
            stmt = stmt.where(NodalLedgerEntry.transaction_id == payment_id)
        if account_id:
            stmt = stmt.where(NodalLedgerEntry.account_id == account_id)

        stmt = stmt.order_by(NodalLedgerEntry.timestamp.desc()).limit(min(limit, 50))
        entries = session.scalars(stmt).all()

        return {
            "count": len(entries),
            "ledger_entries": [
                {
                    "ledger_id": e.ledger_id,
                    "transaction_id": e.transaction_id,
                    "account_id": e.account_id,
                    "entry_type": e.entry_type,
                    "debit_minor_units": e.debit,
                    "credit_minor_units": e.credit,
                    "balance_after_minor_units": e.balance_after,
                    "reference": e.reference,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                }
                for e in entries
            ],
        }

    def get_merchant(self, session: Session, merchant_id: str) -> Dict[str, Any]:
        """Retrieves merchant overview and exception summary."""
        stmt_pay = select(GatewayTransaction).where(GatewayTransaction.merchant_id == merchant_id)
        gtxs = session.scalars(stmt_pay).all()
        payment_ids = [g.payment_id for g in gtxs]

        exc_count = 0
        open_exc = []
        if payment_ids:
            stmt_exc = select(ExceptionRecord).where(ExceptionRecord.primary_payment_id.in_(payment_ids))
            excs = session.scalars(stmt_exc).all()
            exc_count = len(excs)
            open_exc = [e.exception_id for e in excs if e.state not in ("VERIFIED_CLOSED", "REMEDIATED")]

        return {
            "merchant_id": merchant_id,
            "total_transactions_found": len(gtxs),
            "total_exceptions_found": exc_count,
            "unresolved_exception_ids": open_exc,
        }

    def get_order(
        self,
        session: Session,
        order_id: Optional[str] = None,
        payment_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves merchant order fulfillment details by order_id or payment_id."""
        target = order_id or payment_id
        if not target:
            return {"found": False, "message": "Either order_id or payment_id must be provided."}

        stmt = select(MerchantOrder).where(
            or_(
                MerchantOrder.order_id == target,
                MerchantOrder.payment_id_reference == target,
            )
        )
        ord_rec = session.scalars(stmt).first()
        if not ord_rec:
            return {"found": False, "message": f"Merchant order '{target}' not found."}

        # Retrieve linked gateway transaction if exists
        merchant_id = None
        if ord_rec.gateway_transaction:
            merchant_id = ord_rec.gateway_transaction.merchant_id

        return {
            "found": True,
            "order_id": ord_rec.order_id,
            "payment_id_reference": ord_rec.payment_id_reference,
            "customer_id": ord_rec.customer_id,
            "merchant_id": merchant_id,
            "order_amount_minor_units": ord_rec.order_amount,
            "fulfillment_status": ord_rec.fulfillment_status,
            "created_at": ord_rec.created_at.isoformat() if ord_rec.created_at else None,
        }

    def get_control_findings(self, session: Session, exception_id: str) -> Dict[str, Any]:
        """Retrieves deterministic control findings for an exception."""
        # Delegates to existing lookup_control_findings tool
        findings = lookup_control_findings(session=session, exception_id=exception_id)
        return {"exception_id": exception_id, "findings": findings}

    def get_risk_assessment(self, session: Session, exception_id: str) -> Dict[str, Any]:
        """Retrieves exposure quantification and risk assessment for an exception."""
        stmt = select(RiskAssessment).where(RiskAssessment.exception_id == exception_id)
        risk = session.scalars(stmt).first()
        if not risk:
            return {"found": False, "message": f"No risk assessment recorded for exception '{exception_id}'."}

        return {
            "found": True,
            "assessment_id": risk.assessment_id,
            "exception_id": risk.exception_id,
            "risk_score": risk.risk_score,
            "priority": risk.priority,
            "materiality": risk.materiality,
            "exposure_type": risk.exposure_type,
            "quantitative_exposure": risk.quantitative_exposure,
            "explanation": risk.deterministic_explanation,
            "created_at": risk.created_at.isoformat() if risk.created_at else None,
        }

    def get_policy_decision(self, session: Session, exception_id: str) -> Dict[str, Any]:
        """Retrieves policy decision records for an exception."""
        stmt = select(PolicyDecisionRecord).where(PolicyDecisionRecord.exception_id == exception_id)
        decisions = session.scalars(stmt).all()
        if not decisions:
            return {"found": False, "message": f"No policy decision recorded for exception '{exception_id}'."}

        return {
            "found": True,
            "decisions": [
                {
                    "decision_id": d.decision_id,
                    "requested_action": d.requested_action,
                    "decision": d.decision,
                    "approval_required": d.approval_required,
                    "required_role": d.required_role,
                    "reasoning": d.reasoning,
                    "created_at": d.created_at.isoformat() if d.created_at else None,
                }
                for d in decisions
            ],
        }

    def get_verifier_opinion(self, session: Session, exception_id: str) -> Dict[str, Any]:
        """Retrieves independent adversarial verifier opinion for an exception."""
        from backend.models.verifier import VerifierOpinion
        stmt = (
            select(VerifierOpinion)
            .where(func.upper(VerifierOpinion.exception_id) == func.upper(exception_id))
            .order_by(VerifierOpinion.created_at.desc())
        )
        opinion = session.scalars(stmt).first()
        if not opinion:
            return {"found": False, "message": f"No verifier opinion recorded for exception '{exception_id}'."}

        return {
            "found": True,
            "opinion_id": opinion.opinion_id,
            "exception_id": opinion.exception_id,
            "verdict": opinion.verdict,
            "confidence": opinion.confidence,
            "reasoning_summary": opinion.reasoning_summary,
            "evidence_refs": json.loads(opinion.evidence_refs) if opinion.evidence_refs else [],
            "recommended_action": opinion.recommended_action,
            "original_policy_decision": opinion.original_policy_decision,
            "final_policy_decision": opinion.final_policy_decision,
            "verifier_version": opinion.verifier_version,
            "created_at": opinion.created_at.isoformat() if opinion.created_at else None,
        }

    def get_clusters(
        self,
        session: Session,
        pattern_type: Optional[str] = None,
        exception_family: Optional[str] = None,
        merchant_id: Optional[str] = None,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """Retrieves structured recurring pattern clusters from the Pattern Miner."""
        from backend.patterns.miner import PatternMinerService
        service = PatternMinerService()
        clusters = service.get_clusters(
            session=session,
            pattern_type=pattern_type,
            exception_family=exception_family,
            merchant_id=merchant_id,
            limit=limit,
        )
        return {
            "total_clusters": len(clusters),
            "clusters": clusters,
        }

    def get_merchant_trust_score(self, session: Session, merchant_id: str) -> Dict[str, Any]:
        """Retrieves deterministic Merchant Trust & Impact Score."""
        from sqlalchemy import func
        from backend.api.merchants import _format_merchant_response
        from backend.models.merchant_score import MerchantScore
        from backend.merchants.scoring import MerchantScoringService
        
        m_id_clean = merchant_id.strip()
        score = session.query(MerchantScore).filter(func.lower(MerchantScore.merchant_id) == m_id_clean.lower()).first()
        if not score:
            scoring_service = MerchantScoringService()
            scoring_service.calculate_all_scores(session)
            score = session.query(MerchantScore).filter(func.lower(MerchantScore.merchant_id) == m_id_clean.lower()).first()
            
        if not score:
            return {"found": False, "message": f"Merchant score for '{merchant_id}' not found."}
            
        return {"found": True, "score": _format_merchant_response(score)}

    def get_business_impact(self, session: Session) -> Dict[str, Any]:
        """Retrieves deterministic Business Impact and ROI analytics from persisted records."""
        from backend.impact.roi_service import BusinessImpactService
        service = BusinessImpactService()
        result = service.calculate_impact(session=session, log_audit=True, actor_type="AI_AGENT", actor_id="ask_sentinel")
        return {
            "found": True,
            "impact": result,
        }

    def get_drift_prediction(self, session: Session, nodal_account_id: str = "nodal_escrow_main") -> Dict[str, Any]:
        """Retrieves deterministic leading early-warning operational drift signals for a nodal account."""
        from backend.predictions.drift_service import PredictiveDriftService
        service = PredictiveDriftService()
        result = service.evaluate_drift(
            session=session,
            nodal_account_id=nodal_account_id,
            persist=True,
            log_audit=True,
            actor_id="ask_sentinel",
        )
        return {
            "found": True,
            "drift": result,
        }

    def get_confidence_calibration(
        self,
        session: Session,
        prediction_type: Optional[str] = None,
        source: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieves deterministic confidence calibration and empirical correctness metrics."""
        from backend.calibration.service import ConfidenceCalibrationService
        service = ConfidenceCalibrationService()
        result = service.evaluate_calibration(
            session=session,
            prediction_type=prediction_type,
            source=source,
            persist=True,
            log_audit=True,
            actor_id="ask_sentinel",
        )
        return {
            "found": True,
            "calibration": result,
        }

    def get_audit_events(self, session: Session, entity_id: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """Retrieves append-only audit event trail."""
        stmt = select(AuditEvent)
        if entity_id:
            stmt = stmt.where(
                or_(
                    AuditEvent.exception_id == entity_id,
                    AuditEvent.investigation_id == entity_id,
                    AuditEvent.event_payload.like(f"%{entity_id}%"),
                )
            )

        stmt = stmt.order_by(AuditEvent.timestamp.desc()).limit(min(limit, 50))
        events = session.scalars(stmt).all()

        return {
            "count": len(events),
            "events": [
                {
                    "audit_event_id": e.audit_event_id,
                    "event_type": e.event_type,
                    "actor_id": e.actor_id,
                    "summary": e.event_summary,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else None,
                }
                for e in events
            ],
        }

    def get_aggregate_summary(self, session: Session) -> Dict[str, Any]:
        """Retrieves deterministic aggregate stats on open exceptions and exposure."""
        stmt_tot = select(func.count(ExceptionRecord.id))
        total_exceptions = session.scalar(stmt_tot) or 0

        stmt_open = select(
            func.count(ExceptionRecord.id),
            func.sum(ExceptionRecord.exposure)
        ).where(
            ExceptionRecord.state.not_in(["VERIFIED_CLOSED", "REMEDIATED"])
        )
        row_open = session.execute(stmt_open).fetchone()
        open_count = row_open[0] if row_open else 0
        open_exposure = int(row_open[1]) if row_open and row_open[1] is not None else 0

        # Breakdown by family
        stmt_fam = select(
            ExceptionRecord.exception_type,
            func.count(ExceptionRecord.id),
            func.sum(ExceptionRecord.exposure)
        ).where(
            ExceptionRecord.state.not_in(["VERIFIED_CLOSED", "REMEDIATED"])
        ).group_by(ExceptionRecord.exception_type)

        fam_rows = session.execute(stmt_fam).fetchall()
        family_breakdown = [
            {"family": r[0], "open_count": r[1], "exposure_minor_units": int(r[2]) if r[2] else 0}
            for r in fam_rows
        ]

        return {
            "total_exceptions": total_exceptions,
            "open_exceptions_count": open_count,
            "open_exposure_minor_units": open_exposure,
            "family_breakdown": family_breakdown,
        }

    def get_escalation_status(self, session: Session, exception_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves safe escalation webhook delivery status and masked configuration."""
        from backend.escalation.service import EscalationWebhookService
        svc = EscalationWebhookService()
        cfg = svc.get_webhook_configuration()
        recent = svc.get_recent_deliveries(session=session, limit=10)

        specific = None
        if exception_id:
            for d in recent:
                if d["exception_id"] == exception_id:
                    specific = d
                    break

        return {
            "configuration": cfg,
            "specific_delivery": specific,
            "recent_deliveries_count": len(recent),
            "recent_deliveries": recent[:5],
        }

    def get_merchant_discrepancies(self, session: Session) -> Dict[str, Any]:
        """Retrieves deterministic merchant anomaly profiles and settlement discrepancy summaries."""
        from backend.models.merchant_score import MerchantScore
        from backend.merchants.scoring import MerchantScoringService
        from backend.api.merchants import _format_merchant_response

        scores = session.query(MerchantScore).all()
        if not scores:
            scoring_service = MerchantScoringService()
            scores = scoring_service.calculate_all_scores(session)

        # Filter merchants with active exceptions or elevated risk bands
        anomalous_merchants = [
            _format_merchant_response(s) for s in scores
            if s.exception_count > 0 or s.score_band in ("WATCH", "HIGH_RISK", "CRITICAL")
        ]
        # Sort by total exposure descending
        anomalous_merchants.sort(key=lambda m: m["metrics"]["total_exposure"], reverse=True)

        return {
            "total_merchants_with_anomalies": len(anomalous_merchants),
            "merchants": anomalous_merchants,
            "total_merchants_evaluated": len(scores),
        }

    def get_sales_summary(self, session: Session, merchant_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves deterministic sales metrics aggregated from completed gateway transactions.

        Strictly aggregates captured transactions (PaymentStatus.CAPTURED) using integer paise.
        Excludes failed, uncaptured authorized, refunds, bank settlements, and exception exposure.
        """
        stmt = select(
            func.count(GatewayTransaction.id),
            func.sum(GatewayTransaction.amount)
        ).where(
            GatewayTransaction.status == PaymentStatus.CAPTURED.value
        )
        if merchant_id:
            stmt = stmt.where(GatewayTransaction.merchant_id == merchant_id)

        row = session.execute(stmt).fetchone()
        tx_count = row[0] if row and row[0] is not None else 0
        total_paise = int(row[1]) if row and row[1] is not None else 0
        total_inr = round(total_paise / 100.0, 2)

        return {
            "total_sales_paise": total_paise,
            "total_sales_inr": total_inr,
            "transaction_count": tx_count,
            "currency": "INR",
            "definition": "Gross captured payment transactions recorded at gateway",
            "source": "gateway_transactions",
            "merchant_id": merchant_id,
        }

    def get_refunds_summary(self, session: Session, merchant_id: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves deterministic refund metrics aggregated from dispute and refund events."""
        stmt = select(
            func.count(DisputeRefundEvent.id),
            func.sum(DisputeRefundEvent.amount)
        ).where(
            DisputeRefundEvent.event_type == DisputeEventType.REFUND.value
        )
        if merchant_id:
            stmt = stmt.join(GatewayTransaction, DisputeRefundEvent.payment_id == GatewayTransaction.payment_id).where(
                GatewayTransaction.merchant_id == merchant_id
            )

        row = session.execute(stmt).fetchone()
        refund_count = row[0] if row and row[0] is not None else 0
        total_paise = int(row[1]) if row and row[1] is not None else 0
        total_inr = round(total_paise / 100.0, 2)

        return {
            "total_refunds_paise": total_paise,
            "total_refunds_inr": total_inr,
            "refund_count": refund_count,
            "currency": "INR",
            "definition": "Customer refund events recorded in dispute/refund records",
            "source": "dispute_refund_events",
            "merchant_id": merchant_id,
        }

    def get_transaction_metrics(
        self,
        session: Session,
        status: Optional[str] = None,
        min_amount_paise: Optional[int] = None,
        max_amount_paise: Optional[int] = None,
        merchant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Calculates rich transaction analytics: counts by status, averages, min/max, and filtered lists."""
        base_stmt = select(GatewayTransaction)
        if status:
            base_stmt = base_stmt.where(GatewayTransaction.status == status)
        if merchant_id:
            base_stmt = base_stmt.where(GatewayTransaction.merchant_id == merchant_id)
        if min_amount_paise is not None:
            base_stmt = base_stmt.where(GatewayTransaction.amount >= min_amount_paise)
        if max_amount_paise is not None:
            base_stmt = base_stmt.where(GatewayTransaction.amount <= max_amount_paise)

        txs = session.scalars(base_stmt).all()
        total_count = len(txs)
        total_paise = sum(t.amount for t in txs)
        avg_paise = round(total_paise / total_count) if total_count > 0 else 0

        # Breakdowns by status across the entire database or filter
        stmt_status = select(
            GatewayTransaction.status,
            func.count(GatewayTransaction.id),
            func.sum(GatewayTransaction.amount)
        ).group_by(GatewayTransaction.status)
        if merchant_id:
            stmt_status = stmt_status.where(GatewayTransaction.merchant_id == merchant_id)
        status_rows = session.execute(stmt_status).fetchall()
        status_breakdown = {
            r[0]: {"count": r[1], "total_paise": int(r[2]) if r[2] else 0, "total_inr": round((r[2] or 0) / 100.0, 2)}
            for r in status_rows
        }

        # Min and Max transactions
        largest_tx = max(txs, key=lambda t: t.amount) if txs else None
        smallest_tx = min(txs, key=lambda t: t.amount) if txs else None

        return {
            "total_count": total_count,
            "total_paise": total_paise,
            "total_inr": round(total_paise / 100.0, 2),
            "average_paise": avg_paise,
            "average_inr": round(avg_paise / 100.0, 2),
            "status_breakdown": status_breakdown,
            "largest_transaction": {
                "payment_id": largest_tx.payment_id,
                "amount_paise": largest_tx.amount,
                "amount_inr": round(largest_tx.amount / 100.0, 2),
                "merchant_id": largest_tx.merchant_id,
                "status": largest_tx.status,
            } if largest_tx else None,
            "smallest_transaction": {
                "payment_id": smallest_tx.payment_id,
                "amount_paise": smallest_tx.amount,
                "amount_inr": round(smallest_tx.amount / 100.0, 2),
                "merchant_id": smallest_tx.merchant_id,
                "status": smallest_tx.status,
            } if smallest_tx else None,
            "sample_transactions": [
                {
                    "payment_id": t.payment_id,
                    "amount_paise": t.amount,
                    "amount_inr": round(t.amount / 100.0, 2),
                    "status": t.status,
                    "merchant_id": t.merchant_id,
                }
                for t in txs[:10]
            ],
            "filtered_criteria": {
                "status": status,
                "min_amount_paise": min_amount_paise,
                "max_amount_paise": max_amount_paise,
                "merchant_id": merchant_id,
            }
        }

    def get_settlements_summary(self, session: Session, acquirer_id: Optional[str] = None) -> Dict[str, Any]:
        """Calculates settlement clearing metrics, batch counts, timing delays, and unallocated settlements."""
        stmt = select(BankSettlementBatch)
        if acquirer_id:
            stmt = stmt.where(BankSettlementBatch.acquirer_id == acquirer_id)

        batches = session.scalars(stmt).all()
        total_batches = len(batches)
        total_net_paise = sum(b.net_amount for b in batches)
        total_fee_paise = sum(b.interchange_fee_deducted for b in batches)
        total_tax_paise = sum(b.tax_deducted for b in batches)

        largest_batch = max(batches, key=lambda b: b.net_amount) if batches else None
        smallest_batch = min(batches, key=lambda b: b.net_amount) if batches else None

        # Settlement timing differences (clearing_timestamp minus transaction created_at)
        delays_hours = []
        for b in batches:
            if b.gateway_transaction and b.clearing_timestamp and b.gateway_transaction.created_at:
                diff = (b.clearing_timestamp - b.gateway_transaction.created_at).total_seconds() / 3600.0
                if diff >= 0:
                    delays_hours.append(diff)

        avg_delay_hours = round(sum(delays_hours) / len(delays_hours), 1) if delays_hours else None

        # Check for unallocated settlement batches (missing payment_id or raw reference not matching)
        unallocated_batches = [
            {
                "settlement_id": b.settlement_id,
                "net_amount_inr": round(b.net_amount / 100.0, 2),
                "acquirer_id": b.acquirer_id,
                "raw_reference": b.raw_payment_reference,
            }
            for b in batches
            if not b.payment_id
        ]

        return {
            "total_settlement_batches": total_batches,
            "total_net_amount_paise": total_net_paise,
            "total_net_amount_inr": round(total_net_paise / 100.0, 2),
            "total_fees_inr": round(total_fee_paise / 100.0, 2),
            "total_tax_inr": round(total_tax_paise / 100.0, 2),
            "average_settlement_delay_hours": avg_delay_hours,
            "unallocated_batches_count": len(unallocated_batches),
            "unallocated_batches": unallocated_batches[:5],
            "largest_settlement": {
                "settlement_id": largest_batch.settlement_id,
                "net_amount_inr": round(largest_batch.net_amount / 100.0, 2),
                "payment_id": largest_batch.payment_id,
            } if largest_batch else None,
            "smallest_settlement": {
                "settlement_id": smallest_batch.settlement_id,
                "net_amount_inr": round(smallest_batch.net_amount / 100.0, 2),
                "payment_id": smallest_batch.payment_id,
            } if smallest_batch else None,
        }

    def get_cross_source_reconciliation(self, session: Session) -> Dict[str, Any]:
        """Cross-examines Gateway Transactions vs Bank Settlements vs Nodal Ledger entries."""
        from backend.controls.settlement_sla import evaluate_settlement_sla, SLATimingStatus
        from backend.controls.nodal_health import evaluate_nodal_health

        all_payments = session.scalars(select(GatewayTransaction)).all()
        all_settlements = session.scalars(select(BankSettlementBatch)).all()

        settlements_by_payment: Dict[str, List[BankSettlementBatch]] = {}
        for s in all_settlements:
            if s.payment_id:
                settlements_by_payment.setdefault(s.payment_id, []).append(s)

        captured_payments = [p for p in all_payments if p.status == PaymentStatus.CAPTURED.value]

        unsettled_captured = []
        partially_settled = []
        amount_mismatches = []
        sla_breaches = []

        for p in captured_payments:
            p_sets = settlements_by_payment.get(p.payment_id, [])
            if not p_sets:
                unsettled_captured.append({
                    "payment_id": p.payment_id,
                    "merchant_id": p.merchant_id,
                    "amount_inr": round(p.amount / 100.0, 2),
                    "created_at": p.created_at.isoformat() if p.created_at else None,
                })
            else:
                gross_settled = sum(s.net_amount + s.interchange_fee_deducted + s.tax_deducted for s in p_sets)
                if gross_settled < p.amount:
                    partially_settled.append({
                        "payment_id": p.payment_id,
                        "payment_amount_inr": round(p.amount / 100.0, 2),
                        "settled_amount_inr": round(gross_settled / 100.0, 2),
                        "difference_inr": round((p.amount - gross_settled) / 100.0, 2),
                    })
                elif gross_settled != p.amount:
                    amount_mismatches.append({
                        "payment_id": p.payment_id,
                        "gateway_amount_inr": round(p.amount / 100.0, 2),
                        "settlement_gross_inr": round(gross_settled / 100.0, 2),
                        "difference_inr": round((p.amount - gross_settled) / 100.0, 2),
                    })

            # Check SLA
            sla_res = evaluate_settlement_sla(p, all_settlements)
            if sla_res.calculated_values.get("timing_status") in (SLATimingStatus.SLA_BREACH.value, SLATimingStatus.LATE_BUT_VALID.value):
                sla_breaches.append({
                    "payment_id": p.payment_id,
                    "status": sla_res.calculated_values.get("timing_status"),
                    "amount_inr": round(p.amount / 100.0, 2),
                    "delay_hours": sla_res.calculated_values.get("delay_hours"),
                })

        # Nodal health / ledger balance variance check
        nh = evaluate_nodal_health(session=session)

        return {
            "total_captured_payments": len(captured_payments),
            "unsettled_captured_count": len(unsettled_captured),
            "unsettled_captured_payments": unsettled_captured[:5],
            "partially_settled_count": len(partially_settled),
            "partially_settled_payments": partially_settled[:5],
            "amount_mismatches_count": len(amount_mismatches),
            "amount_mismatches": amount_mismatches[:5],
            "sla_breach_count": len(sla_breaches),
            "sla_breach_payments": sla_breaches[:5],
            "nodal_ledger_reconciliation": {
                "expected_balance_inr": round(nh.expected_balance / 100.0, 2),
                "actual_balance_inr": round(nh.actual_balance / 100.0, 2),
                "variance_inr": round(nh.variance / 100.0, 2),
                "overall_status": nh.overall_status.value,
            },
        }

    def get_merchants_overview(self, session: Session) -> Dict[str, Any]:
        """Provides holistic merchant intelligence: counts, sales rankings, refund volume, and exposure."""
        from backend.models.merchant_score import MerchantScore
        from backend.merchants.scoring import MerchantScoringService

        scores = session.query(MerchantScore).all()
        if not scores:
            scoring_service = MerchantScoringService()
            scores = scoring_service.calculate_all_scores(session)

        # Sales volume by merchant
        sales_stmt = select(
            GatewayTransaction.merchant_id,
            func.count(GatewayTransaction.id),
            func.sum(GatewayTransaction.amount)
        ).where(
            GatewayTransaction.status == PaymentStatus.CAPTURED.value
        ).group_by(GatewayTransaction.merchant_id)
        sales_rows = session.execute(sales_stmt).fetchall()
        merchant_sales = {
            r[0]: {"count": r[1], "sales_paise": int(r[2]) if r[2] else 0, "sales_inr": round((r[2] or 0) / 100.0, 2)}
            for r in sales_rows
        }

        # Refunds by merchant
        refund_stmt = select(
            GatewayTransaction.merchant_id,
            func.count(DisputeRefundEvent.id),
            func.sum(DisputeRefundEvent.amount)
        ).join(
            DisputeRefundEvent, GatewayTransaction.payment_id == DisputeRefundEvent.payment_id
        ).where(
            DisputeRefundEvent.event_type == DisputeEventType.REFUND.value
        ).group_by(GatewayTransaction.merchant_id)
        refund_rows = session.execute(refund_stmt).fetchall()
        merchant_refunds = {
            r[0]: {"count": r[1], "refunds_paise": int(r[2]) if r[2] else 0, "refunds_inr": round((r[2] or 0) / 100.0, 2)}
            for r in refund_rows
        }

        # Exceptions by merchant
        all_merch_ids = set(merchant_sales.keys()).union(set(s.merchant_id for s in scores))
        summary_list = []
        for m_id in all_merch_ids:
            s_rec = next((s for s in scores if s.merchant_id == m_id), None)
            sales_info = merchant_sales.get(m_id, {"count": 0, "sales_paise": 0, "sales_inr": 0.0})
            refund_info = merchant_refunds.get(m_id, {"count": 0, "refunds_paise": 0, "refunds_inr": 0.0})
            exposure = s_rec.total_exposure if s_rec else 0
            exc_count = s_rec.exception_count if s_rec else 0
            trust_score = s_rec.trust_score if s_rec else None
            band = s_rec.score_band if s_rec else "UNKNOWN"

            summary_list.append({
                "merchant_id": m_id,
                "sales_inr": sales_info["sales_inr"],
                "sales_count": sales_info["count"],
                "refunds_inr": refund_info["refunds_inr"],
                "refunds_count": refund_info["count"],
                "exposure_inr": round(exposure / 100.0, 2),
                "exception_count": exc_count,
                "trust_score": trust_score,
                "score_band": band,
                "refund_exceeds_sales": refund_info["refunds_paise"] > sales_info["sales_paise"] if sales_info["sales_paise"] > 0 else False,
            })

        # Sortings
        top_by_sales = sorted(summary_list, key=lambda m: m["sales_inr"], reverse=True)
        top_by_exposure = sorted(summary_list, key=lambda m: m["exposure_inr"], reverse=True)
        top_by_exceptions = sorted(summary_list, key=lambda m: m["exception_count"], reverse=True)
        merchants_refund_exceeds_sales = [m for m in summary_list if m["refund_exceeds_sales"]]

        return {
            "total_merchants_count": len(all_merch_ids),
            "top_merchant_by_sales": top_by_sales[0] if top_by_sales else None,
            "top_merchant_by_exposure": top_by_exposure[0] if top_by_exposure else None,
            "top_merchant_by_exceptions": top_by_exceptions[0] if top_by_exceptions else None,
            "merchants_ranked_by_sales": top_by_sales[:5],
            "merchants_ranked_by_exposure": top_by_exposure[:5],
            "merchants_refund_exceeds_sales": merchants_refund_exceeds_sales,
        }


