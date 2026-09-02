"""Deterministic Pattern Signature extraction from operational exception records."""
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from backend.models.exceptions import ExceptionRecord, ExceptionAffectedRecord
from backend.models.financial_sources import GatewayTransaction, BankSettlementBatch, NodalLedgerEntry
from backend.agent.tools.control_findings import lookup_control_findings


@dataclass
class PatternSignature:
    """Structured dimensional signature extracted from an individual exception."""
    exception_id: str
    exception_type: str
    severity: str
    state: str
    exposure: int
    detected_at: datetime
    source_flag: str = "seeded"  # 'seeded' | 'live-injected'
    
    # Financial & Merchant Dimensions
    merchant_id: Optional[str] = None
    payment_id: Optional[str] = None
    payment_method: Optional[str] = None
    payment_status: Optional[str] = None
    order_id: Optional[str] = None
    
    # Settlement & Ledger Dimensions
    settlement_id: Optional[str] = None
    settlement_count: int = 0
    ledger_entry_count: int = 0
    
    # Control Finding Codes (e.g. CTRL-001, CTRL-004)
    control_codes: List[str] = field(default_factory=list)
    
    # Affected Records
    affected_record_types: List[str] = field(default_factory=list)


class PatternExtractionService:
    """Extracts structured dimensional signatures from operational exception records."""

    @staticmethod
    def extract_signature(session: Session, exception: ExceptionRecord) -> PatternSignature:
        """Extracts structured multidimensional signature for a single exception."""
        merchant_id = None
        payment_method = None
        payment_status = None
        settlement_id = None
        settlement_count = 0
        ledger_count = 0

        # 1. Payment Details
        if exception.primary_payment_id:
            gtx = session.scalars(
                select(GatewayTransaction).where(GatewayTransaction.payment_id == exception.primary_payment_id)
            ).first()
            if gtx:
                merchant_id = gtx.merchant_id
                payment_method = gtx.method
                payment_status = gtx.status

            # 2. Settlement Details
            batches = session.scalars(
                select(BankSettlementBatch).where(
                    or_(
                        BankSettlementBatch.payment_id == exception.primary_payment_id,
                        BankSettlementBatch.settlement_id == exception.primary_payment_id,
                    )
                )
            ).all()
            settlement_count = len(batches)
            if batches:
                settlement_id = batches[0].settlement_id

            # 3. Ledger Entries
            led_count = len(
                session.scalars(
                    select(NodalLedgerEntry).where(NodalLedgerEntry.transaction_id == exception.primary_payment_id)
                ).all()
            )
            ledger_count = led_count

        # 4. Control Findings
        control_codes = []
        if exception.primary_payment_id:
            findings = lookup_control_findings(session=session, payment_id=exception.primary_payment_id)
            for f in findings:
                if isinstance(f, dict):
                    code = f.get("control_id") or f.get("code") or f.get("check_id")
                    if code and code not in control_codes:
                        control_codes.append(str(code))


        # 5. Affected Records
        aff_stmt = select(ExceptionAffectedRecord).where(
            ExceptionAffectedRecord.exception_id == exception.exception_id
        )
        aff_records = session.scalars(aff_stmt).all()
        affected_types = list(dict.fromkeys([r.record_type for r in aff_records]))

        return PatternSignature(
            exception_id=exception.exception_id,
            exception_type=exception.exception_type,
            severity=exception.severity,
            state=exception.state,
            exposure=exception.exposure or 0,
            detected_at=exception.detected_at or datetime.now(timezone.utc),
            source_flag=exception.source_flag or "seeded",
            merchant_id=merchant_id,
            payment_id=exception.primary_payment_id,
            payment_method=payment_method,
            payment_status=payment_status,
            order_id=exception.primary_order_id,
            settlement_id=settlement_id,
            settlement_count=settlement_count,
            ledger_entry_count=ledger_count,
            control_codes=sorted(control_codes),
            affected_record_types=sorted(affected_types),
        )

    @classmethod
    def extract_all_signatures(
        cls,
        session: Session,
        exceptions: Optional[List[ExceptionRecord]] = None,
    ) -> List[PatternSignature]:
        """Batch-extracts signatures for all or specified exceptions."""
        if exceptions is None:
            stmt = select(ExceptionRecord).order_by(ExceptionRecord.detected_at.asc())
            exceptions = list(session.scalars(stmt).all())

        return [cls.extract_signature(session, exc) for exc in exceptions]
