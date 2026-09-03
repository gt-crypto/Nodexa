"""Ask Sentinel copilot service handling question parsing, read-only evidence retrieval, grounded answer generation, and query audit logging."""
import json
import re
import uuid
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.models.copilot import CopilotQuery
from backend.models.audit import AuditEvent
from backend.copilot.tools import AskSentinelToolRegistry


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
        exceptions = re.findall(r"EXC-[A-Z0-9_-]+", text, re.IGNORECASE)
        payments = re.findall(r"PAY-[A-Z0-9_-]+", text, re.IGNORECASE)
        settlements = re.findall(r"SET-[A-Z0-9_-]+", text, re.IGNORECASE)
        orders = re.findall(r"ORD-[A-Z0-9_-]+", text, re.IGNORECASE)
        
        # Look for "merchant <ID>" or "merchant M123"
        merchants = []
        merch_matches = re.findall(r"merchant\s+([A-Za-z0-9_-]+)", text, re.IGNORECASE)
        merchants.extend(merch_matches)
        
        return (
            [e.upper() for e in set(exceptions)],
            [p.upper() for p in set(payments)],
            [s.upper() for s in set(settlements)],
            [o.upper() for o in set(orders)],
            [m.strip() for m in set(merchants)],
        )

    def _format_minor_units(self, paise: int) -> str:
        """Formats integer minor unit paise into readable Rupee representation."""
        rupees = paise / 100.0
        return f"₹{rupees:,.2f} ({paise} paise)"

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
                        "I can only retrieve and explain live Nodal Sentinel operational facts."
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

        # Exception investigation question
        if exc_ids:
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

        # Payment lookup question
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

        # Merchant Trust Score questions
        elif merch_ids:
            target_merch_id = merch_ids[0]
            m_res = self.tool_registry.execute_tool("get_merchant_trust_score", session=session, merchant_id=target_merch_id)
            tools_used.append("get_merchant_trust_score")
            if m_res.get("status") == "success" and m_res.get("data", {}).get("found"):
                m_data = m_res["data"]["score"]
                retrieved_data["merchant_score"] = m_data
                evidence_refs.append(f"MERCHANT_SCORE_{target_merch_id}")

        # Business Impact & ROI questions
        elif any(k in q_lower for k in [
            "roi",
            "business impact",
            "money saved",
            "saved",
            "how much money",
            "save",
            "recovered",
            "recovery",
            "financial exposure has sentinel",
            "exposure has sentinel identified",
            "exposure is associated with live-injected",
            "how much financial exposure",
            "actionable cases has sentinel",
            "what business impact",
        ]):
            imp_res = self.tool_registry.execute_tool("get_business_impact", session=session)
            tools_used.append("get_business_impact")
            if imp_res.get("status") == "success" and imp_res.get("data", {}).get("found"):
                retrieved_data["business_impact"] = imp_res["data"]["impact"]
                evidence_refs.append("BUSINESS_IMPACT_ROI")

        # Predictive Nodal Drift Radar questions
        elif any(k in q_lower for k in [
            "drift",
            "deteriorating",
            "early warning",
            "drift risk",
            "nodal health deteriorating",
            "predictive",
            "radar",
            "leading indicator",
            "leading signal",
            "drift score",
        ]):
            drift_res = self.tool_registry.execute_tool("get_drift_prediction", session=session)
            tools_used.append("get_drift_prediction")
            if drift_res.get("status") == "success" and drift_res.get("data", {}).get("found"):
                retrieved_data["drift_prediction"] = drift_res["data"]["drift"]
                evidence_refs.append(drift_res["data"]["drift"]["prediction_id"])

        # Confidence Calibration / Reliability questions
        elif any(k in q_lower for k in [
            "calibration",
            "calibrated",
            "confidence reliable",
            "how reliable is confidence",
            "historical correctness",
            "confidence calibration",
            "brier",
            "ece",
        ]):
            calib_res = self.tool_registry.execute_tool("get_confidence_calibration", session=session)
            tools_used.append("get_confidence_calibration")
            if calib_res.get("status") == "success" and calib_res.get("data", {}).get("found"):
                retrieved_data["confidence_calibration"] = calib_res["data"]["calibration"]
                evidence_refs.append(calib_res["data"]["calibration"]["snapshot_id"])

        # Escalation Webhook questions
        elif any(k in q_lower for k in [
            "webhook",
            "escalation webhook",
            "escalate webhook",
            "downstream alert",
            "escalation status",
            "did we escalate",
            "escalations delivered",
        ]):
            exc_id_param = exc_ids[0] if exc_ids else None
            esc_res = self.tool_registry.execute_tool("get_escalation_status", session=session, exception_id=exc_id_param)
            tools_used.append("get_escalation_status")
            if esc_res.get("status") == "success":
                retrieved_data["escalation_status"] = esc_res.get("data", {})

        # Pattern Miner / Recurring cluster questions
        elif any(k in q_lower for k in ["pattern", "cluster", "recurring", "repeated", "clustering", "largest pattern"]):
            cl_res = self.tool_registry.execute_tool("get_clusters", session=session)
            tools_used.append("get_clusters")
            if cl_res.get("status") == "success":
                retrieved_data["clusters"] = cl_res.get("data", {}).get("clusters", [])
                for cl in retrieved_data["clusters"]:
                    evidence_refs.append(cl["cluster_id"])
                    for exc_id in cl.get("exception_ids", [])[:2]:
                        evidence_refs.append(exc_id)

        # Aggregate / Overview questions
        elif any(k in q_lower for k in ["exposure", "how much", "summary", "overview", "total", "open exceptions", "unresolved", "families"]):
            agg_res = self.tool_registry.execute_tool("get_aggregate_summary", session=session)
            tools_used.append("get_aggregate_summary")
            if agg_res.get("status") == "success":
                retrieved_data["aggregate"] = agg_res["data"]


        # 3. Formulate Answer & Check Abstention
        if not retrieved_data:
            return self._persist_and_respond(
                session=session,
                query_id=query_id,
                question=question,
                answer=(
                    "I cannot establish an answer from available Nodal Sentinel operational records. "
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
        if "exception" in data:
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
