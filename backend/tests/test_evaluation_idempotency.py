"""Unit tests for evaluation idempotency and cache management."""
from datetime import datetime, timezone
import pytest
from sqlalchemy.orm import Session

from backend.data.generator.service import generate_dataset
from backend.exceptions.service import ExceptionDetectionService
from backend.evaluation.service import BenchmarkEvaluationService
from backend.evaluation.models import EvaluationRunRequest


def test_evaluation_idempotency_and_force_rerun(db_session: Session):
    """Verifies that evaluation is deterministic and force_rerun controls caching behavior."""
    # 1. Generate dataset and detect exceptions
    summary = generate_dataset(session=db_session, record_count=30, seed=42)
    db_session.commit()
    dataset_id = summary["dataset_id"]

    det_service = ExceptionDetectionService()
    det_service.detect_exceptions(session=db_session)
    db_session.commit()

    eval_service = BenchmarkEvaluationService()

    # 2. First evaluation run
    req1 = EvaluationRunRequest(dataset_id=dataset_id, force_rerun=False)
    res1 = eval_service.run_benchmark(session=db_session, request=req1)
    run_id_1 = res1.run.evaluation_run_id

    # 3. Second run without force_rerun -> should return cached run
    req2 = EvaluationRunRequest(dataset_id=dataset_id, force_rerun=False)
    res2 = eval_service.run_benchmark(session=db_session, request=req2)
    assert res2.run.evaluation_run_id == run_id_1
    assert res2.run.overall_score == res1.run.overall_score

    # 4. Third run with force_rerun=True -> creates new run
    req3 = EvaluationRunRequest(dataset_id=dataset_id, force_rerun=True)
    res3 = eval_service.run_benchmark(session=db_session, request=req3)
    assert res3.run.evaluation_run_id != run_id_1
    assert res3.run.overall_score == res1.run.overall_score
