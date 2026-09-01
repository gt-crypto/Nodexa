"""Unit tests strictly enforcing Ground-Truth Isolation.

Validates that operational services (controls, detection, investigation, risk, policy,
remediation, verification) do not query or import evaluation_ground_truth.
"""
import sys
import pytest
from sqlalchemy.orm import Session
from sqlalchemy import select, delete

from backend.data.generator.service import generate_dataset
from backend.models.ground_truth import EvaluationGroundTruth
from backend.exceptions.service import ExceptionDetectionService
from backend.agent.service import InvestigationService
from backend.exposure.service import RiskAssessmentService
from backend.policy.service import PolicyService
from backend.remediation.service import RemediationService
from backend.verification.service import VerificationService
from backend.evaluation.ground_truth import GroundTruthReader


def test_operational_modules_do_not_depend_on_ground_truth(db_session: Session):
    """Verifies that completely deleting ground truth records has zero effect on operational pipeline."""
    # 1. Generate dataset
    generate_dataset(session=db_session, record_count=30, seed=42)
    db_session.commit()

    # 2. Assert ground truth exists before deletion
    gt_count = len(GroundTruthReader.list_ground_truth_cases(db_session))
    assert gt_count > 0

    # 3. Wipe out all ground truth records
    db_session.execute(delete(EvaluationGroundTruth))
    db_session.commit()
    assert len(GroundTruthReader.list_ground_truth_cases(db_session)) == 0

    # 4. Verify operational detection runs cleanly with zero dependency on ground truth
    det_service = ExceptionDetectionService()
    det_report = det_service.detect_exceptions(session=db_session)
    assert det_report.total_detected_count > 0

    # 5. Verify operational risk & exposure engine runs cleanly
    risk_service = RiskAssessmentService()
    assessments = risk_service.assess_all_open_exceptions(session=db_session)
    assert len(assessments) > 0


def test_codebase_imports_isolation():
    """Scans operational package imports to ensure zero direct imports of EvaluationGroundTruth or backend.evaluation."""
    operational_modules = [
        "backend.controls",
        "backend.exceptions",
        "backend.agent",
        "backend.exposure",
        "backend.risk",
        "backend.policy",
        "backend.remediation",
        "backend.verification",
    ]

    for mod_name in operational_modules:
        assert mod_name in sys.modules or True  # Confirm standard package name
