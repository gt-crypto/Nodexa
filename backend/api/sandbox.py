"""FastAPI router for the Sandbox 'Test New Dataset' feature."""
from typing import Optional
from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status
from pydantic import BaseModel
from fastapi.responses import PlainTextResponse

from backend.sandbox.models import SandboxValidationResult, SandboxAnalysisReport
from backend.sandbox.service import (
    SandboxValidationService,
    SandboxAnalysisService,
    get_sample_sandbox_csv,
    MAX_UPLOAD_BYTES,
)
from backend.logging import logger

router = APIRouter(prefix="/sandbox", tags=["Sandbox Analysis"])


class AnalyzeJsonRequest(BaseModel):
    csv_content: str
    dataset_name: Optional[str] = "sandbox_dataset.csv"


@router.post("/validate", response_model=SandboxValidationResult)
async def validate_sandbox_dataset(
    file: Optional[UploadFile] = File(None),
    csv_content: Optional[str] = Form(None),
) -> SandboxValidationResult:
    """Validates an uploaded CSV dataset against the standard Nodexa operational schema.
    
    Accepts multipart/form-data with a file or raw form string.
    Does NOT mutate any database records.
    """
    raw_text = ""
    if file:
        content_bytes = await file.read()
        if len(content_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of 5 MB ({round(len(content_bytes) / (1024 * 1024), 2)} MB)",
            )
        try:
            raw_text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                raw_text = content_bytes.decode("latin-1")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid file encoding. CSV must be UTF-8 or ASCII encoded.",
                )
    elif csv_content:
        raw_text = csv_content
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No CSV file or csv_content provided for validation.",
        )

    result, _ = SandboxValidationService.validate_csv(raw_text)
    logger.info(
        operation="SANDBOX_VALIDATION",
        message=f"Sandbox dataset validated: valid={result.is_valid}, rows={result.total_rows}, valid_rows={result.valid_rows}",
        details={
            "total_rows": result.total_rows,
            "valid_rows": result.valid_rows,
            "invalid_rows": result.invalid_rows,
            "is_valid": result.is_valid,
        },
    )
    return result


@router.post("/analyze", response_model=SandboxAnalysisReport)
async def analyze_sandbox_dataset(
    file: Optional[UploadFile] = File(None),
    csv_content: Optional[str] = Form(None),
    dataset_name: Optional[str] = Form("sandbox_dataset.csv"),
) -> SandboxAnalysisReport:
    """Executes deterministic finance-control detection and pattern mining on the uploaded dataset.
    
    Operates 100% inside an isolated in-memory SQLite sandbox database.
    Does NOT mutate, insert, or delete any records in production PostgreSQL or SQLite.
    """
    raw_text = ""
    actual_name = dataset_name or "sandbox_dataset.csv"

    if file:
        actual_name = file.filename or actual_name
        content_bytes = await file.read()
        if len(content_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds maximum allowed size of 5 MB ({round(len(content_bytes) / (1024 * 1024), 2)} MB)",
            )
        try:
            raw_text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            try:
                raw_text = content_bytes.decode("latin-1")
            except Exception:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid file encoding. CSV must be UTF-8 or ASCII encoded.",
                )
    elif csv_content:
        raw_text = csv_content
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No CSV file or csv_content provided for analysis.",
        )

    # 1. Validate
    val_result, valid_rows = SandboxValidationService.validate_csv(raw_text)
    if not val_result.is_valid or not valid_rows:
        error_sample = "; ".join([e.error for e in val_result.errors[:3]])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Dataset validation failed ({val_result.invalid_rows} invalid rows): {error_sample or val_result.message}",
        )

    # 2. Run isolated sandbox analysis
    report = SandboxAnalysisService.analyze_dataset(valid_rows=valid_rows, dataset_name=actual_name)
    logger.info(
        operation="SANDBOX_ANALYSIS_COMPLETE",
        message=f"Sandbox analysis complete: {report.exceptions_detected} exceptions, exposure={report.total_exposure_minor_units}",
        details={
            "dataset_name": actual_name,
            "records": report.dataset_summary.total_records,
            "exceptions": report.exceptions_detected,
            "patterns": report.recurring_patterns_count,
            "exposure_paise": report.total_exposure_minor_units,
        },
    )
    return report


@router.post("/analyze-json", response_model=SandboxAnalysisReport)
async def analyze_sandbox_dataset_json(payload: AnalyzeJsonRequest) -> SandboxAnalysisReport:
    """Alternative JSON endpoint for analyzing CSV text content."""
    val_result, valid_rows = SandboxValidationService.validate_csv(payload.csv_content)
    if not val_result.is_valid or not valid_rows:
        error_sample = "; ".join([e.error for e in val_result.errors[:3]])
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Dataset validation failed: {error_sample or val_result.message}",
        )
    return SandboxAnalysisService.analyze_dataset(valid_rows=valid_rows, dataset_name=payload.dataset_name or "sandbox_dataset.csv")


@router.get("/sample-csv", response_class=PlainTextResponse)
def get_sample_csv():
    """Returns a canonical sample CSV dataset containing representative anomalies for sandbox testing."""
    csv_text = get_sample_sandbox_csv()
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=nodexa_sample_anomaly_dataset.csv"},
    )
