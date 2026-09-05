"""Ask Sentinel copilot service handling question parsing, read-only evidence retrieval, grounded answer generation, and query audit logging."""
import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from backend.models.copilot import CopilotQuery
from backend.models.audit import AuditEvent
from backend.models.exceptions import ExceptionRecord
from backend.copilot.tools import AskSentinelToolRegistry
from backend.copilot.agent import CopilotToolCallingAgent
from backend.copilot.provider import CopilotLLMProvider


MUTATION_KEYWORDS = [
    "approve",
    "refund",
    "execute",
    "override",
    "delete",
    "mutate",
    "create",
    "modify",
    "drop table",
    "update",
    "insert",
    "alter",
    "transfer money",
    "close exception",
    "bypass",
]

UNSUPPORTED_OUT_OF_SCOPE_KEYWORDS = [
    "secret",
    "api key",
    "password",
    "legal advice",
    "future prediction",
    "stock price",
]


class AskSentinelService:
    """Read-only grounded copilot service for Nodal Sentinel operational state."""

    def __init__(self, max_tool_calls: int = 15):
        self.tool_registry = AskSentinelToolRegistry(max_tool_calls=max_tool_calls)
        self.agent = CopilotToolCallingAgent(tool_registry=self.tool_registry)

    def _extract_identifiers(self, text: str) -> Tuple[List[str], List[str], List[str], List[str], List[str]]:
        """Extracts exception_id, payment_id, settlement_id, order_id, merchant_id patterns from user input."""
        exceptions = re.findall(r"EXC-[A-Za-z0-9_-]+", text, re.IGNORECASE)
        # Strip exceptions before matching payment IDs so PAY inside EXC-... doesn't become a standalone payment ID
        text_without_exc = re.sub(r"EXC-[A-Za-z0-9_-]+", "", text, flags=re.IGNORECASE)
        payments = re.findall(r"(?:PAY|TXN)[-_][A-Za-z0-9_-]+", text_without_exc, re.IGNORECASE)
        settlements = re.findall(r"(?:SET|STL)[-_][A-Za-z0-9_-]+", text_without_exc, re.IGNORECASE)
        orders = re.findall(r"(?:ORD|ORDER)[-_][A-Za-z0-9_-]+", text_without_exc, re.IGNORECASE)

        # Look for "merchant <ID>" or "merchant M123"
        merchants = []
        merch_matches = re.findall(r"merchant\s+([A-Za-z0-9_-]+)", text, re.IGNORECASE)
        stop_words = {
            "id", "ids", "discrepancies", "anomalies", "accounts", "names", "currently", "with", "having",
            "status", "risk", "processed", "has", "had", "have", "the", "that", "most", "highest", "sold", "is", "are"
        }
        merchants.extend([m for m in merch_matches if m.lower() not in stop_words])
        merchants.extend(re.findall(r"(?:MERCH|MERCHANT)[-_][A-Za-z0-9_-]+", text, re.IGNORECASE))

        return (
            [e.upper() for e in set(exceptions)],
            [p.upper() for p in set(payments)],
            [s.upper() for s in set(settlements)],
            [o.upper() for o in set(orders)],
            [m.strip() for m in set(merchants)],
        )

    def _format_minor_units(self, paise: Any) -> str:
        """Formats integer or Decimal minor unit paise into readable Rupee representation."""
        numeric_paise = float(paise or 0)
        rupees = numeric_paise / 100.0
        return f"₹{rupees:,.2f} ({int(numeric_paise)} paise)"

    def ask(
        self,
        session: Session,
        question: str,
        exception_id_context: Optional[str] = None,
        request_id: Optional[str] = None,
        actor_id: str = "operator",
    ) -> Dict[str, Any]:
        """Processes a natural language question against live operational evidence using LLM tool calling."""
        query_id = f"copilot_q_{uuid.uuid4().hex[:16]}"
        self.tool_registry.reset_call_counter()

        q_lower = question.lower()

        # 1. Safety & Mutation check
        for kw in MUTATION_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", q_lower):
                # Allow informational queries containing "refund" (e.g. "how much did we refund?", "total refunds", "refund rate")
                if kw == "refund":
                    is_info_refund = any(
                        p in q_lower
                        for p in (
                            "how much", "what was", "how many", "total", "summary",
                            "rate", "volume", "count", "amount of", "net sales",
                            "after refund", "highest refund", "refunds"
                        )
                    )
                    if is_info_refund:
                        continue

                return self._persist_and_respond(
                    session=session,
                    query_id=query_id,
                    question=question,
                    answer=(
                        "I am Ask Sentinel, a strictly read-only copilot. I cannot execute remediations, approve actions, "
                        "modify financial ledgers, or override policies. Operational mutations must be executed through "
                        "governed policy and human approval workflows."
                    ),
                    evidence_refs=[],
                    reasoning="Requested action involves financial or policy state mutation, which is prohibited for Ask Sentinel.",
                    confidence="LOW",
                    abstained=True,
                    limitations="Mutation commands are rejected at the tool permission layer.",
                    tools_used=[],
                    request_id=request_id,
                    actor_id=actor_id,
                    status="ABSTAINED",
                )

        # 2. Out-of-scope check
        for kw in UNSUPPORTED_OUT_OF_SCOPE_KEYWORDS:
            if kw in q_lower:
                return self._persist_and_respond(
                    session=session,
                    query_id=query_id,
                    question=question,
                    answer=(
                        "I cannot answer questions regarding system credentials, external predictions, or legal/out-of-scope matters. "
                        "I can only retrieve and explain live Nodexa operational facts."
                    ),
                    evidence_refs=[],
                    reasoning="Query asks for information outside operational database scope.",
                    confidence="LOW",
                    abstained=True,
                    limitations="Out-of-scope query.",
                    tools_used=[],
                    request_id=request_id,
                    actor_id=actor_id,
                    status="ABSTAINED",
                )

        # 3. Extract identifiers from input & context
        exc_ids, pay_ids, set_ids, ord_ids, merch_ids = self._extract_identifiers(question)

        if exception_id_context and exception_id_context.upper() not in exc_ids:
            exc_ids.append(exception_id_context.upper())

        context = {}
        if exception_id_context:
            context["exception_id"] = exception_id_context

        # 4. LLM Tool-Calling Layer (Selects minimum necessary read-only tools)
        planned_tools, reasoning_plan, was_real_llm = self.agent.plan_tools(
            question=question,
            exc_ids=exc_ids,
            pay_ids=pay_ids,
            set_ids=set_ids,
            ord_ids=ord_ids,
            merch_ids=merch_ids,
            context=context,
        )

        # 5. Execute Read-Only Tools against Database
        retrieved_data, tools_used, evidence_refs = self.agent.execute_tools(
            session=session,
            planned_tools=planned_tools,
        )

        # 6. Check for missing evidence abstention if specific payment or exception was not found
        if "get_payment" in retrieved_data and not retrieved_data["get_payment"].get("found"):
            if pay_ids and not any(k in q_lower for k in ("compare", "vs", "versus")):
                target_pay = pay_ids[0]
                return self._persist_and_respond(
                    session=session,
                    query_id=query_id,
                    question=question,
                    answer=f"I cannot establish an answer from available Nodexa operational records. No matching payment record was found for '{target_pay}'.",
                    evidence_refs=[],
                    reasoning="Payment lookup returned no records from database.",
                    confidence="LOW",
                    abstained=True,
                    limitations="Record does not exist in operational database.",
                    tools_used=tools_used,
                    request_id=request_id,
                    actor_id=actor_id,
                    status="ABSTAINED",
                )

        if "get_exception" in retrieved_data and not retrieved_data["get_exception"].get("found"):
            if exc_ids:
                target_exc = exc_ids[0]
                return self._persist_and_respond(
                    session=session,
                    query_id=query_id,
                    question=question,
                    answer=f"I cannot establish an answer from available Nodexa operational records. No matching exception record was found for '{target_exc}'.",
                    evidence_refs=[],
                    reasoning="Exception lookup returned no records from database.",
                    confidence="LOW",
                    abstained=True,
                    limitations="Record does not exist in operational database.",
                    tools_used=tools_used,
                    request_id=request_id,
                    actor_id=actor_id,
                    status="ABSTAINED",
                )

        if not retrieved_data:
            return self._persist_and_respond(
                session=session,
                query_id=query_id,
                question=question,
                answer=(
                    "I cannot establish an answer from available Nodexa operational records. "
                    "No matching exception, payment, or settlement records were found for your query."
                ),
                evidence_refs=[],
                reasoning="Retrieved zero matching records from operational database.",
                confidence="LOW",
                abstained=True,
                limitations="Insufficient operational evidence available to answer the question.",
                tools_used=tools_used,
                request_id=request_id,
                actor_id=actor_id,
                status="ABSTAINED",
            )

        # 7. Grounded Answer Synthesis with Answer Relevance Guard
        answer, reasoning, confidence, abstained, limitations = self.agent.synthesize_response(
            question=question,
            retrieved_data=retrieved_data,
            tools_used=tools_used,
            was_real_llm=was_real_llm,
        )

        provider_status = CopilotLLMProvider.get_provider_status()
        provider_meta = {
            "provider": provider_status["provider_name"],
            "model": provider_status["model"],
            "is_real_llm": was_real_llm,
        }

        return self._persist_and_respond(
            session=session,
            query_id=query_id,
            question=question,
            answer=answer,
            evidence_refs=evidence_refs,
            reasoning=reasoning,
            confidence=confidence,
            abstained=abstained,
            limitations=limitations,
            tools_used=tools_used,
            request_id=request_id,
            actor_id=actor_id,
            status="ABSTAINED" if abstained else "SUCCESS",
            provider_metadata=provider_meta,
        )

    def _persist_and_respond(
        self,
        session: Session,
        query_id: str,
        question: str,
        answer: str,
        evidence_refs: List[str],
        reasoning: str,
        confidence: str,
        abstained: bool,
        limitations: Optional[str],
        tools_used: List[str],
        request_id: Optional[str],
        actor_id: str,
        status: str,
        provider_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Persists copilot query audit record to database and logs COPILOT_QUERY_EXECUTED audit event."""
        if provider_metadata is None:
            p_status = CopilotLLMProvider.get_provider_status()
            provider_metadata = {
                "provider": p_status["provider_name"],
                "model": p_status["model"],
                "is_real_llm": False,
            }

        # 1. DB Model persistence
        copilot_rec = CopilotQuery(
            query_id=query_id,
            question=question,
            request_id=request_id,
            actor_id=actor_id,
            tools_used=json.dumps(tools_used),
            evidence_refs=json.dumps(evidence_refs),
            response_status=status,
            abstained=abstained,
            confidence=confidence,
            copilot_version="v2.0",
        )
        session.add(copilot_rec)

        # 2. Append-only Audit Log Event
        audit_event = AuditEvent(
            audit_event_id=f"audit_copilot_{uuid.uuid4().hex[:16]}",
            event_type="COPILOT_QUERY_EXECUTED",
            actor_type="OPERATOR",
            actor_id=actor_id,
            event_summary=f"Ask Sentinel query executed: '{question[:60]}...' (Status: {status})",
            event_payload=json.dumps({
                "query_id": query_id,
                "question": question,
                "tools_used": tools_used,
                "evidence_refs": evidence_refs,
                "abstained": abstained,
                "confidence": confidence,
                "provider_metadata": provider_metadata,
            }),
        )
        session.add(audit_event)
        session.commit()

        return {
            "query_id": query_id,
            "question": question,
            "answer": answer,
            "evidence_refs": evidence_refs,
            "reasoning": reasoning,
            "confidence": confidence,
            "abstained": abstained,
            "limitations": limitations,
            "tools_used": tools_used,
            "request_id": request_id,
            "provider_metadata": provider_metadata,
        }
