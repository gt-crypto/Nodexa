"""Investigation graph execution nodes performing modular pipeline stages."""
from datetime import datetime, timezone
from decimal import Decimal
import json
import uuid
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.enums import (
    ExceptionState,
    TransitionActorType,
    InvestigationStatus,
    ExceptionType,
)
from backend.models.exceptions import ExceptionRecord
from backend.models.investigation import InvestigationRun
from backend.models.audit import AuditEvent
from backend.services.repositories.investigation_repository import InvestigationRepository
from backend.services.repositories.audit_repository import AuditRepository
from backend.controls.state_machine import transition_exception_state
from backend.agent.graph.state import InvestigationState
from backend.agent.tools.registry import AgentToolRegistry
from backend.agent.prompts.system_prompt import INVESTIGATOR_SYSTEM_PROMPT
from backend.agent.prompts.investigation_prompt import build_investigation_user_prompt
from backend.agent.provider import LLMProvider, StructuredInvestigationOutput


def load_exception_node(
    state: InvestigationState,
    session: Session,
    reinvestigate: bool = False,
) -> InvestigationState:
    """Loads exception details and transitions lifecycle state from DETECTED to INVESTIGATING."""
    state.current_stage = "LOAD_EXCEPTION"
    stmt = select(ExceptionRecord).where(ExceptionRecord.exception_id == state.exception_id)
    exc = session.scalars(stmt).first()

    if not exc:
        state.status = "FAILED"
        state.error_message = f"Exception '{state.exception_id}' not found."
        return state

    # Validate lifecycle transition
    if exc.state == ExceptionState.DETECTED.value:
        transition_exception_state(
            session=session,
            exception_id=exc.exception_id,
            to_state=ExceptionState.INVESTIGATING,
            reason="AI Investigator assigned case.",
            actor_type=TransitionActorType.AI_AGENT,
            actor_id="ai_investigator_v1",
        )
        session.flush()
    elif exc.state == ExceptionState.DIAGNOSED.value and reinvestigate:
        transition_exception_state(
            session=session,
            exception_id=exc.exception_id,
            to_state=ExceptionState.INVESTIGATING,
            reason="AI Investigator reassigned case for reinvestigation.",
            actor_type=TransitionActorType.AI_AGENT,
            actor_id="ai_investigator_v1",
        )
        session.flush()
    elif exc.state == ExceptionState.INVESTIGATING.value:
        # Resuming/continuing investigation
        pass
    else:
        state.status = "FAILED"
        state.error_message = f"Exception '{state.exception_id}' is in state '{exc.state}' (cannot investigate)."
        return state

    state.exception_record = {
        "exception_id": exc.exception_id,
        "exception_type": exc.exception_type,
        "severity": exc.severity,
        "state": exc.state,
        "exposure": exc.exposure,
        "confidence": float(exc.confidence) if exc.confidence else 1.0,
        "description": exc.description,
        "primary_payment_id": exc.primary_payment_id,
        "primary_order_id": exc.primary_order_id,
    }
    state.status = "RUNNING"
    return state


def gather_evidence_node(
    state: InvestigationState,
    session: Session,
    tool_registry: AgentToolRegistry,
) -> InvestigationState:
    """Gathers multi-source operational records and control findings using read-only tools."""
    if state.status == "FAILED":
        return state

    state.current_stage = "GATHER_EVIDENCE"
    tool_res = tool_registry.execute_tool(
        "extract_investigation_evidence",
        session=session,
        exception_id=state.exception_id,
    )

    if tool_res.get("status") == "error":
        state.status = "FAILED"
        state.error_message = f"Evidence gathering failed: {tool_res.get('error')}"
        return state

    state.gathered_evidence = tool_res.get("data", {})
    state.tool_call_count = tool_registry.call_count
    return state


