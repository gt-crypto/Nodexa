"""Lightweight deterministic & semantic intent classification layer for Nodexa Copilot.

Determines the operator's precise query intent prior to selecting and executing
read-only operational tools. Prevents financial aggregation queries (e.g., sales,
processed volume, refunds) from defaulting to exception-summary tools.
"""
from enum import Enum
import re
from typing import Any, Dict, List, Optional, Tuple


class CopilotIntent(str, Enum):
    """Enumeration of recognized Copilot operational query intents."""
    SALES_SUMMARY = "SALES_SUMMARY"
    NET_SALES_SUMMARY = "NET_SALES_SUMMARY"
    REFUND_SUMMARY = "REFUND_SUMMARY"
    SETTLEMENT_SUMMARY = "SETTLEMENT_SUMMARY"
    TRANSACTION_METRICS = "TRANSACTION_METRICS"
    CROSS_SOURCE_RECONCILIATION = "CROSS_SOURCE_RECONCILIATION"
    MERCHANT_ANALYTICS = "MERCHANT_ANALYTICS"
    TRANSACTION_LOOKUP = "TRANSACTION_LOOKUP"
    EXCEPTION_INVESTIGATION = "EXCEPTION_INVESTIGATION"
    EXCEPTION_SUMMARY = "EXCEPTION_SUMMARY"
    EXCEPTION_FAMILY_SEARCH = "EXCEPTION_FAMILY_SEARCH"
    MERCHANT_SUMMARY = "MERCHANT_SUMMARY"
    PATTERN_SUMMARY = "PATTERN_SUMMARY"
    VERIFICATION_STATUS = "VERIFICATION_STATUS"
    DRIFT_PREDICTION = "DRIFT_PREDICTION"
    CONFIDENCE_CALIBRATION = "CONFIDENCE_CALIBRATION"
    ESCALATION_STATUS = "ESCALATION_STATUS"
    BUSINESS_IMPACT = "BUSINESS_IMPACT"
    GENERAL_OPERATIONAL_QUERY = "GENERAL_OPERATIONAL_QUERY"


class QueryPlan:
    """Structured execution plan for one or more read-only operational tools."""
    def __init__(
        self,
        intent: CopilotIntent,
        tools: List[str],
        params: Optional[Dict[str, Any]] = None,
        reasoning: str = "",
    ):
        self.intent = intent
        self.tools = tools
        self.params = params or {}
        self.reasoning = reasoning


