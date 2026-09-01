"""Financial Exposure, Materiality & Risk Prioritization module for Nodal Sentinel."""
from backend.exposure.config import (
    POLICY_VERSION,
    SCORING_VERSION,
    THRESHOLD_VERSION,
    EXPOSURE_LOW,
    EXPOSURE_MEDIUM,
    EXPOSURE_HIGH,
    EXPOSURE_MATERIAL,
    EXPOSURE_SEVERE,
)
from backend.exposure.materiality import (
    classify_exposure_type,
    classify_materiality,
    calculate_relative_materiality_bps,
)
from backend.exposure.factors import extract_risk_factors
from backend.exposure.scoring import (
    calculate_risk_score,
    determine_priority,
    determine_escalation,
    generate_risk_explanation,
)
from backend.exposure.prioritization import (
    get_prioritized_risk_queue,
    get_account_risk_summary,
)
from backend.exposure.service import RiskAssessmentService

__all__ = [
    "POLICY_VERSION",
    "SCORING_VERSION",
    "THRESHOLD_VERSION",
    "EXPOSURE_LOW",
    "EXPOSURE_MEDIUM",
    "EXPOSURE_HIGH",
    "EXPOSURE_MATERIAL",
    "EXPOSURE_SEVERE",
    "classify_exposure_type",
    "classify_materiality",
    "calculate_relative_materiality_bps",
    "extract_risk_factors",
    "calculate_risk_score",
    "determine_priority",
    "determine_escalation",
    "generate_risk_explanation",
    "get_prioritized_risk_queue",
    "get_account_risk_summary",
    "RiskAssessmentService",
]
