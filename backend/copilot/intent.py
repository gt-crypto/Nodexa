"""Lightweight deterministic & semantic intent classification layer for Nodexa Copilot.

Determines the operator's precise query intent prior to selecting and executing
read-only operational tools. Prevents financial aggregation queries (e.g., sales,
volume, refunds) from defaulting to exception-summary tools.
"""
from enum import Enum
import re
from typing import List, Optional, Tuple


class CopilotIntent(str, Enum):
    """Enumeration of recognized Copilot operational query intents."""
    SALES_SUMMARY = "SALES_SUMMARY"
    NET_SALES_SUMMARY = "NET_SALES_SUMMARY"
    REFUND_SUMMARY = "REFUND_SUMMARY"
    SETTLEMENT_SUMMARY = "SETTLEMENT_SUMMARY"
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


class CopilotIntentClassifier:
    """Classifies user queries into distinct financial and operational intents."""

    # Patterns indicating sales / GMV / payment volume queries
    SALES_PATTERNS = [
        r"\b(?:total|gross|all|overall)?\s*(?:amount\s+of\s+)?sales\b",
        r"\b(?:what\s+are\s+my|what\s+is\s+(?:the|our)|show\s+me)\s+(?:total|gross)?\s*sales\b",
        r"\bhow\s+much\s+(?:did\s+we\s+sell|was\s+sold|sales\s+did\s+we\s+make)\b",
        r"\bsales\s+amount\b",
        r"\btotal\s+sales\b",
        r"\bgross\s+sales\b",
        r"\btotal\s+transaction\s+value\b",
        r"\bhow\s+much\s+money\s+was\s+processed\b",
        r"\bhow\s+much\s+(?:payment|transaction)?\s*volume\s+was\s+processed\b",
        r"\btotal\s+payment\s+volume\b",
        r"\bpayment\s+volume\b",
        r"\btotal\s+gmv\b",
        r"\bgmv\b",
        r"\btotal\s+processed\b",
        r"\btotal\s+payments?\s+processed\b",
        r"\bvalue\s+of\s+payments?\s+processed\b",
        r"\bvolume\s+of\s+payments?\s+processed\b",
    ]

    # Patterns indicating net sales (sales after refunds)
    NET_SALES_PATTERNS = [
        r"\bnet\s+sales\b",
        r"\bnet\s+revenue\b",
        r"\bsales\s+after\s+refunds\b",
        r"\bnet\s+processed\b",
        r"\bnet\s+volume\b",
        r"\bnet\s+gmv\b",
    ]

    # Patterns indicating refund queries
    REFUND_PATTERNS = [
        r"\b(?:total|all)?\s*refunds?\b",
        r"\bhow\s+much\s+was\s+refunded\b",
        r"\brefund\s+amount\b",
        r"\btotal\s+refunded\b",
        r"\brefund\s+volume\b",
        r"\brefund\s+count\b",
        r"\bhow\s+many\s+refunds\b",
    ]

    # Patterns indicating exception summary / open exposure queries
    EXCEPTION_SUMMARY_PATTERNS = [
        r"\b(?:how\s+many|number\s+of|count\s+of)?\s*(?:unresolved|open|active|pending)?\s*exceptions\b",
        r"\b(?:total|open|unresolved|current)\s+exposure\b",
        r"\bunresolved\s+cases\b",
        r"\bopen\s+cases\b",
        r"\bexception\s+summary\b",
        r"\bactive\s+exception\s+families\b",
        r"\bwhich\s+exception\s+families\b",
        r"\bhow\s+many\s+anomalies\b",
        r"\bopen\s+anomalies\b",
    ]

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
        """Classifies a query into a CopilotIntent using deterministic heuristics."""
        q_clean = question.strip()
        q_lower = q_clean.lower()
        exc_ids = exc_ids or []
        pay_ids = pay_ids or []
        set_ids = set_ids or []
        ord_ids = ord_ids or []
        merch_ids = merch_ids or []

        # 1. Verification query check (e.g. "is PAY-000001 verified?", "verification status of ...")
        is_verification_query = any(
            k in q_lower for k in [
                "verified",
                "verification",
                "verifier",
                "verifier opinion",
                "is closed",
                "is verified",
                "verification result",
            ]
        )
        if is_verification_query:
            return CopilotIntent.VERIFICATION_STATUS

        # 2. Net Sales queries (must precede general sales to avoid partial match)
        for pattern in cls.NET_SALES_PATTERNS:
            if re.search(pattern, q_lower):
                return CopilotIntent.NET_SALES_SUMMARY

        # 3. Pure Refund queries (must precede general financial queries)
        is_refund_query = any(re.search(p, q_lower) for p in cls.REFUND_PATTERNS)
        if is_refund_query and not any(k in q_lower for k in ["sales", "gmv", "sell"]):
            return CopilotIntent.REFUND_SUMMARY

        # 4. Sales / Volume / GMV queries (High Priority to prevent exception fallback)
        for pattern in cls.SALES_PATTERNS:
            if re.search(pattern, q_lower):
                return CopilotIntent.SALES_SUMMARY

        # 5. Entity-specific investigations
        if exc_ids:
            return CopilotIntent.EXCEPTION_INVESTIGATION

        if pay_ids or ord_ids:
            return CopilotIntent.TRANSACTION_LOOKUP

        if set_ids:
            return CopilotIntent.SETTLEMENT_SUMMARY

        if merch_ids:
            return CopilotIntent.MERCHANT_SUMMARY

        # 6. Merchant discrepancy queries
        if any(k in q_lower for k in ["merchant", "merchants", "vendor", "vendors"]):
            return CopilotIntent.MERCHANT_SUMMARY

        # 7. Pattern Miner / Recurring cluster queries
        if any(k in q_lower for k in [
            "pattern",
            "cluster",
            "recurring",
            "repeated",
            "clustering",
            "largest pattern",
            "recurring patterns",
            "patterns",
        ]):
            return CopilotIntent.PATTERN_SUMMARY

        # 8. Business Impact & ROI queries
        if any(k in q_lower for k in [
            "roi",
            "business impact",
            "money saved",
            "saved",
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
            return CopilotIntent.BUSINESS_IMPACT

        # 9. Predictive Drift Radar queries
        if any(k in q_lower for k in [
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
            return CopilotIntent.DRIFT_PREDICTION

        # 10. Confidence Calibration queries
        if any(k in q_lower for k in [
            "calibration",
            "calibrated",
            "confidence reliable",
            "how reliable is confidence",
            "historical correctness",
            "confidence calibration",
            "brier",
            "ece",
        ]):
            return CopilotIntent.CONFIDENCE_CALIBRATION

        # 11. Escalation Webhook queries
        if any(k in q_lower for k in [
            "webhook",
            "escalation webhook",
            "escalate webhook",
            "downstream alert",
            "escalation status",
            "did we escalate",
            "escalations delivered",
        ]):
            return CopilotIntent.ESCALATION_STATUS

        # 12. Specific Exception Family questions
        if any(k in q_lower for k in [
            "ghost",
            "double dip",
            "double-dip",
            "chargeback",
            "sla breach",
            "sla",
            "breach",
            "partial settlement",
            "unallocated",
            "missing settlement",
            "timing exception",
        ]):
            return CopilotIntent.EXCEPTION_FAMILY_SEARCH

        # 13. Exception Summary queries
        for pattern in cls.EXCEPTION_SUMMARY_PATTERNS:
            if re.search(pattern, q_lower):
                return CopilotIntent.EXCEPTION_SUMMARY

        if any(k in q_lower for k in [
            "exposure",
            "open exceptions",
            "unresolved",
            "families",
            "exceptions",
            "anomaly",
            "anomalies",
            "issues",
        ]):
            return CopilotIntent.EXCEPTION_SUMMARY

        # 14. General Operational Query (fallback)
        return CopilotIntent.GENERAL_OPERATIONAL_QUERY
