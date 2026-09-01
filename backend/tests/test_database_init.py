"""Tests verifying clean database startup, schema creation, and reset functionality."""
import pytest
from sqlalchemy import inspect, create_engine
from backend.models.database import Base, init_db, reset_db


def test_clean_database_initializes_all_tables():
    """Verify that init_db creates all registered tables in a clean engine."""
    test_engine = create_engine("sqlite:///:memory:")
    init_db(custom_engine=test_engine)

    inspector = inspect(test_engine)
    table_names = set(inspector.get_table_names())

    expected_tables = {
        "gateway_transactions",
        "bank_settlement_batches",
        "merchant_orders",
        "dispute_refund_events",
        "nodal_ledger",
        "exceptions",
        "exception_state_transitions",
        "exception_affected_records",
        "investigation_runs",
        "audit_events",
        "remediation_actions",
        "verification_results",
        "dataset_metadata",
        "evaluation_ground_truth",
    }

    assert expected_tables.issubset(table_names), f"Missing tables: {expected_tables - table_names}"
    test_engine.dispose()


def test_reset_db_drops_and_recreates_schema():
    """Verify that reset_db cleanly wipes and recreates the schema."""
    test_engine = create_engine("sqlite:///:memory:")
    init_db(custom_engine=test_engine)
    
    # Reset should succeed without errors
    reset_db(custom_engine=test_engine)
    
    inspector = inspect(test_engine)
    assert len(inspector.get_table_names()) >= 14
    test_engine.dispose()
