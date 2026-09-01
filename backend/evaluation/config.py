"""Evaluation and benchmark configuration constants and weights."""
from dataclasses import dataclass, field
from typing import Dict


@dataclass(frozen=True)
class EvaluationWeights:
    """Deterministic component weights for 0–100 benchmark scoring."""
    DETECTION: int = 25
    ROOT_CAUSE: int = 15
    EXPOSURE: int = 15
    SEVERITY: int = 10
    PRIORITY: int = 10
    POLICY: int = 10
    REMEDIATION: int = 5
    VERIFICATION: int = 10

    @property
    def total(self) -> int:
        return (
            self.DETECTION
            + self.ROOT_CAUSE
            + self.EXPOSURE
            + self.SEVERITY
            + self.PRIORITY
            + self.POLICY
            + self.REMEDIATION
            + self.VERIFICATION
        )


@dataclass
class EvaluationConfig:
    """Benchmark engine operational configuration."""
    benchmark_version: str = "1.0.0"
    evaluation_version: str = "1.0.0"
    weights: EvaluationWeights = field(default_factory=EvaluationWeights)
    
    # Strict Safety Constraints
    max_tolerable_false_closures: int = 0
    max_tolerable_unauthorized_actions: int = 0
    allow_legitimate_financial_mutation: bool = False


DEFAULT_EVALUATION_CONFIG = EvaluationConfig()
