"""Pytest fixtures for database testing with isolated in-memory and temporary SQLite databases."""
import os
import tempfile

# CRITICAL: Point DATABASE_URL to an isolated test database BEFORE any backend module is imported.
_TEST_DB_PATH = os.path.join(tempfile.gettempdir(), "test_nodal_sentinel_isolated.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB_PATH}"
os.environ["ENVIRONMENT"] = "test"

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

import backend.models.database as db_mod
from backend.models.database import Base


@pytest.fixture(scope="session", autouse=True)
def isolate_test_database():
    """Guarantees that tests never touch nodal_sentinel.db by isolating global engine and SessionLocal."""
    from backend.data.generator.service import generate_dataset
    from backend.exceptions.service import ExceptionDetectionService

    Base.metadata.create_all(bind=db_mod.engine)
    session = db_mod.SessionLocal()
    generate_dataset(session=session, record_count=60, seed=42)
    ExceptionDetectionService().detect_exceptions(session=session)
    session.commit()
    session.close()

    yield db_mod.engine

    db_mod.engine.dispose()
    try:
        if os.path.exists(_TEST_DB_PATH):
            os.remove(_TEST_DB_PATH)
    except Exception:
        pass


@pytest.fixture(scope="function")
def db_engine():
    """Provides an isolated in-memory SQLite engine for testing."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(Engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=test_engine)
    yield test_engine
    Base.metadata.drop_all(bind=test_engine)
    test_engine.dispose()


@pytest.fixture(scope="function")
def db_session(db_engine) -> Session:
    """Provides a transactional database session for each test function."""
    connection = db_engine.connect()
    transaction = connection.begin()
    SessionTest = sessionmaker(bind=connection)
    session = SessionTest()

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def client(db_session: Session):
    """Provides a Starlette TestClient with db_session dependency override."""
    from starlette.testclient import TestClient
    from backend.main import app
    from backend.models.database import get_db

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()
