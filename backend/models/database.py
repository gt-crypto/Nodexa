"""Centralized database configuration and session management for Nodal Sentinel."""
import os
from typing import Generator
from dotenv import load_dotenv
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session

load_dotenv()

# Database URL from environment or default to SQLite local file
DEFAULT_DATABASE_URL = "sqlite:///./nodal_sentinel.db"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

# SQLite-specific connect args
connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    echo=os.getenv("SQL_ECHO", "false").lower() == "true",
)


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


def init_db(custom_engine=None) -> None:
    """Create all registered database tables and apply incremental schema migrations."""
    from sqlalchemy import inspect, text
    target_engine = custom_engine or engine
    # Create any completely new tables
    Base.metadata.create_all(bind=target_engine)

    # Incremental column migrations for SQLite (ALTER TABLE ADD COLUMN is safe and idempotent)
    if str(target_engine.url).startswith("sqlite"):
        inspector = inspect(target_engine)
        with target_engine.connect() as conn:
            for table_name, columns in _COLUMN_MIGRATIONS.items():
                try:
                    existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
                except Exception:
                    continue  # table doesn't exist yet; create_all will handle it
                for col_name, col_ddl in columns:
                    if col_name not in existing_cols:
                        conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_ddl}"))
            conn.commit()


# Incremental migrations: list of (column_name, full_DDL_fragment) per table.
# Add new entries here whenever a column is added to an existing ORM model.
_COLUMN_MIGRATIONS: dict = {
    "exceptions": [
        ("source_flag", "source_flag TEXT NOT NULL DEFAULT 'seeded'"),
    ],
}


def reset_db(custom_engine=None) -> None:
    """Drop all tables and recreate clean schema."""
    target_engine = custom_engine or engine
    Base.metadata.drop_all(bind=target_engine)
    Base.metadata.create_all(bind=target_engine)
