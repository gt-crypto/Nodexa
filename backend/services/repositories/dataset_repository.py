"""Repository for synthetic dataset metadata."""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.dataset import DatasetMetadata


class DatasetRepository:
    """Provides data access for synthetic dataset metadata."""

    def __init__(self, session: Session):
        self.session = session

    def save_dataset_metadata(self, metadata: DatasetMetadata) -> DatasetMetadata:
        """Saves metadata for a generated synthetic dataset."""
        self.session.add(metadata)
        self.session.flush()
        return metadata

    def get_dataset_metadata(self, dataset_id: str) -> Optional[DatasetMetadata]:
        """Retrieves dataset metadata by dataset_id."""
        stmt = select(DatasetMetadata).where(DatasetMetadata.dataset_id == dataset_id)
        return self.session.scalars(stmt).first()

    def list_datasets(self, limit: int = 50) -> List[DatasetMetadata]:
        """Lists generated dataset records ordered by generation timestamp."""
        stmt = select(DatasetMetadata).order_by(DatasetMetadata.generated_at.desc()).limit(limit)
        return list(self.session.scalars(stmt).all())