class CopilotIntentClassifier:
    """Classifies user queries and formulates a multi-source read-only QueryPlan."""

    EXCEPTION_KEYWORDS = [
        "exception",
        "exceptions",
        "exposure",
        "unresolved",
        "stuck",
        "tied up",
        "anomaly",
        "anomalies",
        "lost",
        "breach",
        "discrepanc",
        "flagged",
    ]

    NON_VOLUME_PROCESS_KEYWORDS = [
        "remediation process",
        "investigation process",
        "approval process",
        "policy process",
        "verification process",
        "process sla",
        "processing sla",
        "why did",
        "fail during processing",
        "failed during processing",
    ]

    NET_SALES_PATTERNS = [
        r"\bnet\s+sales\b",
        r"\bnet\s+revenue\b",
        r"\bsales\s+after\s+refunds\b",
        r"\bnet\s+processed\b",
        r"\bnet\s+volume\b",
        r"\bnet\s+gmv\b",
        r"\bnet\s+amount\b",
    ]

    REFUND_PATTERNS = [
        r"\b(?:total|all)?\s*refunds?\b",
        r"\bhow\s+much\s+(?:was|were)\s+refunded\b",
        r"\brefund\s+amount\b",
        r"\btotal\s+refunded\b",
        r"\brefund\s+volume\b",
        r"\brefund\s+count\b",
        r"\bhow\s+many\s+refunds\b",
        r"\blargest\s+refund\b",
        r"\bchargeback\b",
    ]

    SALES_AND_VOLUME_PATTERNS = [
        r"\b(?:total|gross|all|overall)?\s*(?:amount\s+of\s+)?sales\b",
        r"\b(?:what\s+are\s+my|what\s+is\s+(?:the|our)|show\s+me)\s+(?:total|gross)?\s*sales\b",
        r"\bhow\s+much\s+(?:did\s+we\s+sell|was\s+sold|sales\s+did\s+we\s+make)\b",
        r"\bsales\s+amount\b",
        r"\btotal\s+sales\b",
        r"\bgross\s+sales\b",
        r"\bhow\s+much\s+money\s+(?:did\s+we\s+process|was\s+processed|have\s+we\s+processed|is\s+processed)\b",
        r"\bhow\s+much\s+(?:did\s+we\s+process|was\s+processed|have\s+we\s+processed)\b",
        r"\bwhat\s+amount\s+(?:did\s+we\s+process|was\s+processed)\b",
        r"\b(?:what\s+is|what\s+was)\s+(?:our\s+|the\s+)?(?:total\s+)?processed\s+volume\b",
        r"\b(?:what\s+is|what\s+was)\s+(?:our\s+|the\s+)?total\s+processed\s+amount\b",
        r"\btotal\s+processed\s+amount\b",
        r"\bhow\s+much\s+payment\s+volume\s+(?:did\s+we\s+process|was\s+processed)\b",
        r"\b(?:what\s+is|what\s+was)\s+(?:our\s+|the\s+)?(?:total\s+)?payment\s+volume\b",
        r"\bpayment\s+volume\b",
        r"\btransaction\s+volume\b",
        r"\bprocessed\s+volume\b",
        r"\btotal\s+payment\s+volume\b",
        r"\btotal\s+transaction\s+value\b",
        r"\btransaction\s+value\b",
        r"\bpayment\s+value\b",
        r"\bhow\s+much\s+was\s+processed\s+in\s+payments\b",
        r"\bhow\s+much\s+was\s+processed\b",
        r"\bhow\s+much\s+did\s+customers\s+pay\b",
        r"\bhow\s+much\s+money\s+flowed\s+through\b",
        r"\bflowed\s+through\s+(?:the\s+)?(?:system|nodexa)\b",
        r"\bprocessed\s+through\s+(?:the\s+)?(?:system|nodexa)\b",
        r"\btotal\s+captured\s+amount\b",
        r"\bcaptured\s+amount\b",
        r"\btotal\s+gmv\b",
        r"\bgmv\b",
        r"\btotal\s+processed\b",
        r"\btotal\s+payments?\s+processed\b",
        r"\bvalue\s+of\s+payments?\s+processed\b",
        r"\bvolume\s+of\s+payments?\s+processed\b",
    ]

    EXCEPTION_SUMMARY_PATTERNS = [
        r"\b(?:how\s+many|number\s+of|count\s+of)?\s*(?:unresolved|open|active|pending)?\s*exceptions\b",
        r"\b(?:total|open|unresolved|current)\s+exposure\b",
        r"\bhow\s+much\s+(?:is\s+(?:our\s+|the\s+)?(?:open\s+|unresolved\s+)?)?exposure\b",
        r"\b(?:how\s+much\s+money\s+is\s+)?(?:stuck|tied\s+up)\s+in\s+exceptions\b",
        r"\b(?:how\s+much\s+money\s+was\s+)?lost\s+due\s+to\s+exceptions\b",
        r"\bunresolved\s+cases\b",
        r"\bopen\s+cases\b",
        r"\bexception\s+summary\b",
        r"\bactive\s+exception\s+families\b",
        r"\bwhich\s+exception\s+families\b",
        r"\bhow\s+many\s+anomalies\b",
        r"\bopen\s+anomalies\b",
    ]

    @classmethod
    def plan_query(
        cls,
        question: str,
        exc_ids: Optional[List[str]] = None,
        pay_ids: Optional[List[str]] = None,
        set_ids: Optional[List[str]] = None,
        ord_ids: Optional[List[str]] = None,
        merch_ids: Optional[List[str]] = None,
    ) -> QueryPlan:
        """Formulates a multi-dataset operational QueryPlan for answering general financial inquiries."""
        q_clean = question.strip()
        q_norm = re.sub(r"[^\w\s-]", " ", q_clean.lower())
        q_norm = re.sub(r"\s+", " ", q_norm).strip()
        q_lower = q_norm
        exc_ids = exc_ids or []
        pay_ids = pay_ids or []
        set_ids = set_ids or []
        ord_ids = ord_ids or []
        merch_ids = merch_ids or []

        # 1. Verification query check
        is_verification_query = any(
            k in q_lower for k in [
                "verified", "verification", "verifier", "verifier opinion",
                "is closed", "is verified", "verification result", "failed verification",
                "unresolved verification", "verified closed"
            ]
        )
        if is_verification_query:
            tools = ["get_verifier_opinion"]
            if pay_ids:
                tools.insert(0, "get_payment")
            elif exc_ids:
                tools.insert(0, "get_exception")
            else:
                tools = ["search_exceptions", "get_aggregate_summary"]
            return QueryPlan(
                intent=CopilotIntent.VERIFICATION_STATUS,
                tools=tools,
                reasoning="Verification status query for specific case or aggregate closed/pending verification.",
            )

        # 2. Cross-source reconciliation (Compare gateway vs settlement, unsettled captured, SLA breaches, ledger mismatches)
        is_cross_source = any(k in q_lower for k in [
            "compare", "mismatch", "mismatches", "unsettled", "not settled", "has not settled", "no settlement",
            "differ", "differs", "partial settlement", "partial settlements", "sla breach", "sla breaches",
            "breached", "ledger mismatch", "variance", "difference between gateway and settlement",
            "gateway amounts with settlement", "gateway vs settlement", "captured without settlement"
        ]) or (("captured" in q_lower or "gateway" in q_lower or "payments" in q_lower) and ("settlement" in q_lower or "settled" in q_lower) and any(neg in q_lower for neg in ["no", "not", "without", "zero", "missing", "unsettled"]))
        if is_cross_source and not exc_ids and not pay_ids and not set_ids:
            return QueryPlan(
                intent=CopilotIntent.CROSS_SOURCE_RECONCILIATION,
                tools=["get_cross_source_reconciliation", "get_settlements_summary", "get_sales_summary"],
                reasoning="Cross-source reconciliation comparing gateway transactions, settlement batches, SLAs, and nodal ledger.",
            )

        # 3. Merchant analytics & rankings (e.g. top merchant by sales, merchant with highest exposure, refund vs sales)
        is_merchant_analytics = any(k in q_lower for k in [
            "how many merchants", "which merchant", "top merchant", "merchant processed the most",
            "highest exposure", "most exceptions", "merchant-wise", "refunds greater than their sales",
            "refund greater than sales", "merchant rankings", "merchants with most", "merchant count",
            "which merchant has", "who processed the most", "who sold the most"
        ])
        if is_merchant_analytics and not merch_ids:
            return QueryPlan(
                intent=CopilotIntent.MERCHANT_ANALYTICS,
                tools=["get_merchants_overview", "get_merchant_discrepancies"],
                reasoning="Comprehensive merchant intelligence, rankings by sales, exception exposure, and refund volume.",
            )

        # 4. Transaction analytics (averages, min/max, counts by status, thresholds like > 50,000)
        is_tx_analytics = any(k in q_lower for k in [
            "average transaction", "average payment", "largest payment", "largest transaction",
            "smallest transaction", "smallest payment", "highest payment", "highest transaction",
            "lowest payment", "lowest transaction", "how many transactions", "how many captured transactions",
            "how many failed transactions", "transaction count", "payment count", "total number of transactions",
            "which payment failed", "failed transactions", "transactions above", "payments above",
            "transactions over", "payments over", "transactions greater", "payments greater",
            "transactions exceeding", "payments exceeding", "transactions more than", "payments more than",
            "transactions higher than", "payments higher than", "show transactions"
        ])
        if is_tx_analytics and not pay_ids and not exc_ids:
            min_amt = None
            # Check for threshold like 50000 or 50,000 against q_clean to preserve numbers with commas
            amt_match = re.search(
                r"(?:above|greater than|>|over|more than|exceeding|higher than)\s*(?:[^\d\s]*\s*)?(\d+(?:,\d+)*(?:\.\d+)?)",
                q_clean,
                re.IGNORECASE,
            )
            if amt_match:
                raw_num = amt_match.group(1).replace(",", "")
                try:
                    min_amt = int(float(raw_num) * 100)
                except ValueError:
                    pass

            status_filter = None
            if "failed" in q_lower:
                status_filter = "FAILED"
            elif "captured" in q_lower:
                status_filter = "CAPTURED"
            elif "authorized" in q_lower:
                status_filter = "AUTHORIZED"

            return QueryPlan(
                intent=CopilotIntent.TRANSACTION_METRICS,
                tools=["get_transaction_metrics", "get_sales_summary"],
                params={"status": status_filter, "min_amount_paise": min_amt},
                reasoning="Detailed transaction metrics covering counts, averages, extremes, and value distributions.",
            )

        # 5. Settlement metrics (total settlement amount, how many settlements, average settlement time, late settlements)
        is_settlement_query = any(k in q_lower for k in [
            "settlement amount", "total settlement", "how many settlements", "average settlement",
            "settlement time", "settlement clearing", "clearing time", "clearing delay",
            "settlement delay", "late settlements", "largest settlement", "which settlements are late",
            "settlement batches", "unallocated settlement", "settlement count", "total settled"
        ]) or ("settlement" in q_lower and any(w in q_lower for w in ["average", "clearing", "time", "delay", "total", "amount", "batch", "batches", "count"]))
        if is_settlement_query and not set_ids and not pay_ids:
            return QueryPlan(
                intent=CopilotIntent.SETTLEMENT_SUMMARY,
                tools=["get_settlements_summary", "get_cross_source_reconciliation"],
                reasoning="Bank settlement batch statistics, total cleared amount, timing delays, and unallocated lines.",
            )

        # 6. Net Sales queries
        for pattern in cls.NET_SALES_PATTERNS:
            if re.search(pattern, q_lower):
                return QueryPlan(
                    intent=CopilotIntent.NET_SALES_SUMMARY,
                    tools=["get_sales_summary", "get_refunds_summary"],
                    reasoning="Net sales aggregation deducting customer refunds from gross captured sales.",
                )

        # 7. Pure Refund queries
        is_refund_query = any(re.search(p, q_lower) for p in cls.REFUND_PATTERNS)
        if is_refund_query and not any(k in q_lower for k in ["sales", "gmv", "sell", "process"]):
            return QueryPlan(
                intent=CopilotIntent.REFUND_SUMMARY,
                tools=["get_refunds_summary"],
                reasoning="Customer refund volume and dispute event aggregation.",
            )

        # 8. Sales / Payment Volume / GMV queries
        has_exception_context = any(kw in q_lower for kw in cls.EXCEPTION_KEYWORDS)
        is_non_volume_process = any(k in q_lower for k in cls.NON_VOLUME_PROCESS_KEYWORDS)

        if not has_exception_context and not is_non_volume_process:
            for pattern in cls.SALES_AND_VOLUME_PATTERNS:
                if re.search(pattern, q_lower):
                    return QueryPlan(
                        intent=CopilotIntent.SALES_SUMMARY,
                        tools=["get_sales_summary"],
                        reasoning="Total gross payment/sales volume from captured gateway transactions.",
                    )

            has_amount_query = any(k in q_lower for k in [
                "how much", "what amount", "what was", "what is", "total", "volume", "amount", "show me", "tell me"
            ])
            has_processing_term = any(k in q_lower for k in [
                "process", "processed", "processing", "flowed", "sales", "sold", "gmv", "payment volume", "transaction volume"
            ])
            if has_amount_query and has_processing_term:
                return QueryPlan(
                    intent=CopilotIntent.SALES_SUMMARY,
                    tools=["get_sales_summary"],
                    reasoning="Payment volume query mapped from natural language processing combination.",
                )

            if any(k in q_lower for k in [
                "payments processed", "transactions processed", "money processed", "processed money",
                "payment volume", "transaction volume", "processed volume", "processed amount",
                "volume processed", "amount processed"
            ]):
                return QueryPlan(
                    intent=CopilotIntent.SALES_SUMMARY,
                    tools=["get_sales_summary"],
                    reasoning="Explicit payment volume and transaction value query.",
                )

        # 9. Entity-specific lookups
        if exc_ids:
            return QueryPlan(
                intent=CopilotIntent.EXCEPTION_INVESTIGATION,
                tools=["get_exception", "get_risk_assessment", "get_control_findings", "get_policy_decision", "get_verifier_opinion"],
                params={"exception_id": exc_ids[0]},
                reasoning=f"Deep operational investigation for exception {exc_ids[0]}.",
            )

        if pay_ids or ord_ids:
            target_id = pay_ids[0] if pay_ids else ord_ids[0]
            tools = ["get_payment", "get_settlement", "get_ledger_entries"]
            if ord_ids:
                tools.append("get_order")
            return QueryPlan(
                intent=CopilotIntent.TRANSACTION_LOOKUP,
                tools=tools,
                params={"payment_id": target_id},
                reasoning=f"Gateway payment and ledger lifecycle lookup for {target_id}.",
            )

        if set_ids:
            return QueryPlan(
                intent=CopilotIntent.SETTLEMENT_SUMMARY,
                tools=["get_settlement"],
                params={"settlement_id": set_ids[0]},
                reasoning=f"Bank settlement clearing batch lookup for {set_ids[0]}.",
            )

        if merch_ids:
            return QueryPlan(
                intent=CopilotIntent.MERCHANT_SUMMARY,
                tools=["get_merchant_trust_score", "get_sales_summary"],
                params={"merchant_id": merch_ids[0]},
                reasoning=f"Merchant operational profile and trust score lookup for {merch_ids[0]}.",
            )

        # 10. Pattern Miner
        if any(k in q_lower for k in [
            "pattern", "cluster", "recurring", "repeated", "clustering", "largest pattern",
            "recurring patterns", "patterns", "most common exception pattern"
        ]):
            return QueryPlan(
                intent=CopilotIntent.PATTERN_SUMMARY,
                tools=["get_clusters"],
                reasoning="Pattern Miner systemic cluster analysis.",
            )

        # 11. Business Impact & ROI
        if any(k in q_lower for k in [
            "roi", "business impact", "money saved", "saved", "save", "recovered", "recovery",
            "financial exposure has sentinel", "what business impact"
        ]):
            return QueryPlan(
                intent=CopilotIntent.BUSINESS_IMPACT,
                tools=["get_business_impact"],
                reasoning="Business impact and identified exposure quantification.",
            )

        # 12. Drift & Calibration
        if any(k in q_lower for k in ["drift", "deteriorating", "early warning", "radar", "drift score"]):
            return QueryPlan(
                intent=CopilotIntent.DRIFT_PREDICTION,
                tools=["get_drift_prediction"],
                reasoning="Predictive Nodal Drift Radar health signals.",
            )

        if any(k in q_lower for k in ["calibration", "calibrated", "confidence reliable", "brier", "ece"]):
            return QueryPlan(
                intent=CopilotIntent.CONFIDENCE_CALIBRATION,
                tools=["get_confidence_calibration"],
                reasoning="Empirical confidence calibration and observed outcome metrics.",
            )

        if any(k in q_lower for k in ["webhook", "escalation webhook", "downstream alert", "escalations delivered"]):
            return QueryPlan(
                intent=CopilotIntent.ESCALATION_STATUS,
                tools=["get_escalation_status"],
                reasoning="Outbound escalation webhook dispatcher configuration and logs.",
            )

        # 13. Specific Exception Families
        if any(k in q_lower for k in [
            "ghost", "double dip", "double-dip", "sla breach", "partial settlement", "unallocated", "missing settlement", "timing exception"
        ]):
            return QueryPlan(
                intent=CopilotIntent.EXCEPTION_FAMILY_SEARCH,
                tools=["search_exceptions"],
                reasoning="Targeted exception family search across active operational records.",
            )

        # 14. Exception Summary & Exposure
        for pattern in cls.EXCEPTION_SUMMARY_PATTERNS:
            if re.search(pattern, q_lower):
                return QueryPlan(
                    intent=CopilotIntent.EXCEPTION_SUMMARY,
                    tools=["get_aggregate_summary"],
                    reasoning="Unresolved open exception count and cumulative exposure overview.",
                )

        if any(k in q_lower for k in ["exposure", "open exceptions", "unresolved", "exceptions", "anomaly", "anomalies"]):
            return QueryPlan(
                intent=CopilotIntent.EXCEPTION_SUMMARY,
                tools=["get_aggregate_summary"],
                reasoning="General exception summary.",
            )

        # 15. Default general overview
        return QueryPlan(
            intent=CopilotIntent.GENERAL_OPERATIONAL_QUERY,
            tools=["get_sales_summary", "get_aggregate_summary"],
            reasoning="Broad operational overview combining financial volume and exception health.",
        )

    @classmethod
    def classify(
        cls,
        question: str,
        exc_ids: Optional[List[str]] = None,
        pay_ids: Optional[List[str]] = None,
        set_ids: Optional[List[str]] = None,
        ord_ids: Optional[List[str]] = None,
        merch_ids: Optional[List[str]] = None,
    ) -> CopilotIntent:
        """Backward-compatible intent classification entrypoint."""
        plan = cls.plan_query(
            question=question,
            exc_ids=exc_ids,
            pay_ids=pay_ids,
            set_ids=set_ids,
            ord_ids=ord_ids,
            merch_ids=merch_ids,
        )
        return plan.intent
