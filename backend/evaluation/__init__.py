"""Evaluation package exports."""
from backend.evaluation.config import EvaluationConfig, DEFAULT_EVALUATION_CONFIG, EvaluationWeights
from backend.evaluation.ground_truth import GroundTruthReader
from backend.evaluation.matcher import DeterministicMatcher, CaseMatchResult
from backend.evaluation.detection_metrics import DetectionMetricsCalculator
from backend.evaluation.exposure_metrics import ExposureMetricsCalculator
from backend.evaluation.investigation_metrics import InvestigationMetricsCalculator
from backend.evaluation.risk_metrics import RiskMetricsCalculator
from backend.evaluation.policy_metrics import PolicyMetricsCalculator
from backend.evaluation.remediation_metrics import RemediationMetricsCalculator
from backend.evaluation.verification_metrics import VerificationMetricsCalculator
from backend.evaluation.scorer import BenchmarkScorer
from backend.evaluation.report import EvaluationReportBuilder
from backend.evaluation.service import BenchmarkEvaluationService
from backend.evaluation.models import (
    EvaluationRunRequest,
    EvaluationRunResponse,
    EvaluationCaseResponse,
    EvaluationReportSummary,
)

__all__ = [
    "EvaluationConfig",
    "DEFAULT_EVALUATION_CONFIG",
    "EvaluationWeights",
    "GroundTruthReader",
    "DeterministicMatcher",
    "CaseMatchResult",
    "DetectionMetricsCalculator",
    "ExposureMetricsCalculator",
    "InvestigationMetricsCalculator",
    "RiskMetricsCalculator",
    "PolicyMetricsCalculator",
    "RemediationMetricsCalculator",
    "VerificationMetricsCalculator",
    "BenchmarkScorer",
    "EvaluationReportBuilder",
    "BenchmarkEvaluationService",
    "EvaluationRunRequest",
    "EvaluationRunResponse",
    "EvaluationCaseResponse",
    "EvaluationReportSummary",
]
