"""Configuration for synthetic financial dataset generation."""
from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class GeneratorConfig:
    """Configurable parameters for synthetic financial data generation."""
    total_target_records: int = 60
    dataset_version: str = "v0.1.0-synthetic"
    currency: str = "INR"
    
    # Base starting timestamp for deterministic timeline generation
    base_timestamp: datetime = datetime(2026, 8, 1, 9, 0, 0, tzinfo=timezone.utc)
    
    # SLA parameters in hours
    sla_hours: int = 24
    cutoff_hour: int = 18  # 18:00 (6 PM) daily processing cutoff
    
    # Scenario counts
    ghost_settlement_count: int = 2
    refund_chargeback_count: int = 2
    sla_breach_count: int = 2
    partial_settlement_count: int = 2
    missing_settlement_count: int = 2
    unallocated_settlement_count: int = 2
    timing_exception_count: int = 2
