"""Dataset metadata model for synthetic financial dataset provenance and reproducibility."""
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


class DatasetMetadata(Base):
    """Stores metadata for generated synthetic financial datasets ensuring reproducibility."""
    __tablename__ = "dataset_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_id = Column(String(64), unique=True, nullable=False, index=True)
    dataset_version = Column(String(32), nullable=False)
    seed = Column(BigInteger, nullable=True)
    record_count = Column(Integer, nullable=False, default=0)
    generated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    description = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_ds_version_generated", "dataset_version", "generated_at"),
    )
