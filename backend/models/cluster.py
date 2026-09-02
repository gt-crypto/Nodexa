"""Exception Cluster model for Pattern Miner persistence and explainability."""
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    BigInteger,
    String,
    Text,
    DateTime,
    Index,
)

from backend.models.database import Base


def utc_now():
    return datetime.now(timezone.utc)


class ExceptionCluster(Base):
    """Persisted exception cluster representing a deterministic recurring pattern across exceptions."""
    __tablename__ = "exception_clusters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cluster_id = Column(String(64), unique=True, nullable=False, index=True)
    cluster_key = Column(String(128), nullable=False, index=True)
    pattern_type = Column(String(64), nullable=False, index=True)
    pattern_label = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    
    exception_count = Column(Integer, nullable=False, default=0)
    exception_ids = Column(Text, nullable=False)  # JSON-encoded array of exception_id strings
    merchants = Column(Text, nullable=False, default="[]")  # JSON-encoded array of merchant_id strings
    families = Column(Text, nullable=False, default="[]")  # JSON-encoded array of exception types
    
    first_seen = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    last_seen = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    total_exposure = Column(BigInteger, nullable=False, default=0)
    
    live_injected_count = Column(Integer, nullable=False, default=0)
    seeded_count = Column(Integer, nullable=False, default=0)
    
    evidence = Column(Text, nullable=False, default="{}")  # JSON-encoded signature and matching metadata
    
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        Index("idx_clusters_type_count", "pattern_type", "exception_count"),
        Index("idx_clusters_updated", "updated_at"),
    )
