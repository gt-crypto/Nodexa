"""Dataset generation API endpoint for testing and local simulation."""
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.models.database import get_db
from backend.data.generator.service import generate_dataset

router = APIRouter(prefix="/data", tags=["Synthetic Data"])


class GenerateDatasetRequest(BaseModel):
    record_count: int = Field(default=60, ge=10, le=10000, description="Total target financial records")
    seed: int = Field(default=42, description="Deterministic PRNG seed")


class GenerateDatasetResponse(BaseModel):
    status: str = "success"
    dataset_id: str
    dataset_version: str
    seed: int
    total_financial_records: int
    counts: Dict[str, int]
    scenario_breakdown: Dict[str, Any]


@router.post("/generate", response_model=GenerateDatasetResponse)
def post_generate_dataset(
    req: GenerateDatasetRequest = GenerateDatasetRequest(),
    db: Session = Depends(get_db),
) -> GenerateDatasetResponse:
    """Deterministically generates a synthetic financial dataset with planted anomaly scenarios."""
    result = generate_dataset(session=db, record_count=req.record_count, seed=req.seed)
    db.commit()
    return GenerateDatasetResponse(
        dataset_id=result["dataset_id"],
        dataset_version=result["dataset_version"],
        seed=result["seed"],
        total_financial_records=result["total_financial_records"],
        counts=result["counts"],
        scenario_breakdown=result["scenario_breakdown"],
    )
