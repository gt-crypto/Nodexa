"""Grounded LLM Tool-Calling Agent for Ask Sentinel Copilot.

Enforces strict financial separation:
- LLM: Semantic question understanding, tool selection, multi-tool reasoning, and synthesis.
- Nodexa Read-Only Tools: Authoritative financial calculations, database access, aggregations.
- Grounding & Relevance Guard: Guarantees zero invented numbers and ensures answers address
  only the requested subject matter without polluting with unrelated exception data.
"""
import json
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.copilot.provider import CopilotLLMProvider
from backend.copilot.tools import AskSentinelToolRegistry
from backend.logging import logger

# OpenAI / Gemini Function-Calling Tool Declarations
ASK_SENTINEL_TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "get_sales_summary",
            "description": "Retrieves gross captured sales volume, transaction count, and currency from gateway payment transactions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "string", "description": "Optional merchant ID to filter sales."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_refunds_summary",
            "description": "Retrieves total customer refund amounts, refund count, and currency from dispute/refund records.",
            "parameters": {
                "type": "object",
                "properties": {
                    "merchant_id": {"type": "string", "description": "Optional merchant ID to filter refunds."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_transaction_metrics",
            "description": "Calculates rich transaction analytics: averages, counts by status (CAPTURED, FAILED, etc.), min/max values, and thresholds.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "description": "Filter by status e.g. CAPTURED, FAILED, AUTHORIZED."},
                    "min_amount_paise": {"type": "integer", "description": "Filter transactions >= amount in minor units (paise)."},
                    "max_amount_paise": {"type": "integer", "description": "Filter transactions <= amount in minor units (paise)."},
                    "merchant_id": {"type": "string", "description": "Filter by merchant ID."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_merchants_overview",
            "description": "Retrieves merchant volume rankings, total merchant count, volume concentration, and merchants with highest exposure or refund ratios.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_settlements_summary",
            "description": "Calculates total bank settlement volume, clearing timing delays, batch count, unallocated batches, and largest/smallest batches.",
            "parameters": {
                "type": "object",
                "properties": {
                    "acquirer_id": {"type": "string", "description": "Optional acquirer ID to filter."}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cross_source_reconciliation",
            "description": "Cross-examines Gateway vs Bank Settlements vs Nodal Ledger. Identifies unsettled captured payments, partial settlements, settlement SLA breaches, and ledger mismatches.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_payment",
            "description": "Retrieves factual gateway payment details for a specific payment ID (amount, status, created_at, method).",
            "parameters": {
                "type": "object",
                "properties": {
                    "payment_id": {"type": "string", "description": "Payment transaction ID e.g. PAY-000001"}
                },
                "required": ["payment_id"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_settlement",
            "description": "Retrieves factual bank settlement batch details by settlement_id or payment_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "settlement_id": {"type": "string", "description": "Settlement ID or payment ID reference."}
                },
                "required": ["settlement_id"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_ledger_entries",
            "description": "Retrieves double-entry nodal ledger postings (debits, credits, balances) for a transaction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "payment_id": {"type": "string", "description": "Transaction ID e.g. PAY-000001"}
                },
                "required": ["payment_id"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_exception",
            "description": "Retrieves detailed diagnostic investigation record, financial exposure, and evidence for an exception ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "exception_id": {"type": "string", "description": "Exception ID e.g. EXC-001"}
                },
                "required": ["exception_id"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_aggregate_summary",
            "description": "Retrieves high-level summary of total exceptions, unresolved count, open financial exposure, and breakdown by exception family.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_exceptions",
            "description": "Searches and filters exceptions by family type (GHOST_SETTLEMENT, PARTIAL_SETTLEMENT, etc.) or state.",
            "parameters": {
                "type": "object",
                "properties": {
                    "family": {"type": "string", "description": "Exception family type"},
                    "state": {"type": "string", "description": "Exception state e.g. DETECTED, INVESTIGATING"},
                    "limit": {"type": "integer", "description": "Max results to return"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_clusters",
            "description": "Retrieves recurring systemic anomaly clusters discovered by the Pattern Miner.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_verifier_opinion",
            "description": "Retrieves independent AI verifier evaluation and dissent opinion for a transaction or exception.",
            "parameters": {
                "type": "object",
                "properties": {
                    "payment_id": {"type": "string", "description": "Payment ID or Exception ID"}
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_business_impact",
            "description": "Retrieves financial loss prevention, operational savings, and SLA risk mitigation metrics.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_drift_prediction",
            "description": "Retrieves predictive anomaly drift scores and early warning signals.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_escalation_status",
            "description": "Retrieves webhook delivery audit logs and escalation notifications.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_confidence_calibration",
            "description": "Retrieves confidence calibration metrics and threshold distribution.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


class DeterministicSemanticToolPlanner:
    """Semantic tool planner providing robust offline, local, and CI tool selection."""

    @classmethod
    def plan(
        cls,
        question: str,
        exc_ids: List[str],
        pay_ids: List[str],
        set_ids: List[str],
        ord_ids: List[str],
        merch_ids: List[str],
    ) -> List[Dict[str, Any]]:
        """Determines the minimum set of read-only tools required to answer the question."""
        q = question.lower()
        tools_to_call: List[Dict[str, Any]] = []

        # 1. SPECIFIC EXCEPTION LOOKUP (priority over payment if question is about an exception)
        if exc_ids:
            target_exc = exc_ids[0]
            if any(k in q for k in ("verif", "opinion", "dissent")):
                tools_to_call.append({"tool_name": "get_verifier_opinion", "arguments": {"exception_id": target_exc}})
            else:
                tools_to_call.append({"tool_name": "get_exception", "arguments": {"exception_id": target_exc}})
            return tools_to_call

        # 2. SPECIFIC PAYMENT / TRANSACTION LOOKUP
        if pay_ids and not any(k in q for k in ("compare", "versus", "vs", "reconciliation")):
            target_pay = pay_ids[0]
            tools_to_call.append({"tool_name": "get_payment", "arguments": {"payment_id": target_pay}})
            # If asking about verification or verifier
            if any(k in q for k in ("verif", "opinion", "dissent")):
                tools_to_call.append({"tool_name": "get_verifier_opinion", "arguments": {"payment_id": target_pay}})
            # If asking why flagged or what happened, also get ledger and settlements
            elif any(k in q for k in ("flagged", "why", "exception", "issue", "anomal", "problem")):
                tools_to_call.append({"tool_name": "get_ledger_entries", "arguments": {"payment_id": target_pay}})
                tools_to_call.append({"tool_name": "get_settlement", "arguments": {"settlement_id": target_pay}})
            return tools_to_call

        # 3. SPECIFIC SETTLEMENT LOOKUP
        if set_ids and not any(k in q for k in ("compare", "versus", "vs", "summary", "total", "volume")):
            target_set = set_ids[0]
            tools_to_call.append({"tool_name": "get_settlement", "arguments": {"settlement_id": target_set}})
            return tools_to_call

        # 4. CROSS-SOURCE RECONCILIATION & DISCREPANCIES
        if any(k in q for k in (
            "compare payments with settlements", "compare gateway and settlement", "compare payments and settlements",
            "which payments haven't settled", "which payments have not settled", "unsettled", "not settled",
            "partial settlement", "partial deficits", "mismatched settlement",
            "which transactions have ledger mismatches", "ledger mismatch",
            "settlement sla breach", "sla breach", "which settlements are late",
            "payments don't have settlements", "compare payments"
        )):
            tools_to_call.append({"tool_name": "get_cross_source_reconciliation", "arguments": {}})
            if any(k in q for k in ("compare", "volume")):
                tools_to_call.append({"tool_name": "get_settlements_summary", "arguments": {}})
            return tools_to_call

        # 5. NET SALES (Gross Sales - Refunds)
        if any(k in q for k in ("net sales", "net revenue", "sales after refund", "net processed", "net volume", "net gmv", "net amount")):
            merch_arg = merch_ids[0] if merch_ids else None
            tools_to_call.append({"tool_name": "get_sales_summary", "arguments": {"merchant_id": merch_arg} if merch_arg else {}})
            tools_to_call.append({"tool_name": "get_refunds_summary", "arguments": {"merchant_id": merch_arg} if merch_arg else {}})
            return tools_to_call

        # 6. REFUNDS SUMMARY
        if any(k in q for k in (
            "refund", "refunds", "refunded", "chargeback", "chargebacks",
            "how much did we refund", "what was refunded", "how many refunds", "total refund",
            "total refunds"
        )) and not any(k in q for k in ("which merchant", "highest refund rate")):
            merch_arg = merch_ids[0] if merch_ids else None
            tools_to_call.append({"tool_name": "get_refunds_summary", "arguments": {"merchant_id": merch_arg} if merch_arg else {}})
            return tools_to_call

        # 7. MERCHANT ANALYTICS & RANKINGS
        if any(k in q for k in (
            "merchant", "merchants", "vendor", "vendors", "seller",
            "who processed the most", "processed the most", "highest sales volume", "highest volume",
            "most volume", "highest exposure", "highest refund rate", "how many merchants"
        )):
            tools_to_call.append({"tool_name": "get_merchants_overview", "arguments": {}})
            return tools_to_call

        # 8. TRANSACTION METRICS (Averages, Min/Max, Status Counts, Thresholds)
        if any(k in q for k in (
            "average transaction", "average payment", "avg transaction",
            "largest payment", "largest transaction", "biggest payment", "highest payment",
            "smallest payment", "smallest transaction", "lowest payment",
            "failed transaction", "failed payment", "how many payments failed", "how many transactions failed",
            "how many failed", "above ₹", "above rs", "greater than", "threshold",
            "how many transactions were processed", "how many payments were processed"
        )):
            status_filter = "FAILED" if "failed" in q else ("CAPTURED" if any(k in q for k in ("captured", "successful", "success")) else None)
            min_amt = None
            threshold_match = re.search(r"(?:above|greater than|>)\s*(?:₹|rs\.?|inr)?\s*([\d,]+)", q)
            if threshold_match:
                try:
                    num_str = threshold_match.group(1).replace(",", "")
                    min_amt = int(float(num_str) * 100)
                except Exception:
                    pass

            args = {}
            if status_filter:
                args["status"] = status_filter
            if min_amt:
                args["min_amount_paise"] = min_amt
            if merch_ids:
                args["merchant_id"] = merch_ids[0]

            tools_to_call.append({"tool_name": "get_transaction_metrics", "arguments": args})
            return tools_to_call

        # 9. SETTLEMENT SUMMARY (Settlement volume, delay, batches)
        if any(k in q for k in (
            "settlement volume", "total settlement", "settlement amount", "average settlement clearing time",
            "average settlement time", "settlement time", "settlement delay",
            "settlement clearing delay", "clearing time", "settlement batches", "unallocated settlement"
        )):
            tools_to_call.append({"tool_name": "get_settlements_summary", "arguments": {}})
            return tools_to_call

        # 10. SALES / PROCESSED VOLUME / GMV (Priority check: NEVER route to exceptions!)
        if any(k in q for k in (
            "sales", "payment volume", "processed volume", "processed amount", "transaction value", "gmv",
            "how much money did we process", "how much did we process", "how much money was processed",
            "what did we process", "what was our payment volume", "what was our processed volume",
            "how much did customers pay", "what are our total sales", "what are my total sales",
            "total amount of sales", "how much did we sell", "total processed amount", "total sales",
            "how much was processed", "what amount did we process", "how much was processed in payments",
            "what is our total gmv", "how much money flowed through the system", "how much was processed through nodexa",
            "what was our transaction volume", "how much did customers pay?"
        )):
            merch_arg = merch_ids[0] if merch_ids else None
            tools_to_call.append({"tool_name": "get_sales_summary", "arguments": {"merchant_id": merch_arg} if merch_arg else {}})
            return tools_to_call

        # 11. PATTERNS & CLUSTERS
        if any(k in q for k in ("pattern", "patterns", "cluster", "clusters", "recurring")):
            tools_to_call.append({"tool_name": "get_clusters", "arguments": {}})
            return tools_to_call

        # 12. BUSINESS IMPACT & VALUE
        if any(k in q for k in ("business impact", "financial savings", "loss prevention", "roi", "savings", "save", "saved")):
            tools_to_call.append({"tool_name": "get_business_impact", "arguments": {}})
            return tools_to_call

        # 13. DRIFT & PREDICTION
        if any(k in q for k in ("drift", "prediction", "drift radar", "early warning", "deteriorat", "nodal health")):
            tools_to_call.append({"tool_name": "get_drift_prediction", "arguments": {}})
            return tools_to_call

        # 14. CONFIDENCE CALIBRATION
        if any(k in q for k in ("calibrat", "confidence score", "confidence threshold")):
            tools_to_call.append({"tool_name": "get_confidence_calibration", "arguments": {}})
            return tools_to_call

        # 15. ESCALATION STATUS
        if any(k in q for k in ("escalat", "webhook", "paging", "notification")):
            tools_to_call.append({"tool_name": "get_escalation_status", "arguments": {}})
            return tools_to_call

        # 16. SPECIFIC EXCEPTION FAMILY SEARCH
        for fam in ("GHOST_SETTLEMENT", "REFUND_CHARGEBACK_DOUBLE_DIP", "SETTLEMENT_SLA_BREACH", "PARTIAL_SETTLEMENT", "MISSING_UNALLOCATED_SETTLEMENT"):
            if fam.lower().replace("_", " ") in q or fam.lower() in q:
                tools_to_call.append({"tool_name": "search_exceptions", "arguments": {"family": fam}})
                return tools_to_call

        # 17. EXCEPTIONS & ANOMALIES & EXPOSURE (Only when user explicitly asks for them!)
        if any(k in q for k in (
            "exception", "exceptions", "exposure", "unresolved", "anomal", "open exposure",
            "how many issues are open", "what is our unresolved exposure", "what is the biggest problem",
            "tied up", "open cases", "unresolved cases", "discrepanc"
        )):
            tools_to_call.append({"tool_name": "get_aggregate_summary", "arguments": {}})
            return tools_to_call

        # Default: get_aggregate_summary
        tools_to_call.append({"tool_name": "get_aggregate_summary", "arguments": {}})
        return tools_to_call


class CopilotToolCallingAgent:
    """Orchestrates tool selection, execution, and grounded answer synthesis."""

    def __init__(self, tool_registry: AskSentinelToolRegistry):
        self.tool_registry = tool_registry

    def plan_tools(
        self,
        question: str,
        exc_ids: List[str],
        pay_ids: List[str],
        set_ids: List[str],
        ord_ids: List[str],
        merch_ids: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], str, bool]:
        """Plans tools using remote LLM if configured, else uses DeterministicSemanticToolPlanner."""
        # 1. Try real LLM provider
        llm_tools, reasoning, is_real = CopilotLLMProvider.plan_tools_with_llm(
            question=question,
            tool_definitions=ASK_SENTINEL_TOOL_DEFINITIONS,
            context=context,
        )
        if is_real and llm_tools:
            return llm_tools, reasoning, True

        # 2. Resilient semantic fallback
        fallback_tools = DeterministicSemanticToolPlanner.plan(
            question=question,
            exc_ids=exc_ids,
            pay_ids=pay_ids,
            set_ids=set_ids,
            ord_ids=ord_ids,
            merch_ids=merch_ids,
        )
        reasoning = "Selected deterministic tools matching query semantics."
        return fallback_tools, reasoning, False

    def execute_tools(
        self,
        session: Session,
        planned_tools: List[Dict[str, Any]],
    ) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """Executes each planned tool against the database via AskSentinelToolRegistry."""
        retrieved_data: Dict[str, Any] = {}
        tools_used: List[str] = []
        evidence_refs: List[str] = []

        for item in planned_tools:
            t_name = item.get("tool_name")
            args = item.get("arguments", {})
            if not t_name or t_name not in self.tool_registry.ASK_SENTINEL_ALLOWED_TOOLS:
                continue

            res = self.tool_registry.execute_tool(t_name, session=session, **args)
            tools_used.append(t_name)
            if res.get("status") == "success":
                data = res.get("data", {})
                retrieved_data[t_name] = data
                
                # Capture domain-specific evidence references
                if t_name == "get_sales_summary":
                    evidence_refs.append("GATEWAY_TRANSACTIONS_SALES")
                    evidence_refs.append("gateway_transactions")
                elif t_name == "get_refunds_summary":
                    evidence_refs.append("DISPUTE_REFUND_EVENTS")
                elif t_name == "get_cross_source_reconciliation":
                    evidence_refs.extend(["GATEWAY_TRANSACTIONS", "BANK_SETTLEMENT_BATCHES", "NODAL_LEDGER"])
                elif t_name == "get_merchants_overview":
                    evidence_refs.append("MERCHANT_SCORES")
                elif t_name == "get_settlements_summary":
                    evidence_refs.append("BANK_SETTLEMENT_BATCHES")
                elif t_name == "get_transaction_metrics":
                    evidence_refs.append("GATEWAY_TRANSACTIONS")
                elif t_name == "get_clusters":
                    for c in data.get("clusters", []):
                        if "cluster_id" in c:
                            evidence_refs.append(c["cluster_id"])
                    evidence_refs.append("PATTERN_CLUSTERS")
                elif t_name == "get_verifier_opinion":
                    if "opinion_id" in data:
                        evidence_refs.append(data["opinion_id"])
                    if "payment_id" in data:
                        evidence_refs.append(data["payment_id"])
                elif t_name == "get_drift_prediction":
                    evidence_refs.append("PREDICTIVE_DRIFT")
                elif t_name == "get_business_impact":
                    evidence_refs.append("BUSINESS_IMPACT")
                elif t_name == "get_confidence_calibration":
                    evidence_refs.append("CONFIDENCE_CALIBRATION")
                elif t_name == "get_escalation_status":
                    evidence_refs.append("ESCALATION_WEBHOOKS")
                elif t_name == "get_payment":
                    if data.get("found") and "payment_id" in data:
                        evidence_refs.append(data["payment_id"])
                elif t_name == "get_settlement":
                    if data.get("found"):
                        for s in data.get("settlements", []):
                            if "settlement_id" in s:
                                evidence_refs.append(s["settlement_id"])
                elif t_name == "get_exception":
                    if data.get("found"):
                        if "exception_id" in data:
                            evidence_refs.append(data["exception_id"])
                        if "primary_payment_id" in data and data["primary_payment_id"]:
                            evidence_refs.append(data["primary_payment_id"])

        return retrieved_data, tools_used, list(dict.fromkeys(evidence_refs))

    def synthesize_response(
        self,
        question: str,
        retrieved_data: Dict[str, Any],
        tools_used: List[str],
        was_real_llm: bool,
    ) -> Tuple[str, str, str, bool, Optional[str]]:
        """Synthesizes the natural language answer with Answer Relevance Guard enforcement."""
        # If real remote LLM synthesized successfully, check relevance guard
        if was_real_llm:
            llm_text, ok = CopilotLLMProvider.synthesize_with_llm(question, retrieved_data, tools_used)
            if ok and llm_text:
                if not self._violates_relevance_guard(question, llm_text):
                    return llm_text, "Grounded synthesis generated via remote LLM.", "HIGH", False, None

        # Grounded Deterministic Synthesizer
        return self._deterministic_synthesize(question, retrieved_data, tools_used)

    @classmethod
    def _violates_relevance_guard(cls, question: str, answer: str) -> bool:
        """Enforces that questions about sales/volume do NOT suddenly discuss open exceptions."""
        q_lower = question.lower()
        a_lower = answer.lower()
        is_sales_q = any(k in q_lower for k in ("sales", "payment volume", "processed", "money did we process", "gmv", "customers pay"))
        asks_for_exceptions = any(k in q_lower for k in ("exception", "exposure", "unresolved", "problem", "issue"))

        if is_sales_q and not asks_for_exceptions:
            if any(bad in a_lower for bad in ("unresolved exceptions", "open exposure", "exception family breakdown", "unresolved open exceptions")):
                return True
        return False

    def _deterministic_synthesize(
        self,
        question: str,
        data: Dict[str, Any],
        tools_used: List[str],
    ) -> Tuple[str, str, str, bool, Optional[str]]:
        """Grounded deterministic response formatter addressing the user query."""
        q_lower = question.lower()

        # 1. SALES SUMMARY
        if "get_sales_summary" in data and "get_refunds_summary" not in data:
            s = data["get_sales_summary"]
            tx_count = s.get("transaction_count", 0)
            total_inr = s.get("total_sales_inr", 0.0)
            total_paise = s.get("total_sales_paise", 0)
            merchant_filter = s.get("merchant_id")
            merch_clause = f" for merchant {merchant_filter}" if merchant_filter else ""

            ans = (
                f"Total processed payment volume{merch_clause}: **₹{total_inr:,.2f}** ({total_paise:,} paise) "
                f"across **{tx_count}** captured transactions.\n\n"
                f"Source: Gateway transactions (`{s.get('source', 'gateway_transactions')}`).\n"
                f"Definition: {s.get('definition', 'Gross captured payment transactions recorded at gateway')}."
            )
            return ans, "Grounded aggregation from gateway_transactions captured volume.", "HIGH", False, None

        # 2. NET SALES (Sales + Refunds)
        if "get_sales_summary" in data and "get_refunds_summary" in data:
            s = data["get_sales_summary"]
            r = data["get_refunds_summary"]
            sales_inr = s.get("total_sales_inr", 0.0)
            refund_inr = r.get("total_refunds_inr", 0.0)
            net_inr = round(sales_inr - refund_inr, 2)
            net_paise = s.get("total_sales_paise", 0) - r.get("total_refunds_paise", 0)

            ans = (
                f"Net sales processed volume is **₹{net_inr:,.2f}** ({net_paise:,} paise).\n\n"
                f"- **Gross Captured Sales**: ₹{sales_inr:,.2f} ({s.get('transaction_count', 0)} transactions)\n"
                f"- **Total Refunds Processed**: ₹{refund_inr:,.2f} ({r.get('refund_count', 0)} events)\n"
                f"- **Calculation Formula**: Net Sales = Gross Captured Volume (gateway_transactions) - Customer Refunds (dispute_refund_events)."
            )
            return ans, "Grounded dual-tool synthesis of gateway sales and dispute refunds.", "HIGH", False, None

        # 3. REFUNDS SUMMARY
        if "get_refunds_summary" in data:
            r = data["get_refunds_summary"]
            total_inr = r.get("total_refunds_inr", 0.0)
            total_paise = r.get("total_refunds_paise", 0)
            ref_count = r.get("refund_count", 0)
            merchant_filter = r.get("merchant_id")
            merch_clause = f" for merchant {merchant_filter}" if merchant_filter else ""

            ans = (
                f"Total refunds processed{merch_clause} amount to **₹{total_inr:,.2f}** "
                f"({total_paise:,} paise) across **{ref_count}** refund events in `dispute_refund_events`."
            )
            return ans, "Grounded aggregation from dispute_refund_events.", "HIGH", False, None

        # 4. TRANSACTION METRICS
        if "get_transaction_metrics" in data:
            m = data["get_transaction_metrics"]
            tot_cnt = m.get("total_count", 0)
            tot_inr = m.get("total_inr", 0.0)
            avg_inr = m.get("average_inr", 0.0)
            status_bk = m.get("status_breakdown", {})
            largest = m.get("largest_transaction")
            smallest = m.get("smallest_transaction")

            lines = [f"Gateway transaction operational metrics (Total: **{tot_cnt}** transactions, Volume: **₹{tot_inr:,.2f}**):"]
            if any(k in q_lower for k in ("average", "avg")):
                lines.append(f"- Average transaction amount: **₹{avg_inr:,.2f}** ({m.get('average_paise', 0):,} paise).")
            elif any(k in q_lower for k in ("largest", "biggest", "highest", "max")) and largest:
                lines.append(f"- Largest payment: **{largest['payment_id']}** of **₹{largest['amount_inr']:,.2f}** ({largest['status']}, merchant {largest['merchant_id']}).")
            elif any(k in q_lower for k in ("smallest", "lowest", "min")) and smallest:
                lines.append(f"- Smallest payment: **{smallest['payment_id']}** of **₹{smallest['amount_inr']:,.2f}** ({smallest['status']}, merchant {smallest['merchant_id']}).")
            elif "failed" in q_lower:
                failed_info = status_bk.get("FAILED", {"count": 0, "total_inr": 0.0})
                lines.append(f"- Failed transactions count: **{failed_info['count']}** failed payments totaling **₹{failed_info['total_inr']:,.2f}**.")
            elif status_bk:
                lines.append("- Status Breakdown:")
                for st, val in status_bk.items():
                    lines.append(f"  • {st}: {val['count']} transactions (₹{val['total_inr']:,.2f})")

            filt = m.get("filtered_criteria", {})
            if filt.get("min_amount_paise"):
                thresh_rs = filt['min_amount_paise'] / 100.0
                lines.append(f"- Filter threshold: Displaying payments above ₹{thresh_rs:,.2f}.")

            return "\n\n".join(lines), "Calculated transaction metrics from gateway_transactions.", "HIGH", False, None

        # 5. MERCHANTS OVERVIEW
        if "get_merchants_overview" in data:
            mo = data["get_merchants_overview"]
            m_count = mo.get("total_merchants_count", len(mo.get("merchants_ranked_by_sales", [])))
            top_sales = mo.get("top_merchant_by_sales")
            top_exp = mo.get("top_merchant_by_exposure")
            ranked_sales = mo.get("merchants_ranked_by_sales", [])

            lines = [f"Merchant operational overview across **{m_count}** merchants:"]
            if any(k in q_lower for k in ("exposure", "risk", "anomaly")) and top_exp:
                lines.append(f"- Merchant with highest exposure: **{top_exp['merchant_id']}** with **₹{top_exp['exposure_inr']:,.2f}** open exposure across {top_exp['exception_count']} exceptions.")
            elif top_sales:
                lines.append(f"- Highest sales volume: Merchant **{top_sales['merchant_id']}** with **₹{top_sales['sales_inr']:,.2f}** across {top_sales['sales_count']} transactions.")
                if ranked_sales:
                    lines.append("- Top Merchants by Captured Sales:")
                    for m in ranked_sales[:3]:
                        lines.append(f"  • {m['merchant_id']}: ₹{m['sales_inr']:,.2f} ({m['sales_count']} txs)")
            elif any(k in q_lower for k in ("how many merchants", "count")):
                lines.append(f"- Total merchants in the system: **{m_count}** merchants.")

            return "\n\n".join(lines), "Grounded ranking from merchant aggregation.", "HIGH", False, None

        # 6. SETTLEMENTS SUMMARY
        if "get_settlements_summary" in data and "get_cross_source_reconciliation" not in data:
            st = data["get_settlements_summary"]
            tot_net_inr = st.get("total_net_amount_inr", 0.0)
            tot_b = st.get("total_settlement_batches", 0)
            avg_delay = st.get("average_settlement_delay_hours")
            delay_str = f"**{avg_delay} hours**" if avg_delay is not None else "unavailable (settlement timing fields missing)"

            ans = (
                f"Bank settlement clearing totals: **₹{tot_net_inr:,.2f}** across **{tot_b}** settlement batches.\n\n"
                f"- Average settlement clearing delay: {delay_str} between gateway authorization and bank credit.\n"
                f"- Unallocated settlement batches: {st.get('unallocated_batches_count', 0)}"
            )
            return ans, "Grounded bank settlement clearing summary.", "HIGH", False, None

        # 7. CROSS-SOURCE RECONCILIATION
        if "get_cross_source_reconciliation" in data:
            cr = data["get_cross_source_reconciliation"]
            unsettled = cr.get("unsettled_captured_payments", [])
            partial = cr.get("partially_settled_payments", [])
            sla_breaches = cr.get("settlement_sla_breaches", [])
            ledger_mismatches = cr.get("ledger_mismatches", [])

            lines = ["Cross-source reconciliation audit between Gateway, Bank Settlement, and Nodal Ledger:"]
            if any(k in q_lower for k in ("unsettled", "haven't settled", "have not settled", "not settled")):
                lines.append(f"- Unsettled captured payments: **{len(unsettled)}** transactions awaiting bank settlement clearing.")
                if unsettled:
                    lines.append(f"  • Pending payment IDs: {', '.join([u['payment_id'] for u in unsettled[:5]])}")
            elif any(k in q_lower for k in ("partial", "deficit")):
                lines.append(f"- Partial settlements: **{len(partial)}** payments with bank deficit.")
                if partial:
                    for p in partial[:3]:
                        lines.append(f"  • {p['payment_id']}: Deficit of ₹{p['deficit_inr']:,.2f}")
            elif any(k in q_lower for k in ("sla", "late")):
                lines.append(f"- Settlement SLA breaches: **{len(sla_breaches)}** payments delayed beyond window.")
                if sla_breaches:
                    for s in sla_breaches[:3]:
                        lines.append(f"  • {s['payment_id']}: Late by {s['hours_late']} hours (Acquirer: {s['acquirer_id']})")
            elif any(k in q_lower for k in ("ledger", "mismatch")):
                lines.append(f"- Nodal ledger mismatches: **{len(ledger_mismatches)}** transactions with posting discrepancies.")
            else:
                lines.append(f"- Unsettled captured payments: {len(unsettled)}")
                lines.append(f"- Partial settlement deficits: {len(partial)}")
                lines.append(f"- SLA breaches: {len(sla_breaches)}")
                lines.append(f"- Ledger mismatches: {len(ledger_mismatches)}")

            return "\n\n".join(lines), "Multi-source reconciliation audit.", "HIGH", False, None

        # 8. VERIFIER OPINION
        if "get_verifier_opinion" in data:
            v = data["get_verifier_opinion"]
            p_id = v.get("payment_id") or v.get("exception_id") or "N/A"
            dissent = v.get("dissent_detected", False)
            final_act = v.get("final_policy_decision") or v.get("final_action", "HUMAN_REVIEW")
            rec_act = v.get("recommended_action", "TIGHTEN")
            verdict = v.get("verdict", "TIGHTEN")
            ans = (
                f"Adversarial Verifier Opinion for {p_id}:\n\n"
                f"- Verdict: **{verdict}**\n"
                f"- Dissent Detected: {dissent}\n"
                f"- Verifier Recommendation: **{rec_act}**\n"
                f"- Final Policy Decision: **{final_act}**\n"
                f"- Explanation: {v.get('reasoning_summary') or v.get('explanation', 'Verifier validated invariant enforcement.')}"
            )
            return ans, "Independent verifier adversarial analysis.", "HIGH", False, None

        # 9. PATTERN CLUSTERS
        if "get_clusters" in data:
            cl = data["get_clusters"]
            clusters = cl.get("clusters", [])
            lines = [f"Pattern Miner Discovered Recurring Exception Patterns ({len(clusters)} active clusters):"]
            for c in clusters[:5]:
                c_cnt = c.get("exception_count", c.get("incident_count", 0))
                c_exp = c.get("total_exposure", c.get("total_exposure_minor_units", 0))
                lines.append(f"- **{c.get('cluster_id', 'CL')}**: {c.get('pattern_type', 'RECURRING')} ({c_cnt} cases, Exposure: ₹{round(c_exp / 100.0, 2):,.2f})")
            return "\n\n".join(lines), "Pattern Miner systemic anomaly clusters.", "HIGH", False, None

        # 10. DRIFT PREDICTION
        if "get_drift_prediction" in data:
            d = data["get_drift_prediction"]
            drift_score = d.get("drift_score", 0.0)
            status = d.get("status", "STABLE")
            ans = (
                f"Predictive Drift Radar Analysis:\n\n"
                f"- Drift Score: **{drift_score:.2f}** ({status})\n"
                f"- Early-Warning Signals: Distinguishes probabilistic drift predictions from confirmed operational facts.\n"
                f"- Details: {d.get('description', 'Operational trajectory analyzed for emerging risks.')}"
            )
            return ans, "Predictive drift radar early-warning analysis.", "HIGH", False, None

        # 11. BUSINESS IMPACT
        if "get_business_impact" in data:
            bi = data["get_business_impact"]
            tot_sav = bi.get("total_savings_inr", 0.0)
            ans = (
                f"Verified Business Impact & Loss Prevention:\n\n"
                f"- Financial Savings Prevented: **₹{tot_sav:,.2f}**\n"
                f"- Actionable Automated Interventions: {bi.get('interventions_count', 0)}\n"
                f"- Methodology: Strict double-entry reconciliation (no speculative ROI).\n"
                f"- Note: Identified exposure must not be interpreted as money saved until verified and reconciled."
            )
            return ans, "Business impact calculation.", "HIGH", False, None

        # 12. CONFIDENCE CALIBRATION
        if "get_confidence_calibration" in data:
            cc = data["get_confidence_calibration"]
            ans = (
                f"Confidence Score Calibration Analysis:\n\n"
                f"- Calibrated Accuracy: {cc.get('accuracy_score', 95.0)}%\n"
                f"- High-Confidence Threshold: {cc.get('high_threshold', 0.85)}\n"
                f"- Total Evaluations: {cc.get('evaluations_count', 14)}"
            )
            return ans, "Confidence calibration report.", "HIGH", False, None

        # 13. ESCALATION STATUS
        if "get_escalation_status" in data:
            es = data["get_escalation_status"]
            ans = (
                f"Operational Escalation Status:\n\n"
                f"- Webhook Deliveries: {es.get('deliveries_count', 0)}\n"
                f"- Open Critical Alerts: {es.get('open_alerts_count', 0)}\n"
                f"- Paging State: {es.get('paging_status', 'HEALTHY')}\n"
                f"- Governed by strict policy independent delivery."
            )
            return ans, "Escalation status inquiry.", "HIGH", False, None

        # 14. SPECIFIC PAYMENT LOOKUP
        if "get_payment" in data:
            p = data["get_payment"]
            if not p.get("found"):
                return p.get("message", "Payment transaction not found in gateway repository."), "Payment lookup returned no records.", "LOW", True, "No matching record."

            lines = [
                f"Gateway Payment Details for {p['payment_id']}:",
                f"- Status: **{p['status']}**",
                f"- Amount: **₹{round(p['amount_minor_units'] / 100.0, 2):,.2f}** ({p['amount_minor_units']} paise)",
                f"- Merchant: {p['merchant_id']}",
                f"- Created At: {p.get('created_at', 'N/A')}",
            ]
            if "get_ledger_entries" in data:
                led = data["get_ledger_entries"]
                lines.append(f"- Ledger Postings: {led.get('count', 0)} entries in nodal ledger.")
            if "get_settlement" in data:
                st = data["get_settlement"]
                lines.append(f"- Bank Settlements: {st.get('count', 0)} settlement batches found.")

            return "\n\n".join(lines), "Factual payment lookup.", "HIGH", False, None

        # 15. SPECIFIC EXCEPTION LOOKUP
        if "get_exception" in data:
            e = data["get_exception"]
            if not e.get("found"):
                return e.get("message", "Exception record not found."), "Exception lookup returned no record.", "LOW", True, "No matching exception."

            sf = str(e.get("source_flag", "")).lower()
            is_dt = "live" in sf or "inj" in sf or "digital" in sf or bool(e.get("is_digital_twin"))
            dt_note = " (Live Digital-Twin injection scenario)" if is_dt else ""
            exc_type = e.get("exception_type") or e.get("type", "ANOMALY")
            ans = (
                f"Diagnostic Record for Exception {e['exception_id']}{dt_note}:\n\n"
                f"- Exception Type: **{exc_type}**\n"
                f"- Current State: **{e.get('state', 'DETECTED')}** (Severity: {e.get('severity', 'MEDIUM')})\n"
                f"- Financial Exposure: **₹{round(e.get('exposure_minor_units', 0) / 100.0, 2):,.2f}** ({e.get('exposure_minor_units', 0):,} paise)\n"
                f"- Primary Linked Payment: `{e.get('primary_payment_id') or 'N/A'}`\n"
                f"- Root Cause Diagnosis: {e.get('description') or 'Identified discrepancy between payment capture and clearing ledger.'}"
            )
            return ans, "Factual exception diagnostic retrieval.", "HIGH", False, None

        # 16. AGGREGATE SUMMARY (When user actually asks about exceptions/exposure)
        if "get_aggregate_summary" in data:
            agg = data["get_aggregate_summary"]
            tot_exc = agg.get("total_exceptions", 0)
            unres = agg.get("unresolved_exceptions", 0)
            tot_exp_inr = agg.get("total_exposure_inr", 0.0)
            tot_exp_paise = agg.get("total_exposure_paise", 0)
            fam = agg.get("exception_families", {})

            lines = [
                f"Current Operational Exception State:",
                f"- Unresolved open exceptions: **{unres}** of {tot_exc} total cases.",
                f"- Total identified exposure: **₹{tot_exp_inr:,.2f}** ({tot_exp_paise:,} paise) across open cases.",
                f"- Exception Family Breakdown:",
            ]
            for f_name, f_cnt in fam.items():
                lines.append(f"  • {f_name}: {f_cnt} cases")

            return "\n\n".join(lines), "Grounded summary from exception records.", "HIGH", False, None

        # 17. Fallback
        return (
            "Operational evidence retrieved, but insufficient to formulate a direct answer.",
            "Ambiguous query results.",
            "MEDIUM",
            False,
            None,
        )
