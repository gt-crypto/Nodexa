"""Adversarial Verifier service — independent second-opinion safety layer.

Provides an independent adversarial assessment of exception conclusions by:
1. Independently retrieving and inspecting operational evidence.
2. Identifying supporting, contradictory, and missing evidence.
3. Producing a verdict (AGREE, TIGHTEN, DISPUTE, ABSTAIN).
4. Deterministically composing a conservative final policy.
5. Persisting the opinion and logging an audit event.

The verifier is strictly read-only and NEVER executes remediations,
approves actions, modifies financial records, or accesses ground truth.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models.exceptions import ExceptionRecord
from backend.models.investigation import InvestigationRun
from backend.models.risk import RiskAssessment
from backend.models.policy import PolicyDecisionRecord
from backend.models.audit import AuditEvent
from backend.models.enums import TransitionActorType
from backend.models.verifier import VerifierOpinion
from backend.verifier.tools import VerifierToolRegistry
from backend.verifier.composer import compose_conservative_policy, get_restrictiveness_rank

VERIFIER_VERSION = "v2.0"


class AdversarialVerifierService:
    """Independent adversarial second-opinion engine for exception decisions."""

    def __init__(self):
        self.tool_registry = VerifierToolRegistry()

    def evaluate_exception(
        self,
        session: Session,
        exception_id: str,
    ) -> Dict[str, Any]:
        """Produces an independent adversarial opinion for the given exception.

        Returns the full verifier opinion including verdict, reasoning,
        evidence references, original policy, and final conservative policy.
        """
        self.tool_registry.reset_call_counter()

        # ── 1. Load Exception ──────────────────────────────────────────────
        exc_result = self.tool_registry.execute_tool("get_exception", session=session, exception_id=exception_id)
        if exc_result.get("status") != "success" or not exc_result.get("data", {}).get("found"):
            return self._create_error_opinion(exception_id, "Exception not found.")

        exc_data = exc_result["data"]
        evidence_refs: List[str] = [exc_data["exception_id"]]
        if exc_data.get("primary_payment_id"):
            evidence_refs.append(exc_data["primary_payment_id"])

        # ── 2. Load Latest Policy Decision ─────────────────────────────────
        pol_result = self.tool_registry.execute_tool("get_policy_decision", session=session, exception_id=exception_id)
        original_policy = "BLOCK"  # Default conservative if no policy exists
        policy_data = None
        if pol_result.get("status") == "success" and pol_result.get("data", {}).get("found"):
            policy_data = pol_result["data"]["decisions"][0]  # Latest
            original_policy = policy_data["decision"]

        # ── 3. Independently Retrieve Evidence ─────────────────────────────
        payment_data = None
        settlement_data = None
        ledger_data = None
        risk_data = None
        control_data = None
        audit_data = None

        # Payment
        if exc_data.get("primary_payment_id"):
            pay_result = self.tool_registry.execute_tool("get_payment", session=session, payment_id=exc_data["primary_payment_id"])
            if pay_result.get("status") == "success" and pay_result.get("data", {}).get("found"):
                payment_data = pay_result["data"]

        # Settlement
        if exc_data.get("primary_payment_id"):
            set_result = self.tool_registry.execute_tool("get_settlement", session=session, settlement_id=exc_data["primary_payment_id"])
            if set_result.get("status") == "success" and set_result.get("data", {}).get("found"):
                settlement_data = set_result["data"]
                for s in settlement_data.get("settlements", []):
                    evidence_refs.append(s["settlement_id"])

        # Ledger
        if exc_data.get("primary_payment_id"):
            led_result = self.tool_registry.execute_tool("get_ledger_entries", session=session, payment_id=exc_data["primary_payment_id"])
            if led_result.get("status") == "success":
                ledger_data = led_result["data"]

        # Risk Assessment
        risk_result = self.tool_registry.execute_tool("get_risk_assessment", session=session, exception_id=exception_id)
        if risk_result.get("status") == "success" and risk_result.get("data", {}).get("found"):
            risk_data = risk_result["data"]

        # Control Findings
        ctrl_result = self.tool_registry.execute_tool("get_control_findings", session=session, exception_id=exception_id)
        if ctrl_result.get("status") == "success":
            control_data = ctrl_result["data"]

        # Audit trail
        audit_result = self.tool_registry.execute_tool("get_audit_events", session=session, exception_id=exception_id)
        if audit_result.get("status") == "success":
            audit_data = audit_result["data"]

        # ── 4. Adversarial Evidence Assessment ─────────────────────────────
        verdict, confidence, reasoning, recommended_action = self._assess_evidence(
            exc_data=exc_data,
            payment_data=payment_data,
            settlement_data=settlement_data,
            ledger_data=ledger_data,
            risk_data=risk_data,
            control_data=control_data,
            policy_data=policy_data,
            original_policy=original_policy,
        )

        # ── 5. Deterministic Conservative Policy Composition ───────────────
        final_policy, original_rank, final_rank = compose_conservative_policy(
            original_policy=original_policy,
            verdict=verdict,
            recommended_action=recommended_action,
        )

        # Safety assertion: final can never be less restrictive
        assert final_rank >= original_rank, (
            f"CRITICAL: Verifier violated restrictiveness invariant! "
            f"original_rank={original_rank}, final_rank={final_rank}"
        )

        # ── 6. Persist Opinion ─────────────────────────────────────────────
        evidence_refs = list(dict.fromkeys(evidence_refs))  # Deduplicate
        opinion_id = f"vop_{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)

        opinion = VerifierOpinion(
            opinion_id=opinion_id,
            exception_id=exception_id,
            verdict=verdict,
            confidence=confidence,
            reasoning_summary=reasoning,
            evidence_refs=json.dumps(evidence_refs),
            recommended_action=recommended_action,
            original_policy_decision=original_policy,
            final_policy_decision=final_policy,
            verifier_version=VERIFIER_VERSION,
            created_at=now,
        )
        session.add(opinion)

        # ── 7. Audit Event ─────────────────────────────────────────────────
        audit_event = AuditEvent(
            audit_event_id=f"audit_verifier_{uuid.uuid4().hex[:16]}",
            exception_id=exception_id,
            event_type="VERIFIER_OPINION_RECORDED",
            timestamp=now,
            actor_type=TransitionActorType.SYSTEM.value,
            actor_id="adversarial_verifier_v2",
            event_summary=(
                f"Adversarial Verifier verdict '{verdict}' for {exception_id}. "
                f"Original: {original_policy} → Final: {final_policy}"
            ),
            event_payload=json.dumps({
                "opinion_id": opinion_id,
                "verdict": verdict,
                "confidence": confidence,
                "original_policy": original_policy,
                "final_policy": final_policy,
                "evidence_refs": evidence_refs,
                "verifier_version": VERIFIER_VERSION,
            }),
        )
        session.add(audit_event)
        session.flush()

        return {
            "opinion_id": opinion_id,
            "exception_id": exception_id,
            "verdict": verdict,
            "confidence": confidence,
            "reasoning_summary": reasoning,
            "evidence_refs": evidence_refs,
            "recommended_action": recommended_action,
            "original_policy_decision": original_policy,
            "final_policy_decision": final_policy,
            "verifier_version": VERIFIER_VERSION,
            "created_at": now.isoformat(),
        }

    def get_opinion(self, session: Session, exception_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves the latest verifier opinion for an exception."""
        stmt = (
            select(VerifierOpinion)
            .where(VerifierOpinion.exception_id == exception_id)
            .order_by(VerifierOpinion.created_at.desc())
        )
        opinion = session.scalars(stmt).first()
        if not opinion:
            return None

        return {
            "opinion_id": opinion.opinion_id,
            "exception_id": opinion.exception_id,
            "verdict": opinion.verdict,
            "confidence": opinion.confidence,
            "reasoning_summary": opinion.reasoning_summary,
            "evidence_refs": json.loads(opinion.evidence_refs),
            "recommended_action": opinion.recommended_action,
            "original_policy_decision": opinion.original_policy_decision,
            "final_policy_decision": opinion.final_policy_decision,
            "verifier_version": opinion.verifier_version,
            "created_at": opinion.created_at.isoformat() if opinion.created_at else None,
        }

    # ────────────────────────────────────────────────────────────────────────
    # Evidence Assessment Logic
    # ────────────────────────────────────────────────────────────────────────

    def _assess_evidence(
        self,
        exc_data: Dict[str, Any],
        payment_data: Optional[Dict[str, Any]],
        settlement_data: Optional[Dict[str, Any]],
        ledger_data: Optional[Dict[str, Any]],
        risk_data: Optional[Dict[str, Any]],
        control_data: Optional[Dict[str, Any]],
        policy_data: Optional[Dict[str, Any]],
        original_policy: str,
    ) -> tuple:
        """Performs independent adversarial evidence assessment.

        Identifies:
        - Supporting evidence (confirms existing conclusion)
        - Contradictory evidence (conflicts with conclusion)
        - Missing evidence (required but unavailable)

        Returns:
            (verdict, confidence, reasoning_summary, recommended_action)
        """
        supporting: List[str] = []
        contradictory: List[str] = []
        missing: List[str] = []

        exc_type = exc_data.get("exception_type", "")
        exposure = exc_data.get("exposure_minor_units", 0) or 0
        state = exc_data.get("state", "")

        # ── Check 1: Payment Evidence ──────────────────────────────────────
        if payment_data:
            payment_status = payment_data.get("status", "")
            payment_amount = payment_data.get("amount_minor_units", 0) or 0

            if exc_type == "GHOST_SETTLEMENT":
                # Ghost settlement: payment should be FAILED but settlements exist
                if payment_status == "FAILED":
                    supporting.append(
                        f"Payment {payment_data['payment_id']} confirmed FAILED status, "
                        f"consistent with ghost settlement classification."
                    )
                else:
                    contradictory.append(
                        f"Payment {payment_data['payment_id']} has status '{payment_status}', "
                        f"not FAILED — ghost settlement classification may be incorrect."
                    )

            if exc_type == "REFUND_CHARGEBACK_DOUBLE_DIP":
                if payment_status in ("REFUNDED", "PARTIALLY_REFUNDED", "DISPUTED"):
                    supporting.append(
                        f"Payment {payment_data['payment_id']} status '{payment_status}' "
                        f"consistent with double-dip refund/chargeback scenario."
                    )
        else:
            if exc_data.get("primary_payment_id"):
                missing.append("Primary payment record not found in operational database.")

        # ── Check 2: Settlement Evidence ───────────────────────────────────
        if settlement_data:
            set_count = settlement_data.get("count", 0)
            if exc_type == "GHOST_SETTLEMENT" and set_count > 0:
                supporting.append(
                    f"{set_count} settlement batch(es) found for a FAILED payment, "
                    f"confirming ghost settlement anomaly."
                )
            elif exc_type == "MISSING_SETTLEMENT" and set_count > 0:
                contradictory.append(
                    f"Settlement records exist ({set_count} batches), but exception "
                    f"classified as MISSING_SETTLEMENT — classification may be stale."
                )
        else:
            if exc_type in ("GHOST_SETTLEMENT", "SETTLEMENT_SLA_BREACH"):
                missing.append("Settlement batch evidence not retrieved.")

        # ── Check 3: Ledger Evidence ───────────────────────────────────────
        if ledger_data:
            ledger_count = ledger_data.get("count", 0)
            if ledger_count == 0:
                missing.append("No nodal ledger entries found for primary payment.")
            else:
                # Check for debit/credit imbalance
                entries = ledger_data.get("entries", [])
                total_debits = sum(e.get("debit_minor_units", 0) or 0 for e in entries)
                total_credits = sum(e.get("credit_minor_units", 0) or 0 for e in entries)
                if total_debits > 0 and total_credits > 0:
                    contradictory.append(
                        f"Ledger evidence shows both debits (₹{total_debits/100:,.2f}) and "
                        f"credits (₹{total_credits/100:,.2f}) for this payment, indicating "
                        f"incomplete or ambiguous financial resolution."
                    )
                elif total_credits > 0 and exc_type == "GHOST_SETTLEMENT":
                    supporting.append(
                        f"Ledger credit of ₹{total_credits/100:,.2f} found for ghost settlement."
                    )
        else:
            missing.append("Ledger entries not available for independent verification.")

        # ── Check 4: Risk Assessment ───────────────────────────────────────
        if risk_data:
            risk_score = risk_data.get("risk_score", 0)
            priority = risk_data.get("priority", "P4")
            if risk_score >= 70:
                supporting.append(
                    f"High risk score ({risk_score}/100, {priority}) supports "
                    f"conservative handling."
                )
            elif risk_score < 30 and exposure > 0:
                contradictory.append(
                    f"Low risk score ({risk_score}/100) despite non-zero exposure "
                    f"(₹{exposure/100:,.2f}) — risk assessment may underweight exposure."
                )
        else:
            missing.append("Risk assessment not found.")

        # ── Check 5: Control Findings ──────────────────────────────────────
        if control_data:
            findings = control_data.get("findings", [])
            if findings:
                supporting.append(
                    f"{len(findings)} deterministic control finding(s) support "
                    f"the exception classification."
                )
            else:
                missing.append("No deterministic control findings linked to this exception.")

        # ── Check 6: Policy Exposure / Approval ────────────────────────────
        original_rank = get_restrictiveness_rank(original_policy)
        if exposure > 500000 and original_rank == 0:
            # High exposure but ALLOW — verifier should challenge
            contradictory.append(
                f"Original policy is ALLOW despite exposure exceeding ₹5,000 "
                f"(₹{exposure/100:,.2f}). High-exposure cases should require human review."
            )

        # ── Determine Verdict ──────────────────────────────────────────────
        return self._determine_verdict(
            supporting=supporting,
            contradictory=contradictory,
            missing=missing,
            original_policy=original_policy,
            exposure=exposure,
        )

    def _determine_verdict(
        self,
        supporting: List[str],
        contradictory: List[str],
        missing: List[str],
        original_policy: str,
        exposure: int,
    ) -> tuple:
        """Determines verdict based on evidence analysis.

        Returns: (verdict, confidence, reasoning_summary, recommended_action)
        """
        # Build concise reasoning
        reasoning_parts: List[str] = []

        if supporting:
            reasoning_parts.append(f"Supporting evidence: {'; '.join(supporting[:3])}")
        if contradictory:
            reasoning_parts.append(f"Contradictory evidence: {'; '.join(contradictory[:3])}")
        if missing:
            reasoning_parts.append(f"Missing evidence: {'; '.join(missing[:3])}")

        reasoning = " | ".join(reasoning_parts) if reasoning_parts else "No independent evidence assessed."

        # Decision logic
        if contradictory and not supporting:
            # Strong contradiction with no support
            return "DISPUTE", "HIGH", reasoning, "BLOCK"

        elif contradictory and supporting:
            # Mixed evidence — tighten for safety
            if len(contradictory) >= len(supporting):
                return "DISPUTE", "MEDIUM", reasoning, "HUMAN_REVIEW"
            else:
                return "TIGHTEN", "MEDIUM", reasoning, "HUMAN_REVIEW"

        elif missing and len(missing) >= 2:
            # Significant missing evidence — insufficient basis for confidence
            if supporting:
                return "TIGHTEN", "LOW", reasoning, "HUMAN_REVIEW"
            else:
                return "ABSTAIN", "LOW", reasoning, original_policy

        elif not supporting and not contradictory:
            # No evidence assessed at all
            return "ABSTAIN", "LOW", reasoning, original_policy

        else:
            # Supporting evidence with no contradictions
            confidence = "HIGH" if len(supporting) >= 3 else "MEDIUM"
            return "AGREE", confidence, reasoning, original_policy

    def _create_error_opinion(self, exception_id: str, error_message: str) -> Dict[str, Any]:
        """Creates a safe error response when the verifier cannot evaluate."""
        return {
            "opinion_id": f"vop_err_{uuid.uuid4().hex[:8]}",
            "exception_id": exception_id,
            "verdict": "ABSTAIN",
            "confidence": "LOW",
            "reasoning_summary": f"Verifier could not evaluate: {error_message}",
            "evidence_refs": [],
            "recommended_action": "BLOCK",
            "original_policy_decision": "UNKNOWN",
            "final_policy_decision": "BLOCK",
            "verifier_version": VERIFIER_VERSION,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
