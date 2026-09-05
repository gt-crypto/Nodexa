import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.models import (
    get_db,
    GatewayTransaction,
    MerchantOrder,
    BankSettlementBatch,
    NodalLedgerEntry,
    DisputeRefundEvent,
    ExceptionRecord,
)
from backend.sandbox.service import SandboxValidationService, SandboxAnalysisService, get_sample_sandbox_csv

client = TestClient(app)


def test_sandbox_sample_csv_endpoint():
    response = client.get("/sandbox/sample-csv")
    assert response.status_code == 200
    assert "text/csv" in response.headers.get("content-type", "")
    assert "transaction_id" in response.text
    assert "TXN_" in response.text
    assert "amount" in response.text


def test_sandbox_validate_valid_csv():
    csv_data = get_sample_sandbox_csv()
    files = {"file": ("test_sample.csv", csv_data.encode("utf-8"), "text/csv")}
    response = client.post("/sandbox/validate", files=files)
    assert response.status_code == 200
    res = response.json()
    assert res["is_valid"] is True
    assert res["total_rows"] >= 10
    assert len(res["preview_rows"]) <= 10
    assert len(res["columns_detected"]) >= 5


def test_sandbox_validate_missing_columns():
    bad_csv = "id,name,value\n1,foo,100\n"
    files = {"file": ("bad.csv", bad_csv.encode("utf-8"), "text/csv")}
    response = client.post("/sandbox/validate", files=files)
    assert response.status_code == 200
    res = response.json()
    assert res["is_valid"] is False
    assert len(res["missing_required_columns"]) > 0
    assert any("missing from CSV header" in err["error"] for err in res["errors"])


def test_sandbox_validate_empty_file():
    files = {"file": ("empty.csv", b"", "text/csv")}
    response = client.post("/sandbox/validate", files=files)
    assert response.status_code == 200
    res = response.json()
    assert res["is_valid"] is False
    assert any("empty" in err["error"].lower() for err in res["errors"])


def test_sandbox_analyze_csv_and_database_immutability():
    # 1. Capture production database counts before sandbox run
    db = next(get_db())
    try:
        pre_gw = db.query(GatewayTransaction).count()
        pre_mo = db.query(MerchantOrder).count()
        pre_sb = db.query(BankSettlementBatch).count()
        pre_nl = db.query(NodalLedgerEntry).count()
        pre_dr = db.query(DisputeRefundEvent).count()
        pre_total = pre_gw + pre_mo + pre_sb + pre_nl + pre_dr
        pre_exceptions = db.query(ExceptionRecord).count()
    finally:
        db.close()

    # 2. Run analysis using sample CSV with intentional anomalies
    csv_data = get_sample_sandbox_csv()
    files = {"file": ("sample_anomaly.csv", csv_data.encode("utf-8"), "text/csv")}
    response = client.post("/sandbox/analyze", files=files)
    assert response.status_code == 200
    report = response.json()

    # Verify report structure
    assert report["dataset_summary"]["total_records"] >= 10
    assert report["isolation_mode"] == "EPHEMERAL_IN_MEMORY_SQLITE"
    assert report["production_database_modified"] is False
    assert report["ground_truth_available"] is False
    assert report["ground_truth_status"] == "Not provided"
    assert "unavailable" in report["accuracy_metrics_message"]
    assert isinstance(report["exceptions"], list)
    assert len(report["exceptions"]) > 0
    assert isinstance(report["patterns"], list)

    # Check exception structure
    first_exc = report["exceptions"][0]
    assert "exception_id" in first_exc
    assert "exception_type" in first_exc
    assert "severity" in first_exc
    assert "exposure_minor_units" in first_exc
    assert "recommended_action" in first_exc

    # 3. Verify production database count AFTER sandbox run is 100% UNTOUCHED
    db2 = next(get_db())
    try:
        post_gw = db2.query(GatewayTransaction).count()
        post_mo = db2.query(MerchantOrder).count()
        post_sb = db2.query(BankSettlementBatch).count()
        post_nl = db2.query(NodalLedgerEntry).count()
        post_dr = db2.query(DisputeRefundEvent).count()
        post_total = post_gw + post_mo + post_sb + post_nl + post_dr
        post_exceptions = db2.query(ExceptionRecord).count()

        assert post_gw == pre_gw, "GatewayTransaction table was mutated by sandbox!"
        assert post_mo == pre_mo, "MerchantOrder table was mutated by sandbox!"
        assert post_sb == pre_sb, "BankSettlementBatch table was mutated by sandbox!"
        assert post_nl == pre_nl, "NodalLedgerEntry table was mutated by sandbox!"
        assert post_dr == pre_dr, "DisputeRefundEvent table was mutated by sandbox!"
        assert post_total == pre_total, f"Total records mutated: {pre_total} -> {post_total}"
        assert post_exceptions == pre_exceptions, f"Exceptions table mutated: {pre_exceptions} -> {post_exceptions}"
    finally:
        db2.close()


