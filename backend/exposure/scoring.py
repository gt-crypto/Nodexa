"""Deterministic risk scoring, priority mapping, escalation logic, and explanation generator."""
from typing import Dict, Optional, Tuple

from backend.models.enums import (
    PriorityLevel,
    EscalationRecommendation,
    MaterialityLevel,
    ExceptionType,
)
from backend.models.exceptions import ExceptionRecord
from backend.exposure.config import (
    EXPOSURE_LOW,
    EXPOSURE_MEDIUM,
    EXPOSURE_HIGH,
    EXPOSURE_SEVERE,
    P1_MIN_SCORE,
    P2_MIN_SCORE,
    P3_MIN_SCORE,
)
from backend.exposure.models import RiskFactors


def calculate_risk_score(factors: RiskFactors) -> Tuple[int, Dict[str, int]]:
    """Calculates deterministic 0-100 risk score and inspectable component breakdown."""
    # Special zero-exposure handling for legitimate observations
    if factors.exposure_amount <= 0:
        breakdown = {
            "financial_exposure_score": 0,
            "severity_score": 0,
            "control_failure_score": 0,
            "confidence_score": 0,
            "complexity_score": 0,
            "sla_score": 0,
            "ledger_risk_score": 0,
            "allocation_risk_score": 0,
            "total": 0,
        }
        return 0, breakdown

    # 1. Financial Exposure Score (Max 30)
    exp = factors.exposure_amount
    if exp < EXPOSURE_LOW:
        exp_score = 5
    elif exp < EXPOSURE_MEDIUM:
        exp_score = 10
    elif exp < EXPOSURE_HIGH:
        exp_score = 18
    elif exp < EXPOSURE_SEVERE:
        exp_score = 25
    else:
        exp_score = 30

    # 2. Severity Score (Max 20)
    sev = factors.severity_level.upper()
    if sev == "CRITICAL":
        sev_score = 20
    elif sev == "HIGH":
        sev_score = 15
    elif sev == "MEDIUM":
        sev_score = 10
    else:
        sev_score = 5

    # 3. Control Failure Score (Max 15)
    ctrl_score = min(15, factors.control_failure_count * 7)

    # 4. Investigation Confidence Score (Max 10)
    conf = factors.investigation_confidence
    if conf == "HIGH":
        conf_score = 10
    elif conf == "MEDIUM":
        conf_score = 6
    elif conf == "LOW":
        conf_score = 2
    else:
        conf_score = 5

    # 5. Operational Complexity Score (Max 5)
    if factors.affected_record_count > 2:
        comp_score = 5
    elif factors.affected_record_count == 2:
        comp_score = 3
    else:
        comp_score = 1

    # 6. SLA Score (Max 10)
    sla_score = 10 if factors.sla_breached else 0

    # 7. Ledger Risk Score (Max 5)
    ledger_score = 5 if factors.ledger_contradiction else 0

    # 8. Allocation / Double-Dip Risk Score (Max 5)
    alloc_score = 5 if (factors.is_unallocated or factors.is_double_dip) else 0

    total_score = min(100, max(0, exp_score + sev_score + ctrl_score + conf_score + comp_score + sla_score + ledger_score + alloc_score))

    breakdown = {
        "financial_exposure_score": exp_score,
        "severity_score": sev_score,
        "control_failure_score": ctrl_score,
        "confidence_score": conf_score,
        "complexity_score": comp_score,
        "sla_score": sla_score,
        "ledger_risk_score": ledger_score,
        "allocation_risk_score": alloc_score,
        "total": total_score,
    }

    return total_score, breakdown


def determine_priority(risk_score: int, exposure: int) -> str:
    """Maps risk score to priority level (P1-P4), strictly enforcing P4 for zero-exposure cases."""
    if exposure <= 0:
        return PriorityLevel.P4.value

    if risk_score >= P1_MIN_SCORE:
        return PriorityLevel.P1.value
    elif risk_score >= P2_MIN_SCORE:
        return PriorityLevel.P2.value
    elif risk_score >= P3_MIN_SCORE:
        return PriorityLevel.P3.value
    else:
        return PriorityLevel.P4.value


def determine_escalation(
    exception_type: str,
    severity: str,
    priority: str,
    exposure: int,
    root_cause_category: Optional[str] = None,
) -> str:
    """Determines deterministic escalation recommendation."""
    if exposure <= 0:
        return EscalationRecommendation.NO_ESCALATION.value

    if priority == PriorityLevel.P1.value or severity == "CRITICAL" or exception_type == ExceptionType.GHOST_SETTLEMENT.value:
        return EscalationRecommendation.IMMEDIATE_ESCALATION.value

    if "UNALLOCATED" in exception_type or root_cause_category == "UNALLOCATED_FUNDS":
        return EscalationRecommendation.FINANCE_REVIEW.value

    if exception_type == ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value:
        return EscalationRecommendation.RISK_REVIEW.value

    if priority in (PriorityLevel.P2.value, PriorityLevel.P3.value):
        return EscalationRecommendation.OPERATIONS_REVIEW.value

    return EscalationRecommendation.NO_ESCALATION.value


def generate_risk_explanation(
    exception: ExceptionRecord,
    materiality: str,
    priority: str,
    score: int,
    breakdown: Dict[str, int],
    escalation: str,
    root_cause_category: Optional[str] = None,
) -> str:
    """Generates structured deterministic natural-language explanation from calculated factors."""
    exp_inr = (exception.exposure or 0) / 100.0

    if exception.exposure <= 0:
        return (
            f"Priority {priority} (Risk Score: {score}/100). "
            f"Zero financial exposure detected. Case classified as legitimate operational observation "
            f"with materiality {materiality} and escalation recommendation {escalation}."
        )

    parts = [
        f"Priority {priority} assigned with total risk score {score}/100.",
        f"Deterministic financial exposure is ₹{exp_inr:,.2f} ({materiality} materiality, contributing {breakdown.get('financial_exposure_score', 0)}/30 pts).",
        f"Exception severity is {exception.severity} (contributing {breakdown.get('severity_score', 0)}/20 pts).",
    ]

    if root_cause_category:
        parts.append(f"AI diagnostic root-cause category is {root_cause_category}.")

    if breakdown.get("ledger_risk_score", 0) > 0:
        parts.append("Elevated risk due to ledger contradiction and invalid settlement credit.")

    if breakdown.get("allocation_risk_score", 0) > 0:
        parts.append("Elevated risk due to unallocated funds or dual-debit liability.")

    if breakdown.get("sla_score", 0) > 0:
        parts.append("SLA clearance window breached.")

    parts.append(f"Recommended escalation: {escalation}.")
    return " ".join(parts)
