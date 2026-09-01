"""Repository for Verification Records and Results."""
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.verification import VerificationRecord, VerificationResult


class VerificationRepository:
    """Provides structured data access for post-remediation verification records."""

    def __init__(self, session: Session):
        self.session = session

    def create_verification_record(self, record: VerificationRecord) -> VerificationRecord:
        """Stores a new verification record."""
        self.session.add(record)
        self.session.flush()
        return record

    def get_verification_record(self, verification_id: str) -> Optional[VerificationRecord]:
        """Retrieves a verification record by its unique verification_id."""
        stmt = select(VerificationRecord).where(VerificationRecord.verification_id == verification_id)
        return self.session.scalars(stmt).first()

    def get_latest_for_remediation(self, remediation_id: str) -> Optional[VerificationRecord]:
        """Retrieves the most recent verification record for a remediation action."""
        stmt = (
            select(VerificationRecord)
            .where(VerificationRecord.remediation_id == remediation_id)
            .order_by(VerificationRecord.created_at.desc(), VerificationRecord.id.desc())
        )
        return self.session.scalars(stmt).first()

    def list_records_for_remediation(self, remediation_id: str) -> List[VerificationRecord]:
        """Retrieves all verification records associated with a remediation action."""
        stmt = (
            select(VerificationRecord)
            .where(VerificationRecord.remediation_id == remediation_id)
            .order_by(VerificationRecord.created_at.desc())
        )
        return list(self.session.scalars(stmt).all())

    def list_records_for_exception(self, exception_id: str) -> List[VerificationRecord]:
        """Retrieves all verification records associated with an exception."""
        stmt = (
            select(VerificationRecord)
            .where(VerificationRecord.exception_id == exception_id)
            .order_by(VerificationRecord.created_at.desc())
        )
        return list(self.session.scalars(stmt).all())

    # Legacy support
    def create_verification_result(self, result: VerificationResult) -> VerificationResult:
        """Stores a new legacy verification result."""
        self.session.add(result)
        self.session.flush()
        return result

    def get_verification_result(self, verification_id: str) -> Optional[VerificationResult]:
        """Retrieves a legacy verification result by its verification_id."""
        stmt = select(VerificationResult).where(VerificationResult.verification_id == verification_id)
        return self.session.scalars(stmt).first()

    def list_results_for_exception(self, exception_id: str) -> List[VerificationResult]:
        """Retrieves all legacy verification results associated with an exception."""
        stmt = (
            select(VerificationResult)
            .where(VerificationResult.exception_id == exception_id)
            .order_by(VerificationResult.started_at.desc())
        )
        return list(self.session.scalars(stmt).all())
