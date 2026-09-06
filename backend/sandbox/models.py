from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FieldMappingItem(BaseModel):
    """Semantic mapping from an uploaded raw column header to a canonical financial concept."""
    canonical_field: str = Field(..., description="Canonical concept name (e.g., transaction_id, amount, status)")
    source_column: str = Field(..., description="The original column name in the uploaded file")
    confidence: str = Field(..., description="Mapping confidence: HIGH, MEDIUM, or LOW")
    sample_values: List[str] = Field(default_factory=list, description="Up to 3 sample normalized values")
    rationale: str = Field(..., description="Reasoning for the inferred mapping")


class CapabilityItem(BaseModel):
    """A financial analysis capability that Nodexa can or cannot perform on the dataset."""
    capability_id: str = Field(..., description="Unique identifier for the capability")
    name: str = Field(..., description="Human-readable capability name")
    available: bool = Field(..., description="Whether this capability can be reliably executed")
    required_fields: List[str] = Field(default_factory=list, description="Canonical fields required for this capability")
    missing_fields: List[str] = Field(default_factory=list, description="Required fields that are absent in this dataset")
    reason: str = Field(..., description="Explanation of why this capability is or is not available")


class MerchantVolumeItem(BaseModel):
    merchant_id: str
    volume_minor_units: int
    volume_inr_formatted: str
    transaction_count: int


class FinancialAnalytics(BaseModel):
    """Computed deterministic financial analytics across the canonical rows."""
    total_volume_minor_units: int = 0
    total_volume_inr_formatted: str = "₹0.00"
    average_amount_minor_units: Optional[int] = None
    average_amount_inr_formatted: Optional[str] = None
    largest_amount_minor_units: Optional[int] = None
    largest_amount_inr_formatted: Optional[str] = None
    smallest_amount_minor_units: Optional[int] = None
    smallest_amount_inr_formatted: Optional[str] = None
    status_breakdown: Dict[str, int] = Field(default_factory=dict)
    settlement_reconciled_count: int = 0
    settlement_discrepancy_count: int = 0
    settlement_total_deficit_minor_units: int = 0
    settlement_total_deficit_inr_formatted: str = "₹0.00"
    refund_total_minor_units: int = 0
    refund_total_inr_formatted: str = "₹0.00"
    top_merchants_by_volume: List[MerchantVolumeItem] = Field(default_factory=list)
    sample_size_notice: Optional[str] = None
    unavailable_capabilities_disclaimer: List[str] = Field(default_factory=list)
    unavailable_capabilities: List[str] = Field(default_factory=list)


class DatasetProfile(BaseModel):
    """Semantic dataset profile produced before execution."""
    file_format: str = Field(..., description="Detected format: CSV, XLSX, or JSON")
    row_count: int = Field(..., description="Number of data rows parsed")
    raw_columns: List[str] = Field(default_factory=list, description="Original columns found in dataset")
    mapped_fields: List[FieldMappingItem] = Field(default_factory=list, description="Discovered semantic mappings")
    unmapped_columns: List[str] = Field(default_factory=list, description="Columns that did not match canonical concepts")
    capabilities: List[CapabilityItem] = Field(default_factory=list, description="Capability breakdown")
    profiling_notes: List[str] = Field(default_factory=list, description="Notes on data cleanliness, sample size, etc.")


class SandboxValidationIssue(BaseModel):
    """Validation issue found on a specific row."""
    row_number: int = Field(..., description="1-indexed row number in the dataset")
    field: str = Field(..., description="Column name with the issue")
    error: str = Field(..., description="Description of the validation failure")
    raw_value: Optional[str] = Field(None, description="The raw offending value")


class SandboxValidationResult(BaseModel):
    """Output summary of dataset validation and semantic profiling."""
    is_valid: bool = Field(..., description="Whether dataset is valid for sandbox analysis")
    total_rows: int = Field(..., description="Total rows in the uploaded file")
    valid_rows: int = Field(..., description="Number of valid, parseable operational rows")
    invalid_rows: int = Field(..., description="Number of invalid rows")
    columns_detected: List[str] = Field(default_factory=list, description="Columns found in dataset header")
    missing_required_columns: List[str] = Field(default_factory=list, description="Required columns missing from header")
    errors: List[SandboxValidationIssue] = Field(default_factory=list, description="List of row-level validation issues (capped at 50)")
    preview_rows: List[Dict[str, Any]] = Field(default_factory=list, description="Preview of the first 10 rows")
    message: str = Field(..., description="Human-readable validation summary")
    validation_time_ms: Optional[float] = Field(default=None, description="Validation duration in milliseconds")

    # Generalized intelligence extensions
    profile: Optional[DatasetProfile] = Field(default=None, description="Semantic dataset profile and mapping breakdown")
    capabilities: List[CapabilityItem] = Field(default_factory=list, description="Available and unavailable capabilities")


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

    # Generalized Intelligence extensions
    profile: Optional[DatasetProfile] = Field(default=None, description="Dataset profile and column mapping info")
    capabilities: List[CapabilityItem] = Field(default_factory=list, description="Capabilities evaluated")
    analytics: Optional[FinancialAnalytics] = Field(default=None, description="Deterministic financial metrics")

    # Timing instrumentation
    timing_ms: Dict[str, float] = Field(
        default_factory=dict,
        description="Detailed execution timing breakdown in milliseconds",
    )

    # Disclaimers
    disclaimer: str = (
        "Sandbox analysis is completely isolated from production. No production records were modified. "
        "All recommended actions are advisory only and zero automated remediation was triggered."
    )


class SandboxQueryRequest(BaseModel):
    """Request to ask a grounded question about an analyzed or uploaded dataset."""
    query: str = Field(..., description="Natural language question about the dataset")
    dataset_name: Optional[str] = Field("sandbox_dataset.csv", description="Name of the dataset")
    raw_content: Optional[str] = Field(None, description="Raw CSV/JSON string if querying on-the-fly")
    report: Optional[SandboxAnalysisReport] = Field(None, description="Pre-computed report context if available")


class SandboxQueryResponse(BaseModel):
    """Response answering a question grounded strictly on the uploaded dataset."""
    query: str
    answer: str
    grounded_data: Dict[str, Any] = Field(default_factory=dict)
    confidence: str = "HIGH"
    capabilities_used: List[str] = Field(default_factory=list)
    disclaimer: str = "Grounded strictly on the ephemeral uploaded dataset. Zero production data accessed."

