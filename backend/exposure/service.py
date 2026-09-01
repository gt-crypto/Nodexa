"""High-level service orchestrating deterministic Risk & Exposure assessments."""
from datetime import datetime, timezone
import json
import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import ExceptionState, TransitionActorType
from backend.models.exceptions import ExceptionRecord
from backend.models.risk import RiskAssessment
from backend.models.investigation import InvestigationRun
from backend.models.audit import AuditEvent
from backend.services.repositories.audit_repository import AuditRepository
from backend.exposure.config import POLICY_VERSION, SCORING_VERSION, THRESHOLD_VERSION
from backend.exposure.materiality import classify_exposure_type, classify_materiality
from backend.exposure.factors import extract_risk_factors
from backend.exposure.scoring import (
    calculate_risk_score,
    determine_priority,
    determine_escalation,
    generate_risk_explanation,
)


class RiskAssessmentService:
    """Orchestrates deterministic financial exposure, materiality, and risk scoring."""

    def assess_exception_risk(
        self,
        session: Session,
        exception_id: str,
        force_recalculate: bool = False,
    ) -> RiskAssessment:
        """Evaluates and idempotently persists risk assessment for an exception."""
        exc = session.scalars(select(ExceptionRecord).where(ExceptionRecord.exception_id == exception_id)).first()
        if not exc:
            raise ValueError(f"Exception '{exception_id}' not found.")

        # Check existing latest assessment for idempotency
        latest_stmt = (
            select(RiskAssessment)
            .where(RiskAssessment.exception_id == exception_id)
            .order_by(RiskAssessment.calculated_at.desc())
        )
        existing = session.scalars(latest_stmt).first()

        inv_run = session.scalars(
            select(InvestigationRun)
            .where(InvestigationRun.exception_id == exception_id)
            .order_by(InvestigationRun.created_at.desc())
        ).first()

        # Idempotency check: if not forced and inputs unchanged
        if not force_recalculate and existing:
            if (
                existing.deterministic_exposure == exc.exposure
                and existing.policy_version == POLICY_VERSION
                and existing.scoring_version == SCORING_VERSION
                and existing.threshold_version == THRESHOLD_VERSION
            ):
                return existing

        now = datetime.now(timezone.utc)
        sub_type = None
        if "UNALLOCATED" in exc.exception_id or exc.primary_payment_id is None:
            sub_type = "UNALLOCATED_SETTLEMENT"
        elif exc.exception_type == "MISSING_UNALLOCATED_SETTLEMENT":
            sub_type = "MISSING_SETTLEMENT"

        # 1. Deterministic Materiality & Exposure Type
        exposure_type = classify_exposure_type(
            exception_type=exc.exception_type,
            sub_type=sub_type,
            exposure=exc.exposure or 0,
        )
        materiality = classify_materiality(exc.exposure or 0)

        # 2. Risk Factors & 0-100 Score Breakdown
        factors = extract_risk_factors(session=session, exception=exc, investigation_run=inv_run)
        risk_score, breakdown = calculate_risk_score(factors)

        # 3. Priority & Escalation Recommendation
        priority = determine_priority(risk_score=risk_score, exposure=exc.exposure or 0)
        root_cause_cat = inv_run.final_classification if inv_run else None
        escalation = determine_escalation(
            exception_type=exc.exception_type,
            severity=exc.severity,
            priority=priority,
            exposure=exc.exposure or 0,
            root_cause_category=root_cause_cat,
        )

        # 4. Structured Natural-Language Explanation
        explanation = generate_risk_explanation(
            exception=exc,
            materiality=materiality,
            priority=priority,
            score=risk_score,
            breakdown=breakdown,
            escalation=escalation,
            root_cause_category=root_cause_cat,
        )

        # 5. Persist RiskAssessment
        assessment_id = f"RA-{exc.exception_id}-{uuid.uuid4().hex[:8]}"
        assessment = RiskAssessment(
            assessment_id=assessment_id,
            exception_id=exc.exception_id,
            deterministic_exposure=exc.exposure or 0,
            currency="INR",
            exposure_type=exposure_type,
            gross_exposure=exc.exposure or 0,
            recoverable_amount=0,
            net_exposure=exc.exposure or 0,
            materiality=materiality,
            risk_score=risk_score,
            score_breakdown=json.dumps(breakdown),
            risk_factors=json.dumps(factors.model_dump()),
            priority=priority,
            escalation=escalation,
            explanation=explanation,
            policy_version=POLICY_VERSION,
            scoring_version=SCORING_VERSION,
            threshold_version=THRESHOLD_VERSION,
            calculated_at=now,
            created_at=now,
        )
        session.add(assessment)

        # 6. Audit Logging
        audit_repo = AuditRepository(session)
        audit_event = AuditEvent(
            audit_event_id=f"audit_{uuid.uuid4().hex[:16]}",
            exception_id=exc.exception_id,
            investigation_id=inv_run.investigation_id if inv_run else None,
            event_type="RISK_ASSESSED",
            timestamp=now,
            actor_type=TransitionActorType.SYSTEM.value,
            actor_id="risk_scoring_engine_v1",
            event_summary=f"Risk Assessed: Score {risk_score}/100, Priority {priority}, Materiality {materiality}",
            event_payload=json.dumps({
                "assessment_id": assessment_id,
                "risk_score": risk_score,
                "priority": priority,
                "materiality": materiality,
                "escalation": escalation,
            }),
        )
        audit_repo.append_audit_event(audit_event)
        session.flush()

        return assessment

    def get_latest_risk_assessment(
        self,
        session: Session,
        exception_id: str,
    ) -> Optional[RiskAssessment]:
        """Retrieves latest risk assessment for an exception."""
        stmt = (
            select(RiskAssessment)
            .where(RiskAssessment.exception_id == exception_id)
            .order_by(RiskAssessment.calculated_at.desc())
        )
        return session.scalars(stmt).first()

    def assess_all_open_exceptions(
        self,
        session: Session,
    ) -> List[RiskAssessment]:
        """Assesses risk for all open exceptions in the system."""
        stmt = select(ExceptionRecord).where(ExceptionRecord.state.notin_([ExceptionState.VERIFIED_CLOSED.value]))
        exceptions = list(session.scalars(stmt).all())
        assessments: List[RiskAssessment] = []
        for exc in exceptions:
            assessments.append(self.assess_exception_risk(session, exc.exception_id))
        return assessments
