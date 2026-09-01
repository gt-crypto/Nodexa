"""Deterministic multi-source identifier matching service."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from backend.controls.control_result import ControlResult, ControlStatus, EvidenceItem
from backend.models.financial_sources import (
    GatewayTransaction,
    BankSettlementBatch,
    MerchantOrder,
    DisputeRefundEvent,
    NodalLedgerEntry,
)


class MatchStatus(str, Enum):
    """Classification of identifier matching across financial records."""
    EXACT_MATCH = "EXACT_MATCH"
    NO_MATCH = "NO_MATCH"
    AMBIGUOUS_MATCH = "AMBIGUOUS_MATCH"
    MULTIPLE_MATCHES = "MULTIPLE_MATCHES"


@dataclass
class MatchResult:
    """Detailed result of an identifier matching operation."""
    source_identifier: str
    target_entity: str
    status: MatchStatus
    matched_ids: List[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)
    evidence: List[EvidenceItem] = field(default_factory=list)

    def to_control_result(self, control_id: str, control_name: str) -> ControlResult:
        ctrl_status = ControlStatus.PASS if self.status in (MatchStatus.EXACT_MATCH, MatchStatus.MULTIPLE_MATCHES) else ControlStatus.FAIL
        severity = "HIGH" if self.status in (MatchStatus.NO_MATCH, MatchStatus.AMBIGUOUS_MATCH) else None

        return ControlResult(
            control_id=control_id,
            control_name=control_name,
            status=ctrl_status,
            severity=severity,
            affected_record_ids=[self.source_identifier] + self.matched_ids,
            calculated_values={
                "match_status": self.status.value,
                "target_entity": self.target_entity,
                "matched_count": len(self.matched_ids),
                **self.details,
            },
            evidence=self.evidence,
            rule=f"Source record {self.source_identifier} must have verifiable linkage to {self.target_entity}.",
        )


def match_payment_to_orders(
    payment: GatewayTransaction,
    orders: List[MerchantOrder],
) -> MatchResult:
    """Matches a gateway payment to merchant orders via payment_id_reference."""
    matched = [o for o in orders if o.payment_id_reference == payment.payment_id]
    
    if len(matched) == 1:
        status = MatchStatus.EXACT_MATCH
    elif len(matched) == 0:
        status = MatchStatus.NO_MATCH
    else:
        status = MatchStatus.MULTIPLE_MATCHES

    evidence = [
        EvidenceItem(
            source="gateway_transactions",
            record_id=payment.payment_id,
            field="payment_id",
            value=payment.payment_id,
        )
    ]
    for o in matched:
        evidence.append(
            EvidenceItem(
                source="merchant_orders",
                record_id=o.order_id,
                field="payment_id_reference",
                value=o.payment_id_reference,
            )
        )

    return MatchResult(
        source_identifier=payment.payment_id,
        target_entity="merchant_orders",
        status=status,
        matched_ids=[o.order_id for o in matched],
        evidence=evidence,
    )


def match_payment_to_settlements(
    payment: GatewayTransaction,
    settlements: List[BankSettlementBatch],
) -> MatchResult:
    """Matches a gateway payment to bank settlements by payment_id or raw reference."""
    direct_matches = [s for s in settlements if s.payment_id == payment.payment_id]
    
    # If no direct matches, check raw payment reference
    ref_matches = [
        s for s in settlements
        if s.payment_id != payment.payment_id and s.raw_payment_reference and payment.payment_id in s.raw_payment_reference
    ]
    
    all_matched = direct_matches + ref_matches
    
    if len(all_matched) == 1:
        status = MatchStatus.EXACT_MATCH
    elif len(all_matched) == 0:
        status = MatchStatus.NO_MATCH
    elif len(direct_matches) > 1 and len(ref_matches) == 0:
        status = MatchStatus.MULTIPLE_MATCHES  # Legitimate multi-tranche partial settlement
    else:
        status = MatchStatus.AMBIGUOUS_MATCH

    evidence = [
        EvidenceItem(
            source="gateway_transactions",
            record_id=payment.payment_id,
            field="payment_id",
            value=payment.payment_id,
        )
    ]
    for s in all_matched:
        evidence.append(
            EvidenceItem(
                source="bank_settlement_batches",
                record_id=s.settlement_id,
                field="payment_id/raw_payment_reference",
                value={"payment_id": s.payment_id, "raw_ref": s.raw_payment_reference},
            )
        )

    return MatchResult(
        source_identifier=payment.payment_id,
        target_entity="bank_settlement_batches",
        status=status,
        matched_ids=[s.settlement_id for s in all_matched],
        details={"direct_count": len(direct_matches), "raw_ref_count": len(ref_matches)},
        evidence=evidence,
    )


def match_settlement_to_payment(
    settlement: BankSettlementBatch,
    payments: List[GatewayTransaction],
) -> MatchResult:
    """Matches a bank settlement record back to its source gateway payment."""
    if settlement.payment_id:
        matched = [p for p in payments if p.payment_id == settlement.payment_id]
        if len(matched) == 1:
            status = MatchStatus.EXACT_MATCH
        elif len(matched) == 0:
            status = MatchStatus.NO_MATCH
        else:
            status = MatchStatus.AMBIGUOUS_MATCH
    else:
        # Check raw reference for unallocated or unmapped settlement
        if settlement.raw_payment_reference:
            matched = [p for p in payments if p.payment_id in settlement.raw_payment_reference]
            if len(matched) == 1:
                status = MatchStatus.AMBIGUOUS_MATCH  # unallocated in column but reference exists
            else:
                status = MatchStatus.NO_MATCH  # Orphan unallocated
        else:
            matched = []
            status = MatchStatus.NO_MATCH

    evidence = [
        EvidenceItem(
            source="bank_settlement_batches",
            record_id=settlement.settlement_id,
            field="payment_id",
            value=settlement.payment_id,
        )
    ]
    for p in matched:
        evidence.append(
            EvidenceItem(
                source="gateway_transactions",
                record_id=p.payment_id,
                field="payment_id",
                value=p.payment_id,
            )
        )

    return MatchResult(
        source_identifier=settlement.settlement_id,
        target_entity="gateway_transactions",
        status=status,
        matched_ids=[p.payment_id for p in matched],
        evidence=evidence,
    )
