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
from backend.copilot.intent import CopilotIntent, CopilotIntentClassifier


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

    def _extract_identifiers(self, text: str) -> Tuple[List[str], List[str], List[str], List[str], List[str]]:
        """Extracts exception_id, payment_id, settlement_id, order_id, merchant_id patterns from user input."""
        exceptions = re.findall(r"EXC-[A-Za-z0-9_-]+", text, re.IGNORECASE)
        payments = re.findall(r"(?:PAY|TXN)[-_][A-Za-z0-9_-]+", text, re.IGNORECASE)
        settlements = re.findall(r"(?:SET|STL)[-_][A-Za-z0-9_-]+", text, re.IGNORECASE)
        orders = re.findall(r"(?:ORD|ORDER)[-_][A-Za-z0-9_-]+", text, re.IGNORECASE)
        
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
        """Processes a natural language question against live operational evidence."""
        query_id = f"copilot_q_{uuid.uuid4().hex[:16]}"
        self.tool_registry.reset_call_counter()

        q_lower = question.lower()

        # 1. Safety & Mutation check
        for kw in MUTATION_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", q_lower):
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

        # 2. Extract identifiers and select read-only tools
        exc_ids, pay_ids, set_ids, ord_ids, merch_ids = self._extract_identifiers(question)

        if exception_id_context and exception_id_context.upper() not in exc_ids:
            exc_ids.append(exception_id_context.upper())

        tools_used: List[str] = []
        evidence_refs: List[str] = []
        retrieved_data: Dict[str, Any] = {}

        # Formulate structured multi-tool QueryPlan
        plan = CopilotIntentClassifier.plan_query(
            question=question,
            exc_ids=exc_ids,
            pay_ids=pay_ids,
            set_ids=set_ids,
            ord_ids=ord_ids,
            merch_ids=merch_ids,
        )
        intent = plan.intent

        # 1. TRANSACTION_METRICS (Averages, counts, min/max, thresholds)
        if intent == CopilotIntent.TRANSACTION_METRICS:
            tx_params = plan.params
            tx_res = self.tool_registry.execute_tool(
                "get_transaction_metrics",
                session=session,
                status=tx_params.get("status"),
                min_amount_paise=tx_params.get("min_amount_paise"),
                merchant_id=merch_ids[0] if merch_ids else None,
            )
            tools_used.append("get_transaction_metrics")
            if tx_res.get("status") == "success":
                retrieved_data["transaction_metrics"] = tx_res["data"]
                evidence_refs.append("GATEWAY_TRANSACTIONS")

            # Also execute sales summary for captured totals
            sales_res = self.tool_registry.execute_tool("get_sales_summary", session=session)
            tools_used.append("get_sales_summary")
            if sales_res.get("status") == "success":
                retrieved_data["sales_summary"] = sales_res["data"]

        # 2. CROSS_SOURCE_RECONCILIATION (Gateway vs Bank Settlement, SLA, Ledger)
        elif intent == CopilotIntent.CROSS_SOURCE_RECONCILIATION:
            cr_res = self.tool_registry.execute_tool("get_cross_source_reconciliation", session=session)
            tools_used.append("get_cross_source_reconciliation")
            if cr_res.get("status") == "success":
                retrieved_data["cross_source_reconciliation"] = cr_res["data"]
                evidence_refs.extend(["GATEWAY_TRANSACTIONS", "BANK_SETTLEMENT_BATCHES", "NODAL_LEDGER"])

            st_res = self.tool_registry.execute_tool("get_settlements_summary", session=session)
            tools_used.append("get_settlements_summary")
            if st_res.get("status") == "success":
                retrieved_data["settlements_summary"] = st_res["data"]

        # 3. MERCHANT_ANALYTICS (Rankings, top merchants by sales, exposure, refunds vs sales)
        elif intent == CopilotIntent.MERCHANT_ANALYTICS:
            mo_res = self.tool_registry.execute_tool("get_merchants_overview", session=session)
            tools_used.append("get_merchants_overview")
            if mo_res.get("status") == "success":
                retrieved_data["merchants_overview"] = mo_res["data"]
                evidence_refs.append("MERCHANT_SCORES")

        # 4. SETTLEMENT_SUMMARY (General settlement metrics, timing delays, batch count)
        elif intent == CopilotIntent.SETTLEMENT_SUMMARY:
            if set_ids:
                target_set_id = set_ids[0]
                set_res = self.tool_registry.execute_tool("get_settlement", session=session, settlement_id=target_set_id)
                tools_used.append("get_settlement")
                if set_res.get("status") == "success" and set_res.get("data", {}).get("found"):
                    retrieved_data["settlement_lookup"] = set_res["data"]
                    evidence_refs.append(target_set_id)
            else:
                st_res = self.tool_registry.execute_tool("get_settlements_summary", session=session)
                tools_used.append("get_settlements_summary")
                if st_res.get("status") == "success":
                    retrieved_data["settlements_summary"] = st_res["data"]
                    evidence_refs.append("BANK_SETTLEMENT_BATCHES")

        # 5. SALES_SUMMARY
        elif intent == CopilotIntent.SALES_SUMMARY:
            merchant_param = merch_ids[0] if merch_ids else None
            sales_res = self.tool_registry.execute_tool("get_sales_summary", session=session, merchant_id=merchant_param)
            tools_used.append("get_sales_summary")
            if sales_res.get("status") == "success":
                retrieved_data["sales_summary"] = sales_res["data"]
                evidence_refs.append("GATEWAY_TRANSACTIONS_SALES")

        # 6. NET_SALES_SUMMARY
        elif intent == CopilotIntent.NET_SALES_SUMMARY:
            merchant_param = merch_ids[0] if merch_ids else None
            sales_res = self.tool_registry.execute_tool("get_sales_summary", session=session, merchant_id=merchant_param)
            tools_used.append("get_sales_summary")
            refunds_res = self.tool_registry.execute_tool("get_refunds_summary", session=session, merchant_id=merchant_param)
            tools_used.append("get_refunds_summary")
            if sales_res.get("status") == "success" and refunds_res.get("status") == "success":
                retrieved_data["net_sales_summary"] = {
                    "sales": sales_res["data"],
                    "refunds": refunds_res["data"],
                }
                evidence_refs.extend(["GATEWAY_TRANSACTIONS_SALES", "DISPUTE_REFUND_EVENTS"])

        # 7. REFUND_SUMMARY
        elif intent == CopilotIntent.REFUND_SUMMARY:
            merchant_param = merch_ids[0] if merch_ids else None
            refunds_res = self.tool_registry.execute_tool("get_refunds_summary", session=session, merchant_id=merchant_param)
            tools_used.append("get_refunds_summary")
            if refunds_res.get("status") == "success":
                retrieved_data["refunds_summary"] = refunds_res["data"]
                evidence_refs.append("DISPUTE_REFUND_EVENTS")

        # 8. VERIFICATION_STATUS
        elif intent == CopilotIntent.VERIFICATION_STATUS:
            if exc_ids:
                target_exc_id = exc_ids[0]
                exc_res = self.tool_registry.execute_tool("get_exception", session=session, exception_id=target_exc_id)
                tools_used.append("get_exception")
                if exc_res.get("status") == "success" and exc_res.get("data", {}).get("found"):
                    retrieved_data["exception"] = exc_res["data"]
                    evidence_refs.append(target_exc_id)

                ver_res = self.tool_registry.execute_tool("get_verifier_opinion", session=session, exception_id=target_exc_id)
                tools_used.append("get_verifier_opinion")
                if ver_res.get("status") == "success" and ver_res.get("data", {}).get("found"):
                    retrieved_data["verifier_opinion"] = ver_res["data"]
                    if ver_res["data"].get("opinion_id"):
                        evidence_refs.append(ver_res["data"]["opinion_id"])

                retrieved_data["verification_status_query"] = {
                    "target_id": target_exc_id,
                    "target_type": "exception",
                }
            elif pay_ids:
                target_pay_id = pay_ids[0]
                pay_res = self.tool_registry.execute_tool("get_payment", session=session, payment_id=target_pay_id)
                tools_used.append("get_payment")
                if pay_res.get("status") == "success" and pay_res.get("data", {}).get("found"):
                    retrieved_data["payment"] = pay_res["data"]
                    evidence_refs.append(target_pay_id)

                stmt_exc = select(ExceptionRecord).where(
                    or_(
                        ExceptionRecord.primary_payment_id == target_pay_id,
                        ExceptionRecord.exception_id.contains(target_pay_id),
                        ExceptionRecord.description.contains(target_pay_id),
                    )
                )
                linked_exc = session.scalars(stmt_exc).first()
                if linked_exc:
                    retrieved_data["linked_exception"] = {
                        "exception_id": linked_exc.exception_id,
                        "type": linked_exc.exception_type,
                        "state": linked_exc.state,
                        "exposure": linked_exc.exposure,
                        "description": linked_exc.description,
                    }
                    evidence_refs.append(linked_exc.exception_id)
                    ver_res = self.tool_registry.execute_tool("get_verifier_opinion", session=session, exception_id=linked_exc.exception_id)
                    tools_used.append("get_verifier_opinion")
                    if ver_res.get("status") == "success" and ver_res.get("data", {}).get("found"):
                        retrieved_data["verifier_opinion"] = ver_res["data"]
                        if ver_res["data"].get("opinion_id"):
                            evidence_refs.append(ver_res["data"]["opinion_id"])

                retrieved_data["verification_status_query"] = {
                    "target_id": target_pay_id,
                    "target_type": "payment",
                }
            else:
                # Aggregate verification query: search closed and pending verifications
                search_res = self.tool_registry.execute_tool("search_exceptions", session=session, limit=20)
                tools_used.append("search_exceptions")
                agg_res = self.tool_registry.execute_tool("get_aggregate_summary", session=session)
                tools_used.append("get_aggregate_summary")
                retrieved_data["general_verification_query"] = {
                    "search": search_res.get("data", {}),
                    "aggregate": agg_res.get("data", {}),
                }

        # 5. Exception investigation question
        elif exc_ids:
            target_exc_id = exc_ids[0]
            exc_res = self.tool_registry.execute_tool("get_exception", session=session, exception_id=target_exc_id)
            tools_used.append("get_exception")

            if exc_res.get("status") == "success" and exc_res.get("data", {}).get("found"):
                exc_data = exc_res["data"]
                retrieved_data["exception"] = exc_data
                evidence_refs.append(exc_data["exception_id"])
                if exc_data.get("primary_payment_id"):
                    evidence_refs.append(exc_data["primary_payment_id"])

                # Fetch risk assessment
                risk_res = self.tool_registry.execute_tool("get_risk_assessment", session=session, exception_id=target_exc_id)
                tools_used.append("get_risk_assessment")
                if risk_res.get("status") == "success" and risk_res.get("data", {}).get("found"):
                    retrieved_data["risk"] = risk_res["data"]
                    if risk_res["data"].get("assessment_id"):
                        evidence_refs.append(risk_res["data"]["assessment_id"])

                # Fetch control findings
                ctrl_res = self.tool_registry.execute_tool("get_control_findings", session=session, exception_id=target_exc_id)
                tools_used.append("get_control_findings")
                if ctrl_res.get("status") == "success":
                    retrieved_data["control_findings"] = ctrl_res.get("data", {}).get("findings", [])

                # Fetch policy decision
                pol_res = self.tool_registry.execute_tool("get_policy_decision", session=session, exception_id=target_exc_id)
                tools_used.append("get_policy_decision")
                if pol_res.get("status") == "success" and pol_res.get("data", {}).get("found"):
                    retrieved_data["policy"] = pol_res["data"]

                # Fetch verifier opinion if available or if queried
                ver_res = self.tool_registry.execute_tool("get_verifier_opinion", session=session, exception_id=target_exc_id)
                tools_used.append("get_verifier_opinion")
                if ver_res.get("status") == "success" and ver_res.get("data", {}).get("found"):
                    retrieved_data["verifier_opinion"] = ver_res["data"]
                    if ver_res["data"].get("opinion_id"):
                        evidence_refs.append(ver_res["data"]["opinion_id"])

        # 6. Payment lookup question
        elif pay_ids:
            target_pay_id = pay_ids[0]
            pay_res = self.tool_registry.execute_tool("get_payment", session=session, payment_id=target_pay_id)
            tools_used.append("get_payment")
            if pay_res.get("status") == "success" and pay_res.get("data", {}).get("found"):
                pay_data = pay_res["data"]
                retrieved_data["payment"] = pay_data
                evidence_refs.append(pay_data["payment_id"])

                # Fetch linked settlement and ledger
                set_res = self.tool_registry.execute_tool("get_settlement", session=session, settlement_id=target_pay_id)
                tools_used.append("get_settlement")
                if set_res.get("status") == "success" and set_res.get("data", {}).get("found"):
                    retrieved_data["settlement"] = set_res["data"]
                    for s in set_res["data"].get("settlements", []):
                        evidence_refs.append(s["settlement_id"])

                led_res = self.tool_registry.execute_tool("get_ledger_entries", session=session, payment_id=target_pay_id)
                tools_used.append("get_ledger_entries")
                if led_res.get("status") == "success":
                    retrieved_data["ledger"] = led_res["data"]

            # Also check if there is an exception linked to this payment
            stmt_exc = select(ExceptionRecord).where(
                or_(
                    ExceptionRecord.primary_payment_id == target_pay_id,
                    ExceptionRecord.exception_id.contains(target_pay_id),
                    ExceptionRecord.description.contains(target_pay_id),
                )
            )
            linked_exc = session.scalars(stmt_exc).first()
            if linked_exc:
                retrieved_data["linked_exception"] = {
                    "exception_id": linked_exc.exception_id,
                    "type": linked_exc.exception_type,
                    "state": linked_exc.state,
                    "exposure": linked_exc.exposure,
                    "description": linked_exc.description,
                }
                evidence_refs.append(linked_exc.exception_id)

        # 7. Settlement lookup question (e.g. SET-000014)
        elif set_ids:
            target_set_id = set_ids[0]
            set_res = self.tool_registry.execute_tool("get_settlement", session=session, settlement_id=target_set_id)
            tools_used.append("get_settlement")
            if set_res.get("status") == "success" and set_res.get("data", {}).get("found"):
                retrieved_data["settlement_lookup"] = set_res["data"]
                evidence_refs.append(target_set_id)

            # Check if there is an exception linked to this settlement ID
            stmt_exc = select(ExceptionRecord).where(
                or_(
                    ExceptionRecord.description.contains(target_set_id),
                    ExceptionRecord.exception_id.contains(target_set_id),
                )
            )
            linked_exc = session.scalars(stmt_exc).first()
            if linked_exc:
                retrieved_data["linked_exception"] = {
                    "exception_id": linked_exc.exception_id,
                    "type": linked_exc.exception_type,
                    "state": linked_exc.state,
                    "exposure": linked_exc.exposure,
                    "description": linked_exc.description,
                }
                evidence_refs.append(linked_exc.exception_id)

        # 8. Specific Merchant Trust Score or Merchant Discrepancy questions
        elif merch_ids or intent == CopilotIntent.MERCHANT_SUMMARY:
            if merch_ids:
                target_merch_id = merch_ids[0]
                m_res = self.tool_registry.execute_tool("get_merchant_trust_score", session=session, merchant_id=target_merch_id)
                tools_used.append("get_merchant_trust_score")
                if m_res.get("status") == "success" and m_res.get("data", {}).get("found"):
                    m_data = m_res["data"]["score"]
                    retrieved_data["merchant_score"] = m_data
                    evidence_refs.append(f"MERCHANT_SCORE_{target_merch_id}")
            else:
                md_res = self.tool_registry.execute_tool("get_merchant_discrepancies", session=session)
                tools_used.append("get_merchant_discrepancies")
                if md_res.get("status") == "success":
                    retrieved_data["merchant_discrepancies"] = md_res["data"]
                    for m in md_res["data"].get("merchants", [])[:3]:
                        evidence_refs.append(f"MERCHANT_{m['merchant_id']}")

        # 9. Pattern Miner / Recurring cluster questions
        elif intent == CopilotIntent.PATTERN_SUMMARY:
            cl_res = self.tool_registry.execute_tool("get_clusters", session=session)
            tools_used.append("get_clusters")
            if cl_res.get("status") == "success":
                retrieved_data["clusters"] = cl_res.get("data", {}).get("clusters", [])
                for cl in retrieved_data["clusters"]:
                    evidence_refs.append(cl["cluster_id"])
                    for exc_id in cl.get("exception_ids", [])[:2]:
                        evidence_refs.append(exc_id)

        # 10. Business Impact & ROI questions
        elif intent == CopilotIntent.BUSINESS_IMPACT:
            imp_res = self.tool_registry.execute_tool("get_business_impact", session=session)
            tools_used.append("get_business_impact")
            if imp_res.get("status") == "success" and imp_res.get("data", {}).get("found"):
                retrieved_data["business_impact"] = imp_res["data"]["impact"]
                evidence_refs.append("BUSINESS_IMPACT_ROI")

        # 11. Predictive Nodal Drift Radar questions
        elif intent == CopilotIntent.DRIFT_PREDICTION:
            drift_res = self.tool_registry.execute_tool("get_drift_prediction", session=session)
            tools_used.append("get_drift_prediction")
            if drift_res.get("status") == "success" and drift_res.get("data", {}).get("found"):
                retrieved_data["drift_prediction"] = drift_res["data"]["drift"]
                evidence_refs.append(drift_res["data"]["drift"]["prediction_id"])

        # 12. Confidence Calibration / Reliability questions
        elif intent == CopilotIntent.CONFIDENCE_CALIBRATION:
            calib_res = self.tool_registry.execute_tool("get_confidence_calibration", session=session)
            tools_used.append("get_confidence_calibration")
            if calib_res.get("status") == "success" and calib_res.get("data", {}).get("found"):
                retrieved_data["confidence_calibration"] = calib_res["data"]["calibration"]
                evidence_refs.append(calib_res["data"]["calibration"]["snapshot_id"])

        # 13. Escalation Webhook questions
        elif intent == CopilotIntent.ESCALATION_STATUS:
            exc_id_param = exc_ids[0] if exc_ids else None
            esc_res = self.tool_registry.execute_tool("get_escalation_status", session=session, exception_id=exc_id_param)
            tools_used.append("get_escalation_status")
            if esc_res.get("status") == "success":
                retrieved_data["escalation_status"] = esc_res.get("data", {})

        # 14. Specific Exception Family questions (e.g. ghost settlement, SLA breach, etc.)
        elif intent == CopilotIntent.EXCEPTION_FAMILY_SEARCH:
            matched_family = None
            if "ghost" in q_lower:
                matched_family = "GHOST_SETTLEMENT"
            elif any(k in q_lower for k in ["double dip", "double-dip", "chargeback"]):
                matched_family = "REFUND_CHARGEBACK_DOUBLE_DIP"
            elif any(k in q_lower for k in ["sla", "breach"]):
                matched_family = "SETTLEMENT_SLA_BREACH"
            elif "partial" in q_lower:
                matched_family = "PARTIAL_SETTLEMENT"
            elif any(k in q_lower for k in ["unallocated", "missing"]):
                matched_family = "MISSING_UNALLOCATED_SETTLEMENT"
            elif "timing" in q_lower:
                matched_family = "LEGITIMATE_TIMING_EXCEPTION"

            if matched_family:
                search_res = self.tool_registry.execute_tool("search_exceptions", session=session, family=matched_family, limit=5)
                tools_used.append("search_exceptions")
                if search_res.get("status") == "success":
                    retrieved_data["search_exceptions"] = search_res["data"]
                    retrieved_data["searched_family"] = matched_family
                    for e in search_res["data"].get("exceptions", [])[:3]:
                        evidence_refs.append(e["exception_id"])

        # 15. Aggregate / Overview questions
        elif intent == CopilotIntent.EXCEPTION_SUMMARY:
            agg_res = self.tool_registry.execute_tool("get_aggregate_summary", session=session)
            tools_used.append("get_aggregate_summary")
            if agg_res.get("status") == "success":
                retrieved_data["aggregate"] = agg_res["data"]

        # Fallback handling:
        # Do NOT blindly route unclassified queries to get_aggregate_summary.
        # Check semantic query intent:
        if not retrieved_data:
            q_norm_check = re.sub(r"[^\w\s-]", " ", question.lower())
            q_norm_check = re.sub(r"\s+", " ", q_norm_check).strip()
            volume_words = ["process", "processed", "processing", "volume", "sales", "sold", "gmv", "flowed", "payments"]
            exception_words = ["exception", "exceptions", "exposure", "unresolved", "anomaly", "anomalies", "stuck", "lost"]

            has_volume_keyword = any(w in q_norm_check for w in volume_words)
            has_exception_keyword = any(w in q_norm_check for w in exception_words)

            if intent == CopilotIntent.EXCEPTION_SUMMARY or (has_exception_keyword and not has_volume_keyword):
                agg_res = self.tool_registry.execute_tool("get_aggregate_summary", session=session)
                tools_used.append("get_aggregate_summary")
                if agg_res.get("status") == "success":
                    retrieved_data["aggregate"] = agg_res["data"]
            elif has_volume_keyword and not has_exception_keyword:
                merchant_param = merch_ids[0] if merch_ids else None
                sales_res = self.tool_registry.execute_tool("get_sales_summary", session=session, merchant_id=merchant_param)
                tools_used.append("get_sales_summary")
                if sales_res.get("status") == "success":
                    retrieved_data["sales_summary"] = sales_res["data"]
                    evidence_refs.append("GATEWAY_TRANSACTIONS_SALES")

        # Consistency Validation:
        # The selected tool and answer must be semantically relevant to the question.
        # A question asking about volume/processed money must NEVER return exception data or exposure.
        q_norm_str = re.sub(r"[^\w\s-]", " ", question.lower())
        q_norm_str = re.sub(r"\s+", " ", q_norm_str).strip()
        is_volume_query = any(w in q_norm_str for w in [
            "process", "processed", "processing", "volume", "sales", "sell", "sold", "gmv", "flowed", "transaction value"
        ]) and not any(w in q_norm_str for w in [
            "exception", "exceptions", "exposure", "unresolved", "anomaly", "anomalies", "stuck", "tied up"
        ])
        if is_volume_query:
            # If aggregate exception data was inadvertently retrieved, purge it and reroute to get_sales_summary
            if "aggregate" in retrieved_data:
                del retrieved_data["aggregate"]
                tools_used = [t for t in tools_used if t != "get_aggregate_summary"]
            if "sales_summary" not in retrieved_data and "net_sales_summary" not in retrieved_data:
                merchant_param = merch_ids[0] if merch_ids else None
                sales_res = self.tool_registry.execute_tool("get_sales_summary", session=session, merchant_id=merchant_param)
                if "get_sales_summary" not in tools_used:
                    tools_used.append("get_sales_summary")
                if sales_res.get("status") == "success":
                    retrieved_data["sales_summary"] = sales_res["data"]
                    evidence_refs.append("GATEWAY_TRANSACTIONS_SALES")

        # 3. Formulate Answer & Check Abstention
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

        # Synthesize Grounded Answer
        answer, reasoning, confidence, limitations = self._synthesize_answer(question, retrieved_data)

        # Final sanity check: answer must not contain exception data if it is a volume query
        if is_volume_query:
            invalid_terms = ["unresolved exceptions", "open exposure", "exception family breakdown", "unresolved open exceptions"]
            for term in invalid_terms:
                if term in answer.lower():
                    # Fallback to pure sales summary formatting
                    if "sales_summary" in retrieved_data:
                        sales = retrieved_data["sales_summary"]
                        inr = sales["total_sales_inr"]
                        paise = sales["total_sales_paise"]
                        count = sales["transaction_count"]
                        answer = (
                            f"Total processed payment volume: **₹{inr:,.2f}** ({paise:,} paise) across **{count}** captured transactions.\n\n"
                            f"Source: Gateway transactions (`{sales['source']}`).\n"
                            f"Definition: {sales['definition']}."
                        )
                        break

        # Deduplicate evidence refs
        evidence_refs = list(dict.fromkeys(evidence_refs))

        return self._persist_and_respond(
            session=session,
            query_id=query_id,
            question=question,
            answer=answer,
            evidence_refs=evidence_refs,
            reasoning=reasoning,
            confidence=confidence,
            abstained=False,
            limitations=limitations,
            tools_used=tools_used,
            request_id=request_id,
            actor_id=actor_id,
            status="SUCCESS",
        )

    def _synthesize_answer(self, question: str, data: Dict[str, Any]) -> Tuple[str, str, str, Optional[str]]:
        """Synthesizes factual grounded response from structured tool results."""
        # 1. Transaction Metrics (counts, averages, min/max, threshold filters)
        if "transaction_metrics" in data:
            tm = data["transaction_metrics"]
            tot_cnt = tm["total_count"]
            tot_inr = tm["total_inr"]
            avg_inr = tm["average_inr"]
            breakdown = tm.get("status_breakdown", {})
            largest = tm.get("largest_transaction")
            smallest = tm.get("smallest_transaction")
            filtered = tm.get("filtered_criteria", {})

            q_lower = question.lower()
            lines = []

            if "average" in q_lower:
                lines.append(f"Average transaction amount: **₹{avg_inr:,.2f}** ({tm['average_paise']:,} paise) across **{tot_cnt}** transactions.")
            elif any(w in q_lower for w in ["largest", "biggest", "highest", "max"]):
                if largest:
                    lines.append(
                        f"Largest transaction: **₹{largest['amount_inr']:,.2f}** ({largest['payment_id']}) "
                        f"for merchant `{largest['merchant_id']}` (status: {largest['status']})."
                    )
                else:
                    lines.append("No transactions found.")
            elif any(w in q_lower for w in ["smallest", "minimum", "lowest"]):
                if smallest:
                    lines.append(
                        f"Smallest transaction: **₹{smallest['amount_inr']:,.2f}** ({smallest['payment_id']}) "
                        f"for merchant `{smallest['merchant_id']}` (status: {smallest['status']})."
                    )
                else:
                    lines.append("No transactions found.")
            elif filtered.get("min_amount_paise") is not None:
                min_inr = round(filtered["min_amount_paise"] / 100.0, 2)
                lines.append(f"There are **{tot_cnt}** transactions above **₹{min_inr:,.2f}** totaling **₹{tot_inr:,.2f}**.")
                if tm.get("sample_transactions"):
                    lines.append("\n**Matching Transactions (Top 5)**:")
                    for t in tm["sample_transactions"][:5]:
                        lines.append(f"- `{t['payment_id']}`: ₹{t['amount_inr']:,.2f} (Merchant: `{t['merchant_id']}`, Status: {t['status']})")
            elif "failed" in q_lower:
                failed_info = breakdown.get("FAILED", {"count": 0, "total_inr": 0.0})
                lines.append(f"There are **{failed_info['count']}** failed transaction(s) totaling **₹{failed_info['total_inr']:,.2f}**.")
                if tm.get("sample_transactions"):
                    failed_samples = [t for t in tm["sample_transactions"] if t["status"] == "FAILED"]
                    if failed_samples:
                        lines.append("\n**Failed Transactions**:")
                        for t in failed_samples[:5]:
                            lines.append(f"- `{t['payment_id']}`: ₹{t['amount_inr']:,.2f} (Merchant: `{t['merchant_id']}`)")
            else:
                lines.append(f"Total transactions in dataset: **{tot_cnt}** totaling **₹{tot_inr:,.2f}** (Average: **₹{avg_inr:,.2f}**).")
                if breakdown:
                    lines.append("\n**Status Breakdown**:")
                    for st, b in breakdown.items():
                        lines.append(f"- **{st}**: {b['count']} transactions (₹{b['total_inr']:,.2f})")

            lines.append("\nSource: Gateway transactions (`gateway_transactions`).")
            answer = "\n".join(lines)
            reasoning = f"Calculated transaction distribution metrics across {tot_cnt} records."
            return answer, reasoning, "HIGH", None

        # 2. Cross-Source Reconciliation (Gateway vs Settlements, SLA, Ledger)
        elif "cross_source_reconciliation" in data:
            csr = data["cross_source_reconciliation"]
            unsettled_cnt = csr["unsettled_captured_count"]
            partial_cnt = csr["partially_settled_count"]
            mismatch_cnt = csr["amount_mismatches_count"]
            sla_cnt = csr["sla_breach_count"]
            ledger_rec = csr["nodal_ledger_reconciliation"]

            q_lower = question.lower()
            lines = []

            if any(w in q_lower for w in ["unsettled", "not settled", "has not settled", "no settlement", "without settlement"]):
                lines.append(f"There are **{unsettled_cnt}** captured payment(s) that have zero settlement records linked.")
                if csr.get("unsettled_captured_payments"):
                    lines.append("\n**Unsettled Captured Payments**:")
                    for p in csr["unsettled_captured_payments"][:5]:
                        lines.append(f"- `{p['payment_id']}`: ₹{p['amount_inr']:,.2f} (Merchant: `{p['merchant_id']}`)")
            elif "partial" in q_lower:
                lines.append(f"There are **{partial_cnt}** partially settled payment(s) where cleared settlement is less than gateway amount.")
                if csr.get("partially_settled_payments"):
                    lines.append("\n**Partially Settled Payments**:")
                    for p in csr["partially_settled_payments"][:5]:
                        lines.append(f"- `{p['payment_id']}`: Gateway ₹{p['payment_amount_inr']:,.2f} vs Settled ₹{p['settled_amount_inr']:,.2f} (Difference: ₹{p['difference_inr']:,.2f})")
            elif any(w in q_lower for w in ["sla", "late"]):
                lines.append(f"There are **{sla_cnt}** payment(s) that breached the bank settlement clearing SLA window.")
                if csr.get("sla_breach_payments"):
                    lines.append("\n**SLA Breached Payments**:")
                    for p in csr["sla_breach_payments"][:5]:
                        lines.append(f"- `{p['payment_id']}`: ₹{p['amount_inr']:,.2f} (Delay: {p['delay_hours']}h)")
            elif "ledger" in q_lower:
                lines.append(
                    f"Nodal Ledger Escrow Reconciliation: Expected **₹{ledger_rec['expected_balance_inr']:,.2f}** vs "
                    f"Actual Ledger **₹{ledger_rec['actual_balance_inr']:,.2f}** (Variance: **₹{ledger_rec['variance_inr']:,.2f}**, Status: **{ledger_rec['overall_status']}**)."
                )
            else:
                lines.append(
                    f"Cross-Source Reconciliation Overview across **{csr['total_captured_payments']}** captured payments:\n"
                    f"- **Unsettled Payments**: {unsettled_cnt}\n"
                    f"- **Partially Settled**: {partial_cnt}\n"
                    f"- **Amount Mismatches**: {mismatch_cnt}\n"
                    f"- **Settlement SLA Breaches**: {sla_cnt}\n"
                    f"- **Ledger Variance**: ₹{ledger_rec['variance_inr']:,.2f} (Status: {ledger_rec['overall_status']})"
                )

            lines.append("\nSource: Cross-reconciliation of gateway payments, bank settlement batches, and nodal ledger.")
            answer = "\n".join(lines)
            reasoning = "Multi-source reconciliation join across gateway_transactions, bank_settlement_batches, and nodal_ledger."
            return answer, reasoning, "HIGH", None

        # 3. Merchant Analytics Overview
        elif "merchants_overview" in data:
            mo = data["merchants_overview"]
            tot_merch = mo["total_merchants_count"]
            top_sales = mo.get("top_merchant_by_sales")
            top_exp = mo.get("top_merchant_by_exposure")
            top_exc = mo.get("top_merchant_by_exceptions")
            refund_exceeds = mo.get("merchants_refund_exceeds_sales", [])

            q_lower = question.lower()
            lines = []

            if "how many merchants" in q_lower:
                lines.append(f"There are **{tot_merch}** distinct merchants operating in the Nodexa network.")
            elif any(w in q_lower for w in ["most refunds", "refunds greater", "refund greater", "refund volume"]):
                if refund_exceeds:
                    lines.append(f"Found **{len(refund_exceeds)}** merchant(s) where refund volume exceeds gross sales:")
                    for m in refund_exceeds:
                        lines.append(f"- Merchant `{m['merchant_id']}`: Refunds ₹{m['refunds_inr']:,.2f} vs Sales ₹{m['sales_inr']:,.2f}")
                else:
                    lines.append("No merchants currently have refund volume exceeding gross sales.")
            elif any(w in q_lower for w in ["highest exposure", "most exposure"]):
                if top_exp:
                    lines.append(f"Merchant with highest exposure: **`{top_exp['merchant_id']}`** with **₹{top_exp['exposure_inr']:,.2f}** open exposure ({top_exp['exception_count']} exceptions, Band: {top_exp['score_band']}).")
                else:
                    lines.append("No merchant exception exposure found.")
            elif any(w in q_lower for w in ["most exceptions", "highest exceptions"]):
                if top_exc:
                    lines.append(f"Merchant with most exceptions: **`{top_exc['merchant_id']}`** with **{top_exc['exception_count']}** exceptions (Exposure: ₹{top_exc['exposure_inr']:,.2f}).")
                else:
                    lines.append("No exceptions found.")
            elif any(w in q_lower for w in ["top merchant", "processed the most", "highest sales", "most sales", "merchant-wise"]):
                if top_sales:
                    lines.append(f"Top merchant by processed sales: **`{top_sales['merchant_id']}`** with **₹{top_sales['sales_inr']:,.2f}** across {top_sales['sales_count']} transactions.")
                    if mo.get("merchants_ranked_by_sales"):
                        lines.append("\n**Top Merchants by Sales**:")
                        for i, m in enumerate(mo["merchants_ranked_by_sales"][:5], 1):
                            lines.append(f"{i}. `{m['merchant_id']}`: ₹{m['sales_inr']:,.2f} ({m['sales_count']} txs)")
                else:
                    lines.append("No merchant sales recorded.")
            else:
                lines.append(f"Merchant Overview across **{tot_merch}** merchants:\n")
                if top_sales:
                    lines.append(f"- **Top by Sales**: `{top_sales['merchant_id']}` (₹{top_sales['sales_inr']:,.2f})")
                if top_exp:
                    lines.append(f"- **Highest Exposure**: `{top_exp['merchant_id']}` (₹{top_exp['exposure_inr']:,.2f})")

            lines.append("\nSource: Merchant Trust Scores and Gateway Transactions.")
            answer = "\n".join(lines)
            reasoning = f"Aggregated merchant intelligence across {tot_merch} merchants."
            return answer, reasoning, "HIGH", None

        # 4. Settlements Summary
        elif "settlements_summary" in data:
            ss = data["settlements_summary"]
            tot_batches = ss["total_settlement_batches"]
            tot_inr = ss["total_net_amount_inr"]
            avg_delay = ss.get("average_settlement_delay_hours")
            unallocated = ss.get("unallocated_batches_count", 0)
            largest = ss.get("largest_settlement")

            q_lower = question.lower()
            lines = []

            if any(w in q_lower for w in ["average settlement time", "settlement delay", "how long"]):
                if avg_delay is not None:
                    lines.append(f"Average settlement clearing time: **{avg_delay} hours** from gateway transaction creation to bank clearing.")
                else:
                    lines.append("Settlement clearing timestamps are not sufficient to compute average settlement delay.")
            elif any(w in q_lower for w in ["largest", "biggest"]):
                if largest:
                    lines.append(f"Largest settlement batch: **`{largest['settlement_id']}`** with net cleared amount of **₹{largest['net_amount_inr']:,.2f}**.")
                else:
                    lines.append("No settlement batches found.")
            elif any(w in q_lower for w in ["late", "unallocated", "missing"]):
                lines.append(f"There are **{unallocated}** unallocated settlement batch(es) lacking a matching gateway payment reference.")
            else:
                lines.append(f"Total bank settlements: **₹{tot_inr:,.2f}** across **{tot_batches}** clearing batches.")
                if avg_delay is not None:
                    lines.append(f"Average clearing time: **{avg_delay} hours**.")
                lines.append(f"Total interchange fees deducted: ₹{ss.get('total_fees_inr', 0):,.2f}.")

            lines.append("\nSource: Bank settlement batches (`bank_settlement_batches`).")
            answer = "\n".join(lines)
            reasoning = f"Deterministic aggregation of {tot_batches} bank settlement batches."
            return answer, reasoning, "HIGH", None

        # 5. General Verification Query
        elif "general_verification_query" in data:
            gv = data["general_verification_query"]
            agg = gv.get("aggregate", {})
            search = gv.get("search", {})
            tot = agg.get("total_exceptions", 0)
            open_cnt = agg.get("open_exceptions_count", 0)
            closed_cnt = tot - open_cnt

            lines = [
                f"Verification Overview:\n"
                f"- **Verified Closed Cases**: {closed_cnt}\n"
                f"- **Unresolved / Pending Verification**: {open_cnt} (Exposure: {self._format_minor_units(agg.get('open_exposure_minor_units', 0))})\n"
                f"- **Total Lifetime Cases**: {tot}"
            ]
            answer = "\n".join(lines)
            reasoning = f"Aggregated verification status across {tot} lifetime cases."
            return answer, reasoning, "HIGH", None

        elif "sales_summary" in data:
            sales = data["sales_summary"]
            inr = sales["total_sales_inr"]
            paise = sales["total_sales_paise"]
            count = sales["transaction_count"]
            m_id = sales.get("merchant_id")

            merchant_clause = f" for merchant `{m_id}`" if m_id else ""
            q_lower = question.lower()
            is_volume_focused = any(w in q_lower for w in ["process", "processed", "processing", "volume", "flow", "gmv", "amount did we process"])
            
            if is_volume_focused:
                header = f"Total processed payment volume{merchant_clause}"
            else:
                header = f"Total sales{merchant_clause}"

            answer = (
                f"{header}: **₹{inr:,.2f}** ({paise:,} paise) across **{count}** captured transactions.\n\n"
                f"Source: Gateway transactions (`{sales['source']}`).\n"
                f"Definition: {sales['definition']}.\n"
                f"Calculated dynamically from current Nodexa operational records."
            )
            reasoning = f"Deterministic aggregation of captured payment transactions (status = CAPTURED) across {count} records."
            return answer, reasoning, "HIGH", None

        elif "net_sales_summary" in data:
            net_data = data["net_sales_summary"]
            sales = net_data["sales"]
            refunds = net_data["refunds"]
            gross_paise = sales["total_sales_paise"]
            refund_paise = refunds["total_refunds_paise"]
            net_paise = gross_paise - refund_paise
            net_inr = round(net_paise / 100.0, 2)
            gross_inr = sales["total_sales_inr"]
            refund_inr = refunds["total_refunds_inr"]

            answer = (
                f"Net sales: **₹{net_inr:,.2f}** ({net_paise:,} paise).\n\n"
                f"**Calculation Formula**:\n"
                f"- Gross Captured Sales: ₹{gross_inr:,.2f} ({sales['transaction_count']} transactions)\n"
                f"- Less Customer Refunds: ₹{refund_inr:,.2f} ({refunds['refund_count']} refund events)\n"
                f"- Net Total: ₹{gross_inr:,.2f} - ₹{refund_inr:,.2f} = **₹{net_inr:,.2f}**\n\n"
                f"Source: Combined gateway transactions and dispute refund records."
            )
            reasoning = "Deterministic calculation of net sales (Gross Captured Sales minus Settled Refunds)."
            return answer, reasoning, "HIGH", None

        elif "refunds_summary" in data:
            refunds = data["refunds_summary"]
            inr = refunds["total_refunds_inr"]
            paise = refunds["total_refunds_paise"]
            count = refunds["refund_count"]
            m_id = refunds.get("merchant_id")

            merchant_clause = f" for merchant `{m_id}`" if m_id else ""
            answer = (
                f"Total refunds{merchant_clause}: **₹{inr:,.2f}** ({paise:,} paise) across **{count}** refund events.\n\n"
                f"Source: Dispute and refund events (`{refunds['source']}`).\n"
                f"Definition: {refunds['definition']}.\n"
                f"Calculated from the current Nodexa dataset."
            )
            reasoning = f"Deterministic aggregation of customer refund events across {count} records."
            return answer, reasoning, "HIGH", None

        elif "verification_status_query" in data:
            v_info = data["verification_status_query"]
            target_id = v_info["target_id"]
            target_type = v_info["target_type"]

            if target_type == "payment":
                pay = data.get("payment", {})
                linked_exc = data.get("linked_exception")
                vop = data.get("verifier_opinion")

                if linked_exc:
                    exc_state = linked_exc["state"]
                    is_verified_closed = exc_state == "VERIFIED_CLOSED"
                    verdict_text = "VERIFIED CLOSED" if is_verified_closed else f"UNRESOLVED ({exc_state})"
                    lines = [
                        f"Payment `{target_id}` is linked to exception **{linked_exc['exception_id']}** ({linked_exc['type']}), which is currently in state **{exc_state}**."
                    ]
                    if vop:
                        lines.append(
                            f"Adversarial Verifier Opinion: **{vop.get('verdict')}** (Confidence: {vop.get('confidence')}, Policy: {vop.get('final_policy_decision')})."
                        )
                    if is_verified_closed:
                        lines.append("Verification status: **PASSED / VERIFIED CLOSED**.")
                    else:
                        lines.append(f"Verification status: **PENDING / {verdict_text}**.")
                    answer = "\n\n".join(lines)
                    reasoning = f"Verification and reconciliation status retrieved for payment {target_id} and linked exception {linked_exc['exception_id']}."
                    return answer, reasoning, "HIGH", None
                else:
                    status = pay.get("status", "UNKNOWN")
                    amt = self._format_minor_units(pay.get("amount_minor_units", 0))
                    answer = (
                        f"Payment `{target_id}` has status **{status}** with amount {amt}.\n\n"
                        f"No active reconciliation exceptions or dispute holds are associated with this payment. "
                        f"The transaction completed within expected operational boundaries."
                    )
                    reasoning = f"Operational payment query for {target_id} with zero linked exceptions."
                    return answer, reasoning, "HIGH", None

            elif target_type == "exception":
                exc = data.get("exception", {})
                vop = data.get("verifier_opinion")
                exc_state = exc.get("state", "UNKNOWN")
                lines = [
                    f"Exception **{target_id}** is currently in state **{exc_state}**."
                ]
                if vop:
                    lines.append(
                        f"Adversarial Verifier Opinion: **{vop.get('verdict')}** (Confidence: {vop.get('confidence')}, "
                        f"Final Policy: {vop.get('final_policy_decision')}). Rationale: {vop.get('reasoning_summary')}."
                    )
                if exc_state == "VERIFIED_CLOSED":
                    lines.append("Verification status: **PASSED / VERIFIED CLOSED**.")
                else:
                    lines.append(f"Verification status: **PENDING / NOT VERIFIED CLOSED**.")
                answer = "\n\n".join(lines)
                reasoning = f"Verification assessment retrieved for exception {target_id}."
                return answer, reasoning, "HIGH", None

        elif "exception" in data:
            exc = data["exception"]
            exc_id = exc["exception_id"]
            exc_type = exc["exception_type"]
            state = exc["state"]
            exposure_str = self._format_minor_units(exc["exposure_minor_units"])
            src = exc.get("source_flag", "seeded")

            answer_parts = [
                f"Exception **{exc_id}** is a **{exc_type}** in state **{state}** with financial exposure of **{exposure_str}**."
            ]

            if exc.get("description"):
                answer_parts.append(f"Description: {exc['description']}")

            if "risk" in data:
                risk = data["risk"]
                answer_parts.append(
                    f"Risk Priority: **{risk.get('priority')}** (Score {risk.get('risk_score')}/100, Materiality: {risk.get('materiality')})."
                )

            if "control_findings" in data and data["control_findings"]:
                findings = data["control_findings"]
                finding_msgs = [f["message"] for f in findings if isinstance(f, dict) and "message" in f]
                if finding_msgs:
                    answer_parts.append(f"Fired Controls: {'; '.join(finding_msgs[:3])}.")

            if "verifier_opinion" in data:
                vop = data["verifier_opinion"]
                answer_parts.append(
                    f"Adversarial Verifier Opinion: **{vop.get('verdict')}** (Confidence: {vop.get('confidence')}, "
                    f"Final Policy: {vop.get('final_policy_decision')}). Rationale: {vop.get('reasoning_summary')}."
                )

            if src == "live-injected":
                answer_parts.append("Note: This case was generated via Live Digital-Twin synthetic injection.")

            answer = "\n\n".join(answer_parts)
            reasoning = f"Direct factual summary compiled from exception {exc_id} and related control/risk operational records."
            confidence = "HIGH"
            limitations = None
            return answer, reasoning, confidence, limitations

        elif "payment" in data:
            pay = data["payment"]
            pay_id = pay["payment_id"]
            amt_str = self._format_minor_units(pay["amount_minor_units"])
            status = pay["status"]

            answer_parts = [
                f"Payment **{pay_id}** status is **{status}** with gross amount of **{amt_str}**."
            ]

            if "linked_exception" in data:
                exc = data["linked_exception"]
                exc_id = exc["exception_id"]
                exc_type = exc["type"]
                exc_state = exc["state"]
                exc_exp = self._format_minor_units(exc["exposure"])
                answer_parts.append(
                    f"**Operational Exception**: Associated with exception **{exc_id}** (**{exc_type}**) in state **{exc_state}** with financial exposure of **{exc_exp}**."
                )
                if exc.get("description"):
                    answer_parts.append(f"**Anomaly Reason**: {exc['description']}")

            if "settlement" in data and data["settlement"].get("found"):
                sets = data["settlement"].get("settlements", [])
                answer_parts.append(f"Linked bank settlement batches found: **{len(sets)}**.")
            else:
                answer_parts.append("Downstream bank settlement status: No settlement records linked.")

            if "ledger" in data and data["ledger"].get("count", 0) > 0:
                answer_parts.append(f"Nodal ledger entries recorded: **{data['ledger']['count']}**.")

            answer = "\n\n".join(answer_parts)
            reasoning = f"Operational data retrieved directly for gateway payment {pay_id}."
            confidence = "HIGH"
            limitations = None
            return answer, reasoning, confidence, limitations

        elif "linked_exception" in data and "payment" not in data:
            exc = data["linked_exception"]
            exc_id = exc["exception_id"]
            exc_type = exc["type"]
            exc_state = exc["state"]
            exp_str = self._format_minor_units(exc["exposure"])
            desc = exc.get("description", "Identified anomalous reconciliation state.")
            answer = (
                f"Transaction is linked to exception **{exc_id}** (**{exc_type}**) in state **{exc_state}** "
                f"with financial exposure of **{exp_str}**.\n\n"
                f"**Anomaly Cause**: {desc}"
            )
            reasoning = f"Correlated operational exception record {exc_id} identified for requested transaction."
            return answer, reasoning, "HIGH", None

        elif "settlement_lookup" in data:
            s_data = data["settlement_lookup"]
            settlements = s_data.get("settlements", [])
            target_id = evidence_refs[0] if evidence_refs else "Settlement"
            if not settlements:
                answer = f"Settlement **{target_id}** was not located in the bank settlement clearing records."
                reasoning = "Query returned zero matching bank settlement batch records."
                return answer, reasoning, "LOW", "Record not present."

            s = settlements[0]
            net_amt = self._format_minor_units(s.get("net_amount_minor_units", 0))
            utr = s.get("utr_number") or "N/A"
            acq = s.get("acquirer_id") or "N/A"

            lines = [
                f"Settlement batch **{s.get('settlement_id')}** (UTR: `{utr}`) was processed via acquirer **{acq}** with net cleared amount of **{net_amt}**."
            ]
            if "linked_exception" in data:
                exc = data["linked_exception"]
                lines.append(
                    f"**Operational Exception**: Associated with exception **{exc['exception_id']}** (**{exc['type']}**) in state **{exc['state']}** with exposure of **{self._format_minor_units(exc['exposure'])}**."
                )
                if exc.get("description"):
                    lines.append(f"**Anomaly / Unallocated Reason**: {exc['description']}")
            else:
                lines.append(
                    "**Allocation Status**: Settlement is present in the bank clearing batch but unallocated to a corresponding authorized merchant gateway payment or nodal ledger entry."
                )

            answer = "\n\n".join(lines)
            reasoning = f"Operational settlement records retrieved for {s.get('settlement_id')}."
            return answer, reasoning, "HIGH", None

        elif "merchant_score" in data:
            ms = data["merchant_score"]
            m_id = ms["merchant_id"]
            trust = ms["trust_score"]
            impact = ms["impact_score"]
            band = ms["score_band"]
            metrics = ms["metrics"]
            
            exp_str = self._format_minor_units(metrics.get("total_exposure", 0))
            
            answer_parts = [
                f"Merchant **{m_id}** is currently in the **{band}** band.",
                f"**Trust Score**: {trust}/100 | **Impact Score**: {impact}/100",
                f"**Total Exceptions**: {metrics.get('exception_count', 0)} "
                f"({metrics.get('high_risk_exception_count', 0)} high risk)",
                f"**Total Exposure**: {exp_str}",
            ]
            
            if ms.get("factors"):
                answer_parts.append("\n**Key Drivers**:")
                for f in ms["factors"]:
                    icon = "🟢" if f["direction"] == "POSITIVE" else "🔴"
                    answer_parts.append(f"{icon} {f['explanation']}")
                    
            if metrics.get("live_injected_case_count", 0) > 0:
                answer_parts.append("\n*Note: This score incorporates live-injected synthetic cases.*")
                
            answer = "\n".join(answer_parts)
            reasoning = f"Deterministic Merchant Trust Score retrieved for {m_id}."
            return answer, reasoning, "HIGH", None

        elif "business_impact" in data:
            imp = data["business_impact"]
            total_exp_str = self._format_minor_units(imp["financial_exposure_identified"])
            actionable = imp["actionable_case_count"]
            high_risk = imp["high_risk_case_count"]
            patterns = imp["recurring_pattern_count"]
            merchants = imp["merchants_impacted"]
            seeded = imp["seeded_case_count"]
            live_injected = imp["live_injected_case_count"]
            live_exp_str = self._format_minor_units(imp.get("live_injected_exposure_identified", 0))

            q_asks_savings = any(w in question.lower() for w in ["saved", "save", "savings", "recovered", "recovery"])

            lines = []
            if q_asks_savings:
                lines.append(
                    f"Sentinel identified **{total_exp_str}** in financial exposure for review across **{actionable} actionable cases**. "
                    "The current dataset does not contain evidence of realized cash recovery, so this should not be interpreted as money saved."
                )
            else:
                lines.append(
                    f"Sentinel has identified a total of **{total_exp_str}** in potential financial exposure requiring review across **{actionable} actionable cases**."
                )

            lines.append(
                f"- **High-Risk Cases**: {high_risk} (severe financial/reconciliation anomalies)\n"
                f"- **Recurring Patterns Identified**: {patterns} systemic clusters\n"
                f"- **Merchants Impacted**: {merchants} distinct merchants\n"
                f"- **Case Provenance**: {seeded} baseline seeded, {live_injected} synthetic live-injected ({live_exp_str} live exposure)"
            )

            lines.append(
                f"*Note: Value is classified as {imp['value_type']} (exposure surfaced for governance and human/policy intervention; not equivalent to recovered savings).*"
            )

            answer = "\n\n".join(lines)
            reasoning = "Direct deterministic business impact calculation compiled from persisted exceptions, transactions, and pattern clusters."
            return answer, reasoning, "HIGH", None

        elif "drift_prediction" in data:
            drift = data["drift_prediction"]
            direction = drift.get("direction", "STABLE")
            score = drift.get("drift_score", 0)
            band = drift.get("risk_band", "STABLE")
            conf = drift.get("confidence", "MEDIUM")
            signals = drift.get("signals", [])
            account_id = drift.get("nodal_account_id", "nodal_escrow_main")

            if direction == "INSUFFICIENT_DATA":
                answer = (
                    "Sentinel does not currently have enough historical temporal evidence to make a reliable operational drift prediction. "
                    "A valid predictive drift evaluation requires multiple temporal observation windows."
                )
                reasoning = "Insufficient temporal observations in database."
                return answer, reasoning, "LOW", "Insufficient historical baseline data."

            lines = [
                f"Predictive Nodal Drift Radar indicates **{direction}** operational health for account **{account_id}** "
                f"with a deterministic Drift Score of **{score}/100** ({band} risk band, Confidence: **{conf}**)."
            ]

            active_signals = [s for s in signals if s.get("contribution", 0) > 0]
            if active_signals:
                lines.append("\n**Leading Early-Warning Signals**:")
                for s in active_signals:
                    lines.append(f"- **{s['name']}** (+{s['contribution']} pts): {s['explanation']}")
            else:
                lines.append("\nNo deteriorating operational signals detected; metrics remain stable across observation windows.")

            source = drift.get("source", {})
            if source.get("synthetic_included"):
                lines.append(f"\n*Note: Prediction incorporates {source.get('live_injected_count')} synthetic live-injected observations.*")

            lines.append(
                "\n*Disclaimer: This is an analytical early-warning indicator based on leading trend signals, "
                "not a guarantee that a failure will occur or an automated policy mutation.*"
            )

            answer = "\n".join(lines)
            reasoning = f"Deterministic temporal window drift analysis compiled for {account_id}."
            return answer, reasoning, conf, None

        elif "confidence_calibration" in data:
            calib = data["confidence_calibration"]
            status = calib.get("status", "INSUFFICIENT_DATA")
            tot = calib.get("total_predictions", 0)
            eval_cnt = calib.get("evaluated_predictions", 0)
            cov = calib.get("coverage")
            cr = calib.get("correctness_rate")
            buckets = calib.get("confidence_buckets", {})
            reasons = calib.get("insufficiency_reasons", [])

            if status in ("INSUFFICIENT_DATA", "NOT_CALIBRATABLE"):
                reason_txt = "; ".join(reasons) if reasons else "insufficient evaluated historical outcomes."
                answer = (
                    f"Sentinel's confidence calibration is currently **{status}** ({reason_txt}). "
                    "There are not enough evaluated outcomes to make a statistically verified calibration assertion.\n\n"
                    "*Note: Sentinel confidence labels represent model certainty at prediction time, not mathematical failure probabilities.*"
                )
                reasoning = "Insufficient evaluated outcomes available in database."
                return answer, reasoning, "LOW", "Insufficient historical evaluated outcomes."

            cov_str = f"{cov * 100:.1f}%" if cov is not None else "N/A"
            cr_str = f"{cr * 100:.1f}%" if cr is not None else "N/A"

            lines = [
                f"Sentinel's empirical confidence calibration status is **{status}** with **{cov_str}** evaluation coverage "
                f"({eval_cnt} evaluated out of {tot} predictions) and an overall observed correctness rate of **{cr_str}**.\n",
                "**Empirical Correctness by Confidence Level**:"
            ]

            for lvl in ["HIGH", "MEDIUM", "LOW"]:
                b = buckets.get(lvl, {})
                p_cnt = b.get("prediction_count", 0)
                e_cnt = b.get("evaluated_count", 0)
                c_cnt = b.get("correct_count", 0)
                rate = b.get("correctness_rate")
                rate_str = f"{rate * 100:.1f}%" if rate is not None else "N/A (no evaluations)"
                lines.append(f"- **{lvl} Confidence**: {e_cnt} evaluated, {c_cnt} correct ({rate_str}) [out of {p_cnt} predictions]")

            num = calib.get("numerical_metrics", {})
            if num.get("status") == "CALCULATED":
                lines.append(f"\n**Numerical Calibration**: Brier Score: **{num.get('brier_score')}**, ECE: **{num.get('ece')}**.")

            lines.append(
                "\n*Note: Sentinel confidence labels represent model certainty at prediction time, "
                "not mathematical failure probabilities. Displayed rates reflect observed historical outcomes.*"
            )

            answer = "\n".join(lines)
            reasoning = "Deterministic confidence calibration compiled from persisted evaluation records and investigation runs."
            return answer, reasoning, "HIGH", None

        elif "escalation_status" in data:
            esc = data["escalation_status"]
            cfg = esc.get("configuration", {})
            dels = esc.get("recent_deliveries", [])
            specific = esc.get("specific_delivery")

            status_str = "ENABLED" if cfg.get("enabled") and cfg.get("configured") else ("DISABLED" if not cfg.get("enabled") else "UNCONFIGURED")
            target_str = cfg.get("destination_url", "NOT CONFIGURED")
            auth_str = cfg.get("authentication_method", "HMAC-SHA256")

            lines = [
                f"Escalation Webhook Dispatcher is currently **{status_str}** (Destination: `{target_str}`, Security: `{auth_str}`)."
            ]

            if specific:
                lines.append(
                    f"\n**Delivery status for {specific['exception_id']}**: "
                    f"Status: **{specific['delivery_status']}**, Event ID: `{specific['event_id']}`, Attempts: {specific['attempt_count']}."
                )
            elif dels:
                lines.append(f"\n**Recent Outbound Escalations** ({len(dels)} logged):")
                for d in dels[:3]:
                    lines.append(f"- Event `{d['event_id']}` ({d['exception_id']}): **{d['delivery_status']}** (Attempts: {d['attempt_count']})")
            else:
                lines.append("\nNo outbound escalation webhook dispatches have been recorded yet.")

            lines.append(
                "\n*Safety Guarantee: Outbound escalation webhooks are strictly decoupled from Sentinel's policy engine. Webhook delivery failure never modifies policy decisions.*"
            )

            answer = "\n".join(lines)
            reasoning = "Deterministic escalation webhook configuration and delivery state compiled from operational database."
            return answer, reasoning, "HIGH", None

        elif "aggregate" in data:
            agg = data["aggregate"]
            open_count = agg.get("open_exceptions_count", 0)
            open_exp_str = self._format_minor_units(agg.get("open_exposure_minor_units", 0))
            tot = agg.get("total_exceptions", 0)

            answer = (
                f"There are currently **{open_count}** unresolved open exceptions in the system "
                f"with total open exposure of **{open_exp_str}** (out of {tot} total lifetime exceptions)."
            )

            breakdown = agg.get("family_breakdown", [])
            if breakdown:
                b_lines = [f"- **{b['family']}**: {b['open_count']} open ({self._format_minor_units(b['exposure_minor_units'])})" for b in breakdown]
                answer += "\n\n**Breakdown by Exception Family**:\n" + "\n".join(b_lines)

            reasoning = "Deterministic aggregation of active unresolved exceptions and cumulative exposure."
            return answer, reasoning, "HIGH", None

        elif "merchant_discrepancies" in data:
            md = data["merchant_discrepancies"]
            merchants = md.get("merchants", [])
            total = md.get("total_merchants_with_anomalies", 0)

            if not merchants:
                answer = "Currently, no merchants have anomalous settlement discrepancies. All active merchants are within normal operating thresholds."
                reasoning = "Queried operational merchant trust scores; 0 anomalous merchants found."
                return answer, reasoning, "HIGH", None

            lines = [
                f"Currently, **{total} merchant(s)** have active settlement discrepancies or elevated risk profiles:\n"
            ]
            for i, m in enumerate(merchants[:5], 1):
                m_id = m["merchant_id"]
                band = m["score_band"]
                exc_cnt = m["metrics"]["exception_count"]
                exp = self._format_minor_units(m["metrics"]["total_exposure"])
                trust = m["trust_score"]
                lines.append(
                    f"**{i}. Merchant `{m_id}`** (Band: **{band}** | Trust Score: {trust}/100)\n"
                    f"- **Exceptions**: {exc_cnt} | **Total Exposure**: {exp}"
                )
                if m.get("factors"):
                    top_factors = [f["explanation"] for f in m["factors"] if f.get("direction") == "NEGATIVE"][:2]
                    if top_factors:
                        lines.append(f"- **Key Drivers**: {'; '.join(top_factors)}")
                lines.append("")

            answer = "\n".join(lines)
            reasoning = f"Compiled deterministic discrepancy metrics from {total} merchant trust score profiles."
            return answer, reasoning, "HIGH", None

        elif "search_exceptions" in data:
            se = data["search_exceptions"]
            excs = se.get("exceptions", [])
            cnt = se.get("count", 0)
            fam = data.get("searched_family", "requested")
            if not excs:
                answer = f"No active exceptions were found for family **{fam}** in the operational repository."
                reasoning = f"Exception repository search returned 0 matching records for {fam}."
                return answer, reasoning, "HIGH", None

            lines = [f"Found **{cnt} active exception(s)** for family **{fam}**:\n"]
            for i, e in enumerate(excs[:5], 1):
                exp = self._format_minor_units(e.get("exposure_minor_units", 0))
                lines.append(
                    f"**{i}. {e['exception_id']}**\n"
                    f"- **Type**: {e['type']} | **State**: {e['state']} | **Severity**: {e['severity']}\n"
                    f"- **Exposure**: {exp} | **Primary Payment**: `{e.get('primary_payment_id') or 'N/A'}`"
                )
                lines.append("")
            answer = "\n".join(lines)
            reasoning = f"Direct query results from operational exception repository for {fam}."
            return answer, reasoning, "HIGH", None

        elif "clusters" in data:
            clusters = data["clusters"]
            if not clusters:
                return (
                    "No recurring exception patterns currently meet the minimum cluster threshold.",
                    "Pattern Miner discovered 0 multi-case clusters.",
                    "HIGH",
                    None,
                )

            total_cases = sum(c.get("exception_count", 0) for c in clusters)
            total_exp = sum(c.get("total_exposure", 0) for c in clusters)
            exp_str = self._format_minor_units(total_exp)

            answer_lines = [
                f"Pattern Miner has identified **{len(clusters)} recurring exception pattern(s)** "
                f"representing **{total_cases} total cases** and **{exp_str}** in cumulative exposure.\n"
            ]

            for i, cl in enumerate(clusters[:4], 1):
                c_label = cl.get("pattern_label", "Pattern")
                c_count = cl.get("exception_count", 0)
                c_exp = self._format_minor_units(cl.get("total_exposure", 0))
                c_desc = cl.get("description", "")
                c_members = ", ".join(cl.get("exception_ids", [])[:3])
                if len(cl.get("exception_ids", [])) > 3:
                    c_members += f" (+{len(cl.get('exception_ids', [])) - 3} more)"

                answer_lines.append(
                    f"**{i}. {c_label}** ({cl.get('cluster_id')})\n"
                    f"- **Cases**: {c_count} | **Exposure**: {c_exp}\n"
                    f"- **Signature**: {c_desc}\n"
                    f"- **Members**: `{c_members}`"
                )

            answer = "\n\n".join(answer_lines)
            reasoning = f"Direct cluster synthesis from {len(clusters)} deterministic Pattern Miner clusters."
            confidence = "HIGH"
            limitations = None
            return answer, reasoning, confidence, limitations

        return (

            "Operational evidence retrieved, but insufficient to formulate a direct answer.",
            "Ambiguous query results.",
            "MEDIUM",
            "Details missing.",
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
    ) -> Dict[str, Any]:
        """Persists copilot query audit record to database and logs COPILOT_QUERY_EXECUTED audit event."""
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
        }