def test_sandbox_analyze_json_endpoint():
    csv_data = get_sample_sandbox_csv()
    response = client.post("/sandbox/analyze-json", json={"csv_content": csv_data, "dataset_name": "api_test.csv"})
    assert response.status_code == 200
    report = response.json()
    assert report["dataset_summary"]["total_records"] >= 10
    assert report["ground_truth_available"] is False


def test_sandbox_performance_and_timing_instrumentation():
    """Asserts sandbox sub-second execution speed, detailed timing instrumentation, and database immutability."""
    import time
    csv_data = get_sample_sandbox_csv()

    # 0. Capture DB counts before sandbox run
    db_before = next(get_db())
    try:
        pre_gw = db_before.query(GatewayTransaction).count()
        pre_mo = db_before.query(MerchantOrder).count()
        pre_sb = db_before.query(BankSettlementBatch).count()
        pre_nl = db_before.query(NodalLedgerEntry).count()
        pre_dr = db_before.query(DisputeRefundEvent).count()
        pre_exc = db_before.query(ExceptionRecord).count()
    finally:
        db_before.close()

    # 1. Validation timing check
    val_res, valid_rows = SandboxValidationService.validate_csv(csv_data)
    assert val_res.is_valid is True
    assert val_res.validation_time_ms is not None
    assert val_res.validation_time_ms >= 0

    # 2. Performance benchmark: must complete in under 1.5 seconds (warm execution is typically < 150ms)
    t0 = time.perf_counter()
    report = SandboxAnalysisService.analyze_dataset(valid_rows, dataset_name="perf_bench.csv")
    duration_sec = time.perf_counter() - t0

    assert duration_sec < 1.5, f"Sandbox analysis was too slow: {duration_sec:.2f}s (expected < 1.5s)"

    # 3. Timing instrumentation checks
    assert "timing_ms" in report.__dict__
    timing = report.timing_ms
    assert "sqlite_initialization" in timing
    assert "data_insertion" in timing
    assert "deterministic_controls" in timing
    assert "exception_detection" in timing
    assert "pattern_mining" in timing
    assert "report_construction" in timing
    assert "total_analysis_time" in timing
    assert timing["total_analysis_time"] > 0

    # 4. Accuracy & Detection integrity checks
    assert report.exceptions_detected >= 1
    assert any(e.exception_type == "GHOST_SETTLEMENT" for e in report.exceptions)
    assert report.total_exposure_minor_units == 750000
    assert report.production_database_modified is False
    assert report.ground_truth_status == "Not provided"

    # 5. Database immutability check
    db_after = next(get_db())
    try:
        post_gw = db_after.query(GatewayTransaction).count()
        post_mo = db_after.query(MerchantOrder).count()
        post_sb = db_after.query(BankSettlementBatch).count()
        post_nl = db_after.query(NodalLedgerEntry).count()
        post_dr = db_after.query(DisputeRefundEvent).count()
        post_exc = db_after.query(ExceptionRecord).count()
        assert post_gw == pre_gw, "GatewayTransaction table mutated!"
        assert post_mo == pre_mo, "MerchantOrder table mutated!"
        assert post_sb == pre_sb, "BankSettlementBatch table mutated!"
        assert post_nl == pre_nl, "NodalLedgerEntry table mutated!"
        assert post_dr == pre_dr, "DisputeRefundEvent table mutated!"
        assert post_exc == pre_exc, "ExceptionRecord table mutated!"
    finally:
        db_after.close()