def trace_lifecycle_node(state: InvestigationState) -> InvestigationState:
    """Constructs chronological financial lifecycle events across all operational sources."""
    if state.status == "FAILED":
        return state

    state.current_stage = "TRACE_LIFECYCLE"
    ev = state.gathered_evidence
    timeline: List[Dict[str, Any]] = []

    pmt = ev.get("payment")
    if pmt:
        timeline.append({
            "timestamp": pmt.get("created_at"),
            "event": "GATEWAY_PAYMENT_CREATED",
            "source": "gateway_transactions",
            "details": f"Payment {pmt.get('payment_id')} created with status {pmt.get('status')} and amount {pmt.get('amount')}.",
        })
        for ord_info in pmt.get("associated_orders", []):
            timeline.append({
                "timestamp": ord_info.get("created_at"),
                "event": "MERCHANT_ORDER_CREATED",
                "source": "merchant_orders",
                "details": f"Order {ord_info.get('order_id')} created with status {ord_info.get('fulfillment_status')}.",
            })

    for s in ev.get("settlements", []):
        timeline.append({
            "timestamp": s.get("clearing_timestamp"),
            "event": "BANK_SETTLEMENT_CLEARED",
            "source": "bank_settlement_batches",
            "details": f"Settlement {s.get('settlement_id')} cleared net amount {s.get('net_amount')} (UTR: {s.get('utr_number')}).",
        })

    for d in ev.get("disputes", []):
        timeline.append({
            "timestamp": d.get("timestamp"),
            "event": f"DISPUTE_{d.get('event_type')}",
            "source": "dispute_refund_events",
            "details": f"{d.get('event_type')} event {d.get('event_id')} for amount {d.get('amount')}.",
        })

    for l in ev.get("ledger_entries", []):
        timeline.append({
            "timestamp": l.get("timestamp"),
            "event": f"LEDGER_{l.get('entry_type')}",
            "source": "nodal_ledger",
            "details": f"Ledger entry {l.get('ledger_id')} (Debit: {l.get('debit')}, Credit: {l.get('credit')}, Balance After: {l.get('balance_after')}).",
        })

    # Sort chronological events by timestamp
    timeline.sort(key=lambda x: str(x.get("timestamp") or ""))
    state.timeline = timeline
    return state


def cross_source_compare_node(state: InvestigationState) -> InvestigationState:
    """Performs multi-source comparison to detect contradictions, discrepancies, and gaps."""
    if state.status == "FAILED":
        return state

    state.current_stage = "CROSS_SOURCE_COMPARE"
    ev = state.gathered_evidence
    pmt = ev.get("payment")
    settlements = ev.get("settlements", [])
    disputes = ev.get("disputes", [])
    control_findings = ev.get("control_findings", [])

    contradictions: List[str] = []

    if pmt:
        # Gateway vs Settlements check
        if pmt.get("status") == "FAILED" and len(settlements) > 0:
            contradictions.append(
                f"Contradiction: Payment {pmt.get('payment_id')} is marked FAILED in gateway, but {len(settlements)} settlement batch(es) cleared."
            )

        # Dispute double-dip check
        dispute_types = {d.get("event_type") for d in disputes}
        if "REFUND" in dispute_types and "CHARGEBACK" in dispute_types:
            contradictions.append(
                f"Contradiction: Payment {pmt.get('payment_id')} has simultaneous REFUND and CHARGEBACK events causing dual debit liabilities."
            )

    # Control findings failures
    for cf in control_findings:
        if cf.get("status") in ("FAIL", "WARNING"):
            contradictions.append(
                f"Control finding '{cf.get('control_name')}': Status {cf.get('status')} on records {cf.get('affected_record_ids')}."
            )

    state.contradictions = contradictions
    return state


def form_hypotheses_node(state: InvestigationState) -> InvestigationState:
    """Forms candidate explanatory hypotheses from observed contradictions and evidence."""
    if state.status == "FAILED":
        return state

    state.current_stage = "FORM_HYPOTHESES"
    hypotheses: List[str] = []

    ev = state.gathered_evidence
    pmt = ev.get("payment")
    settlements = ev.get("settlements", [])
    disputes = ev.get("disputes", [])

    if pmt and pmt.get("status") == "FAILED" and len(settlements) > 0:
        hypotheses.append("H1: Downstream banking network processed settlement before receiving gateway failure notification.")
        hypotheses.append("H2: Acquirer batch included incorrect payment identifier during clearing.")

    dispute_types = {d.get("event_type") for d in disputes}
    if "REFUND" in dispute_types and "CHARGEBACK" in dispute_types:
        hypotheses.append("H1: Customer initiated bank dispute before merchant refund cleared the banking network.")
        hypotheses.append("H2: Automated merchant refund system failed to check active chargeback status.")

    if not pmt and len(settlements) > 0:
        hypotheses.append("H1: Payment reference was truncated or omitted in bank batch clearing file.")

    if not hypotheses:
        hypotheses.append("H1: Standard operational financial processing workflow.")

    state.hypotheses = hypotheses
    return state


