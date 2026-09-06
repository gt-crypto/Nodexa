"""File ingestion and multi-format parsing for Sandbox dataset intelligence.

Supports:
- CSV (with delimiter sniffing: comma, semicolon, tab)
- XLSX (via openpyxl, read-only mode)
- JSON (flat array of records or wrapped { "data": [...] } / { "records": [...] })
- Safe byte & row bounding (5 MB, 10,000 rows max)
"""
import csv
import io
import json
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5 MB
MAX_PARSED_ROWS = 10000


class ParsedDataset(BaseModel):
    """Normalized output from raw file parsing."""
    file_format: str  # "CSV", "XLSX", "JSON"
    headers: List[str] = Field(default_factory=list)
    raw_rows: List[Dict[str, Any]] = Field(default_factory=list)
    total_raw_rows: int = 0
    parsing_errors: List[str] = Field(default_factory=list)
    truncated: bool = False


def detect_file_format(content_bytes: bytes, filename: Optional[str] = None) -> str:
    """Detects whether content is XLSX, JSON, or CSV based on filename and magic bytes."""
    fname_lower = (filename or "").lower()
    if fname_lower.endswith(".xlsx"):
        return "XLSX"
    if fname_lower.endswith(".json"):
        return "JSON"
    if fname_lower.endswith(".csv"):
        return "CSV"

    # Magic byte inspection
    if content_bytes.startswith(b"PK\x03\x04"):
        return "XLSX"

    stripped = content_bytes.strip()
    if stripped.startswith(b"{") or stripped.startswith(b"["):
        return "JSON"

    return "CSV"


def parse_csv_content(content_str: str) -> ParsedDataset:
    """Parses CSV text using delimiter sniffing and DictReader."""
    if not content_str.strip():
        return ParsedDataset(file_format="CSV", parsing_errors=["CSV content is empty."])

    # Sample for delimiter sniffing
    sample = content_str[:4096]
    delimiter = ","
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=[",", ";", "\t", "|"])
        delimiter = dialect.delimiter
    except Exception:
        # Fallback to comma if sniffing is ambiguous
        if ";" in sample and sample.count(";") > sample.count(","):
            delimiter = ";"
        elif "\t" in sample and sample.count("\t") > sample.count(","):
            delimiter = "\t"
        else:
            delimiter = ","

    reader = csv.DictReader(io.StringIO(content_str), delimiter=delimiter)
    if not reader.fieldnames:
        return ParsedDataset(
            file_format="CSV",
            parsing_errors=["CSV header row is missing or empty."],
        )

    headers = [col.strip() for col in reader.fieldnames if col is not None and col.strip()]
    raw_rows: List[Dict[str, Any]] = []
    total_rows = 0
    truncated = False

    for row in reader:
        total_rows += 1
        if len(raw_rows) >= MAX_PARSED_ROWS:
            truncated = True
            continue
        cleaned_row = {
            k.strip(): (v.strip() if isinstance(v, str) else v)
            for k, v in row.items()
            if k is not None and k.strip()
        }
        raw_rows.append(cleaned_row)

    return ParsedDataset(
        file_format="CSV",
        headers=headers,
        raw_rows=raw_rows,
        total_raw_rows=total_rows,
        truncated=truncated,
    )


