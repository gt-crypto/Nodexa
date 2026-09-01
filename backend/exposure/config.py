"""Configurable thresholds, scoring weights, and versioning for Risk & Materiality engine."""

# Policy and Model Versions
POLICY_VERSION = "v1"
SCORING_VERSION = "v1"
THRESHOLD_VERSION = "v1"

# Materiality Thresholds in integer minor units (paise for INR, 100 paise = 1 INR)
EXPOSURE_NONE: int = 0
EXPOSURE_LOW: int = 100_000         # ₹1,000.00
EXPOSURE_MEDIUM: int = 500_000      # ₹5,000.00
EXPOSURE_HIGH: int = 2_000_000      # ₹20,000.00
EXPOSURE_MATERIAL: int = 5_000_000  # ₹50,000.00
EXPOSURE_SEVERE: int = 10_000_000   # ₹100,000.00

# Scoring Component Maximum Weights (Sum to 100)
FINANCIAL_EXPOSURE_WEIGHT: int = 30
SEVERITY_WEIGHT: int = 20
CONTROL_FAILURE_WEIGHT: int = 15
INVESTIGATION_CONFIDENCE_WEIGHT: int = 10
COMPLEXITY_WEIGHT: int = 5
SLA_WEIGHT: int = 10
LEDGER_RISK_WEIGHT: int = 5
ALLOCATION_RISK_WEIGHT: int = 5

# Priority Score Boundaries (0 - 100)
P1_MIN_SCORE: int = 75  # 75 - 100: Critical priority
P2_MIN_SCORE: int = 50  # 50 - 74: High priority
P3_MIN_SCORE: int = 25  # 25 - 49: Moderate priority
P4_MIN_SCORE: int = 0   # 0 - 24: Low priority