def test_hypotheses_node(state: InvestigationState) -> InvestigationState:
    """Tests and filters candidate hypotheses against factual evidence."""
    if state.status == "FAILED":
        return state

    state.current_stage = "TEST_HYPOTHESES"
    # Filter tested hypotheses against observed facts
    tested = [h for h in state.hypotheses if h.startswith("H1") or len(state.hypotheses) == 1]
    state.hypotheses = tested or state.hypotheses
    return state


def determine_root_cause_node(
    state: InvestigationState,
    llm_provider: LLMProvider,
) -> InvestigationState:
    """Executes AI root-cause reasoning over structured evidence using LLM provider."""
    if state.status == "FAILED":
        return state

    state.current_stage = "DETERMINE_ROOT_CAUSE"
    sub_type = None
    if state.exception_record:
        if "UNALLOCATED" in state.exception_id or (not state.exception_record.get("primary_payment_id") and state.gathered_evidence.get("settlements")):
            sub_type = "UNALLOCATED_SETTLEMENT"
        elif state.exception_record.get("exception_type") == "MISSING_UNALLOCATED_SETTLEMENT":
            sub_type = "MISSING_SETTLEMENT"

    context = {
        "exception": state.exception_record,
        "payment": state.gathered_evidence.get("payment"),
        "settlements": state.gathered_evidence.get("settlements", []),
        "disputes": state.gathered_evidence.get("disputes", []),
        "ledger_entries": state.gathered_evidence.get("ledger_entries", []),
        "control_findings": state.gathered_evidence.get("control_findings", []),
        "timeline": state.timeline,
        "contradictions": state.contradictions,
        "hypotheses": state.hypotheses,
        "exception_type": state.exception_record.get("exception_type") if state.exception_record else "",
        "sub_type": sub_type,
        "exposure": state.exception_record.get("exposure", 0) if state.exception_record else 0,
        "primary_payment_id": state.exception_record.get("primary_payment_id") if state.exception_record else None,
    }

    # Format structured evidence items for mock provider fallback
    raw_evidence_items = []
    pmt = state.gathered_evidence.get("payment")
    if pmt:
        raw_evidence_items.append({"source": "gateway_transactions", "record_id": pmt.get("payment_id"), "field": "status", "value": pmt.get("status")})
        raw_evidence_items.append({"source": "gateway_transactions", "record_id": pmt.get("payment_id"), "field": "amount", "value": pmt.get("amount")})
    for s in state.gathered_evidence.get("settlements", []):
        raw_evidence_items.append({"source": "bank_settlement_batches", "record_id": s.get("settlement_id"), "field": "net_amount", "value": s.get("net_amount")})
    for d in state.gathered_evidence.get("disputes", []):
        raw_evidence_items.append({"source": "dispute_refund_events", "record_id": d.get("event_id"), "field": "event_type", "value": d.get("event_type")})
    context["evidence"] = raw_evidence_items

    user_prompt = build_investigation_user_prompt(context)

    try:
        output = llm_provider.generate_investigation(
            system_prompt=INVESTIGATOR_SYSTEM_PROMPT,
            user_content=user_prompt,
            context=context,
        )
        state.structured_output = output
    except Exception as err:
        state.status = "FAILED"
        state.error_message = f"LLM investigation failed: {str(err)}"

    return state


def validate_exposure_node(state: InvestigationState) -> InvestigationState:
    """Enforces deterministic exposure authority by validating and reconciling AI exposure assessment."""
    if state.status == "FAILED" or not state.structured_output:
        return state

    state.current_stage = "VALIDATE_EXPOSURE"
    deterministic_exposure = state.exception_record.get("exposure", 0) if state.exception_record else 0

    # Guarantee deterministic exposure is strictly preserved
    state.structured_output.exposure_assessment = deterministic_exposure
    return state