def parse_xlsx_content(content_bytes: bytes) -> ParsedDataset:
    """Parses Excel XLSX content using openpyxl in read-only mode."""
    try:
        import openpyxl
    except ImportError:
        return ParsedDataset(
            file_format="XLSX",
            parsing_errors=["openpyxl library is required to parse XLSX files."],
        )

    try:
        wb = openpyxl.load_workbook(io.BytesIO(content_bytes), read_only=True, data_only=True)
        sheet = wb.active
        if sheet is None:
            return ParsedDataset(
                file_format="XLSX",
                parsing_errors=["Workbook contains no active worksheet."],
            )

        headers: List[str] = []
        raw_rows: List[Dict[str, Any]] = []
        total_rows = 0
        truncated = False

        for row_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            if row_idx == 1:
                # Header row
                headers = [str(val).strip() for val in row if val is not None and str(val).strip()]
                if not headers:
                    return ParsedDataset(
                        file_format="XLSX",
                        parsing_errors=["Excel worksheet header row is empty."],
                    )
                continue

            # Skip entirely empty rows
            if not any(val is not None and str(val).strip() for val in row):
                continue

            total_rows += 1
            if len(raw_rows) >= MAX_PARSED_ROWS:
                truncated = True
                continue

            row_dict = {}
            for col_idx, h in enumerate(headers):
                val = row[col_idx] if col_idx < len(row) else None
                row_dict[h] = val
            raw_rows.append(row_dict)

        wb.close()
        return ParsedDataset(
            file_format="XLSX",
            headers=headers,
            raw_rows=raw_rows,
            total_raw_rows=total_rows,
            truncated=truncated,
        )
    except Exception as exc:
        return ParsedDataset(
            file_format="XLSX",
            parsing_errors=[f"Failed to parse Excel file: {str(exc)}"],
        )


def parse_json_content(content_str: str) -> ParsedDataset:
    """Parses JSON content (flat list of dicts, or wrapped in an object)."""
    try:
        data = json.loads(content_str)
    except Exception as exc:
        return ParsedDataset(
            file_format="JSON",
            parsing_errors=[f"Invalid JSON syntax: {str(exc)}"],
        )

    records: List[Dict[str, Any]] = []
    if isinstance(data, list):
        records = [r for r in data if isinstance(r, dict)]
    elif isinstance(data, dict):
        for key in ("data", "records", "transactions", "items", "rows", "events"):
            if key in data and isinstance(data[key], list):
                records = [r for r in data[key] if isinstance(r, dict)]
                break
        if not records and data:
            # Maybe single record or key-value
            records = [data]

    if not records:
        return ParsedDataset(
            file_format="JSON",
            parsing_errors=["JSON data does not contain a list of structured records."],
        )

    # Collect distinct headers preserving appearance order
    headers_dict: Dict[str, bool] = {}
    for r in records:
        for k in r.keys():
            if isinstance(k, str) and k.strip():
                headers_dict[k.strip()] = True
    headers = list(headers_dict.keys())

    total_rows = len(records)
    truncated = total_rows > MAX_PARSED_ROWS
    raw_rows = records[:MAX_PARSED_ROWS]

    return ParsedDataset(
        file_format="JSON",
        headers=headers,
        raw_rows=raw_rows,
        total_raw_rows=total_rows,
        truncated=truncated,
    )


def parse_uploaded_dataset(
    content_bytes: bytes,
    filename: Optional[str] = None,
) -> ParsedDataset:
    """Unified entrypoint to parse an uploaded file or content bytes into a ParsedDataset."""
    if not content_bytes or not content_bytes.strip():
        return ParsedDataset(
            file_format="CSV",
            parsing_errors=["Uploaded file is empty (0 bytes)."],
        )

    if len(content_bytes) > MAX_UPLOAD_BYTES:
        return ParsedDataset(
            file_format="UNKNOWN",
            parsing_errors=[
                f"File size exceeds 5 MB limit ({round(len(content_bytes) / (1024 * 1024), 2)} MB)"
            ],
        )

    detected_format = detect_file_format(content_bytes, filename)

    if detected_format == "XLSX":
        return parse_xlsx_content(content_bytes)

    # Text-based decoding for CSV and JSON
    text_content = ""
    for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            text_content = content_bytes.decode(enc)
            break
        except UnicodeDecodeError:
            continue

    if not text_content:
        return ParsedDataset(
            file_format=detected_format,
            parsing_errors=["File encoding could not be decoded. Please use UTF-8 or ASCII."],
        )

    if detected_format == "JSON":
        return parse_json_content(text_content)
    else:
        return parse_csv_content(text_content)
