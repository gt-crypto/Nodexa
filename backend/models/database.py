"""Centralized database configuration and session management for Nodexa."""
import os
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

load_dotenv()

# Database URL from environment or default to SQLite local file
DEFAULT_DATABASE_URL = "sqlite:///./nodal_sentinel.db"
raw_db_url = (
    os.getenv("DATABASE_URL")
    or os.getenv("INTERNAL_DATABASE_URL")
    or os.getenv("POSTGRES_URL")
    or DEFAULT_DATABASE_URL
)

# Normalize postgres:// to postgresql:// for SQLAlchemy 2.0 compatibility
if raw_db_url.startswith("postgres://"):
    DATABASE_URL = raw_db_url.replace("postgres://", "postgresql://", 1)
else:
    DATABASE_URL = raw_db_url

# Engine configuration with production pooling for PostgreSQL
engine_kwargs = {
    "echo": os.getenv("SQL_ECHO", "false").lower() == "true",
}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    # Production PostgreSQL pool configuration optimized for Render
    engine_kwargs["pool_pre_ping"] = True
    engine_kwargs["pool_size"] = int(os.getenv("DB_POOL_SIZE", "5"))
    engine_kwargs["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "5"))
    engine_kwargs["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", "300"))
    engine_kwargs["pool_timeout"] = int(os.getenv("DB_POOL_TIMEOUT", "10"))

engine = create_engine(DATABASE_URL, **engine_kwargs)


# Enforce foreign key constraints in SQLite
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Ensure SQLite enforces foreign key constraints on all connections."""
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Incremental migrations: list of (column_name, full_DDL_fragment) per table.
# Applied across both SQLite and PostgreSQL to ensure zero missing column errors.
_COLUMN_MIGRATIONS: dict = {
    "exceptions": [
        ("source_flag", "source_flag VARCHAR(32) NOT NULL DEFAULT 'seeded'"),
    ],
    "exception_clusters": [
        ("seeded_count", "seeded_count INTEGER NOT NULL DEFAULT 0"),
        ("live_injected_count", "live_injected_count INTEGER NOT NULL DEFAULT 0"),
        ("evidence", "evidence TEXT NOT NULL DEFAULT '{}'"),
    ],
    "evaluation_runs": [
        ("safety_score", "safety_score INTEGER NOT NULL DEFAULT 0"),
    ],
    "audit_events": [
        ("investigation_id", "investigation_id VARCHAR(64)"),
        ("actor_id", "actor_id VARCHAR(64)"),
        ("previous_event_hash", "previous_event_hash VARCHAR(64)"),
        ("event_hash", "event_hash VARCHAR(64)"),
    ],
}


_TYPE_MIGRATIONS: list = [
    ("evaluation_ground_truth", "expected_root_cause", "VARCHAR(512)", 512),
    ("evaluation_ground_truth", "expected_resolution_class", "VARCHAR(128)", 128),
    ("evaluation_ground_truth", "expected_verification_state", "VARCHAR(128)", 128),
    ("evaluation_cases", "expected_root_cause", "VARCHAR(512)", 512),
    ("evaluation_cases", "predicted_root_cause", "VARCHAR(512)", 512),
    ("evaluation_cases", "expected_resolution_class", "VARCHAR(128)", 128),
    ("evaluation_cases", "predicted_resolution_class", "VARCHAR(128)", 128),
    ("investigation_runs", "recommended_action", "VARCHAR(512)", 512),
    ("investigation_runs", "final_classification", "VARCHAR(128)", 128),
]


def init_db(custom_engine=None) -> None:
    """Create all registered database tables and apply incremental schema migrations."""
    import backend.models

    target_engine = custom_engine or engine

    # 1. Create any newly registered tables
    Base.metadata.create_all(bind=target_engine)

    # 2. Universal incremental column migrations for both SQLite and PostgreSQL
    is_sqlite = str(target_engine.url).startswith("sqlite")
    try:
        inspector = inspect(target_engine)
        for table_name, columns in _COLUMN_MIGRATIONS.items():
            try:
                existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
            except Exception:
                continue  # table doesn't exist yet; create_all will handle it
            for col_name, col_ddl in columns:
                if col_name not in existing_cols:
                    try:
                        with target_engine.begin() as conn:
                            if is_sqlite:
                                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_ddl}"))
                            else:
                                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS {col_ddl}"))
                    except Exception:
                        pass

        # 3. Column type widening migrations for PostgreSQL (only if not already widened)
        if not is_sqlite:
            # Group all required alters into a single transaction to eliminate network round-trips
            table_col_map = {}
            for table_name, col_name, new_type, min_len in _TYPE_MIGRATIONS:
                try:
                    if table_name not in table_col_map:
                        table_col_map[table_name] = {
                            c["name"]: getattr(c["type"], "length", 0) or 0
                            for c in inspector.get_columns(table_name)
                        }
                    curr_len = table_col_map[table_name].get(col_name, 0)
                    # If column already has sufficient width, skip ALTER TABLE entirely
                    if curr_len < min_len:
                        with target_engine.begin() as conn:
                            conn.execute(text(f"ALTER TABLE {table_name} ALTER COLUMN {col_name} TYPE {new_type}"))
                except Exception:
                    pass
    except Exception:
        pass


def reset_db(custom_engine=None) -> None:
    """Drop all tables and recreate clean schema."""
    target_engine = custom_engine or engine
    Base.metadata.drop_all(bind=target_engine)
    init_db(custom_engine=target_engine)
