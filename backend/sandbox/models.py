"""Data models and schemas for the Sandbox 'Test New Dataset' feature."""
from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SandboxValidationIssue(BaseModel):
    """Validation issue found on a specific row."""
    row_number: int = Field(..., description="1-indexed row number in the CSV")
    field: str = Field(..., description="Column name with the issue")
    error: str = Field(..., description="Description of the validation failure")
    raw_value: Optional[str] = Field(None, description="The raw offending value")


class SandboxValidationResult(BaseModel):
    """Output summary of CSV dataset validation."""
    is_valid: bool = Field(..., description="Whether dataset is valid for sandbox analysis")
    total_rows: int = Field(..., description="Total rows in the uploaded CSV")
    valid_rows: int = Field(..., description="Number of valid, parseable operational rows")
    invalid_rows: int = Field(..., description="Number of invalid rows")
    columns_detected: List[str] = Field(default_factory=list, description="Columns found in CSV header")
    missing_required_columns: List[str] = Field(default_factory=list, description="Required columns missing from header")
    errors: List[SandboxValidationIssue] = Field(default_factory=list, description="List of row-level validation issues (capped at 50)")
    preview_rows: List[Dict[str, Any]] = Field(default_factory=list, description="Preview of the first 10 rows")
    message: str = Field(..., description="Human-readable validation summary")


class SandboxExceptionItem(BaseModel):
    """Individual exception discovered in the sandbox dataset."""
    exception_id: str
    exception_type: str
    severity: str
    exposure_minor_units: int
    exposure_inr_formatted: str
    primary_payment_id: Optional[str]
    primary_order_id: Optional[str]
    description: Optional[str]
    is_legitimate_observation: bool = False
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    recommended_action: str = Field(default="Review and investigate discrepancy", description="Recommended action (analysis only, never auto-executed)")


class SandboxPatternItem(BaseModel):
    """Recurring pattern cluster discovered in the sandbox dataset."""
    cluster_id: str
    pattern_type: str
    exception_count: int
    total_exposure_minor_units: int
    total_exposure_inr_formatted: str
    signature: Dict[str, Any]
    description: str


class SandboxDatasetSummary(BaseModel):
    """Operational volume summary of the analyzed sandbox dataset."""
    total_records: int
    gateway_transactions: int
    merchant_orders: int
    settlement_batches: int
    dispute_events: int
    ledger_entries: int
    merchants_impacted: int


class SandboxAnalysisReport(BaseModel):
    """Full deterministic analysis report produced by the sandbox finance controller."""
    status: str = "COMPLETED"
    dataset_name: str = "sandbox_dataset.csv"
    evaluated_at: str
    isolation_mode: str = "EPHEMERAL_IN_MEMORY_SQLITE"
    production_database_modified: bool = False

    # Operational metrics
    dataset_summary: SandboxDatasetSummary
    exceptions_detected: int
    high_risk_cases: int
    total_exposure_minor_units: int
    total_exposure_inr_formatted: str
    recurring_patterns_count: int

    # Honest Ground Truth reporting
    ground_truth_available: bool = False
    ground_truth_status: str = "Not provided"
    accuracy_metrics_message: str = "Accuracy metrics (Precision/Recall/F1) unavailable for this dataset because external ground-truth labels were not supplied."

    # Detailed findings
    exceptions: List[SandboxExceptionItem] = Field(default_factory=list)
    patterns: List[SandboxPatternItem] = Field(default_factory=list)

    # Disclaimers
    disclaimer: str = (
        "Sandbox analysis is completely isolated from production. No production records were modified. "
        "All recommended actions are advisory only and zero automated remediation was triggered."
    )