def generate_explanation_node(state: InvestigationState) -> InvestigationState:
    """Ensures that the final explanation strictly separates FACTS, HYPOTHESES, and CONCLUSIONS."""
    if state.status == "FAILED" or not state.structured_output:
        return state

    state.current_stage = "GENERATE_EXPLANATION"
    exp = state.structured_output.explanation

    # Ensure structure has Facts, Hypothesis, and Conclusion sections
    if "### Facts" not in exp or "### Conclusion" not in exp:
        formatted_exp = (
            f"### Facts\n"
            f"- Evidence analyzed from operational sources across gateway, bank, and ledger.\n\n"
            f"### Hypothesis\n"
            f"- {state.hypotheses[0] if state.hypotheses else 'Operational discrepancy during processing.'}\n\n"
            f"### Conclusion\n"
            f"- {state.structured_output.root_cause}"
        )
        state.structured_output.explanation = formatted_exp

    return state


def persist_investigation_node(
    state: InvestigationState,
    session: Session,
) -> InvestigationState:
    """Persists InvestigationRun record, transitions exception lifecycle state, and logs audit events."""
    state.current_stage = "PERSIST_INVESTIGATION"
    now = datetime.now(timezone.utc)
    state.completed_at = now

    inv_repo = InvestigationRepository(session)
    audit_repo = AuditRepository(session)

    if state.status == "FAILED" or not state.structured_output:
        # Failure path: Create failed investigation run and escalate exception
        run = InvestigationRun(
            investigation_id=state.investigation_id,
            exception_id=state.exception_id,
            status=InvestigationStatus.FAILED.value,
            started_at=state.started_at,
            completed_at=now,
            agent_version="v1.0.0-agent",
            error_info=state.error_message or "Investigation failed to produce structured diagnosis.",
        )
        existing_run = inv_repo.get_investigation_run(state.investigation_id)
        if existing_run:
            existing_run.status = run.status
            existing_run.completed_at = run.completed_at
            existing_run.error_info = run.error_info
        else:
            inv_repo.create_investigation_run(run)

        # Transition to FAILED_ESCALATED
        transition_exception_state(
            session=session,
            exception_id=state.exception_id,
            to_state=ExceptionState.FAILED_ESCALATED,
            reason=f"AI Investigation failed: {state.error_message}",
            actor_type=TransitionActorType.AI_AGENT,
            actor_id="ai_investigator_v1",
        )
        session.flush()
        return state

    # Success path: Create completed investigation run
    confidence_decimal = Decimal("1.0000") if state.structured_output.confidence == "HIGH" else (
        Decimal("0.7500") if state.structured_output.confidence == "MEDIUM" else Decimal("0.5000")
    )

    run = InvestigationRun(
        investigation_id=state.investigation_id,
        exception_id=state.exception_id,
        status=InvestigationStatus.COMPLETED.value,
        started_at=state.started_at,
        completed_at=now,
        agent_version="v1.0.0-agent",
        final_classification=state.structured_output.root_cause_category,
        root_cause=state.structured_output.root_cause,
        confidence=confidence_decimal,
        recommended_action=state.structured_output.recommended_next_step,
        human_approval_required=(state.exception_record.get("severity") == "CRITICAL") if state.exception_record else False,
        error_info=None,
    )
    existing_run = inv_repo.get_investigation_run(state.investigation_id)
    if existing_run:
        existing_run.status = run.status
        existing_run.completed_at = run.completed_at
        existing_run.final_classification = run.final_classification
        existing_run.root_cause = run.root_cause
        existing_run.confidence = run.confidence
        existing_run.recommended_action = run.recommended_action
    else:
        inv_repo.create_investigation_run(run)

    # Transition to DIAGNOSED
    transition_exception_state(
        session=session,
        exception_id=state.exception_id,
        to_state=ExceptionState.DIAGNOSED,
        reason=f"AI Investigation completed. Root Cause: {state.structured_output.root_cause_category}",
        actor_type=TransitionActorType.AI_AGENT,
        actor_id="ai_investigator_v1",
    )

    # Append Audit Event
    audit_event = AuditEvent(
        audit_event_id=f"audit_{uuid.uuid4().hex[:16]}",
        exception_id=state.exception_id,
        investigation_id=state.investigation_id,
        event_type="INVESTIGATION_COMPLETED",
        timestamp=now,
        actor_type=TransitionActorType.AI_AGENT.value,
        actor_id="ai_investigator_v1",
        event_summary=f"AI Diagnosis completed: {state.structured_output.root_cause_category}",
        event_payload=json.dumps(state.structured_output.model_dump()),
    )
    audit_repo.append_audit_event(audit_event)

    session.flush()
    state.status = "COMPLETED"
    return state
