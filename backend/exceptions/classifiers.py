"""Deterministic rule-based exception classifiers for all PRD MVP exception families."""
from dataclasses import dataclass, field
from typing import List, Optional

from backend.models.enums import ExceptionType, ExceptionSeverity, PaymentStatus, OrderFulfillmentStatus
from backend.controls.control_result import EvidenceItem
from backend.controls.settlement_sla import SLATimingStatus
from backend.reconciliation.settlements import SettlementReconciliationStatus, aggregate_settlements_for_payment
from backend.exceptions.correlator import CorrelatedEntity
from backend.exceptions.exposure import calculate_exception_exposure
from backend.exceptions.severity import assign_exception_severity, SeverityConfig


@dataclass
class ExceptionClassification:
    """Deterministic classification output for a correlated entity."""
    exception_type: ExceptionType
    sub_type: Optional[str] = None  # e.g. MISSING_SETTLEMENT or UNALLOCATED_SETTLEMENT
    is_legitimate_observation: bool = False
    exposure: int = 0
    severity: ExceptionSeverity = ExceptionSeverity.LOW
    description: str = ""
    evidence_items: List[EvidenceItem] = field(default_factory=list)


def classify_ghost_settlement(
    entity: CorrelatedEntity,
    severity_config: Optional[SeverityConfig] = None,
) -> Optional[ExceptionClassification]:
    """Detects ghost settlements where gateway payment failed or order cancelled yet funds cleared."""
    if not entity.payment:
        return None

    is_failed_gateway = entity.payment.status == PaymentStatus.FAILED.value
    is_cancelled_order = any(o.fulfillment_status == OrderFulfillmentStatus.CANCELLED.value for o in entity.orders)

    has_settlement_movement = len(entity.settlements) > 0 or any(l.credit > 0 for l in entity.ledger_entries)

    if (is_failed_gateway or is_cancelled_order) and has_settlement_movement:
        exposure = calculate_exception_exposure(
            ExceptionType.GHOST_SETTLEMENT,
            payment=entity.payment,
            settlements=entity.settlements,
        )
        severity = assign_exception_severity(ExceptionType.GHOST_SETTLEMENT, exposure, severity_config)

        evidence = [
            EvidenceItem(
                source="gateway_transactions",
                record_id=entity.payment.payment_id,
                field="status",
                value=entity.payment.status,
                comparison="Gateway transaction state is FAILED but settlement funds cleared",
            )
        ]
        if entity.orders:
            evidence.append(
                EvidenceItem(
                    source="merchant_orders",
                    record_id=entity.orders[0].order_id,
                    field="fulfillment_status",
                    value=entity.orders[0].fulfillment_status,
                )
            )
        for s in entity.settlements:
            evidence.append(
                EvidenceItem(
                    source="bank_settlement_batches",
                    record_id=s.settlement_id,
                    field="net_amount",
                    value=s.net_amount,
                    comparison="Settlement batch credited despite failure",
                )
            )

        return ExceptionClassification(
            exception_type=ExceptionType.GHOST_SETTLEMENT,
            is_legitimate_observation=False,
            exposure=exposure,
            severity=severity,
            description=f"Ghost settlement: Payment {entity.payment.payment_id} marked {entity.payment.status} with {len(entity.settlements)} clearing batches.",
            evidence_items=evidence,
        )

    return None


def classify_refund_chargeback_double_dip(
    entity: CorrelatedEntity,
    severity_config: Optional[SeverityConfig] = None,
) -> Optional[ExceptionClassification]:
    """Detects dual financial liability caused by overlapping refund and chargeback events."""
    if not entity.payment or not entity.disputes:
        return None

    event_types = {d.event_type for d in entity.disputes}
    has_refund = "REFUND" in event_types
    has_chargeback = "CHARGEBACK" in event_types

    if has_refund and has_chargeback:
        exposure = calculate_exception_exposure(
            ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP,
            payment=entity.payment,
            settlements=entity.settlements,
            disputes=entity.disputes,
        )
        severity = assign_exception_severity(ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP, exposure, severity_config)

        evidence = [
            EvidenceItem(
                source="gateway_transactions",
                record_id=entity.payment.payment_id,
                field="amount",
                value=entity.payment.amount,
            )
        ]
        for d in entity.disputes:
            evidence.append(
                EvidenceItem(
                    source="dispute_refund_events",
                    record_id=d.event_id,
                    field="event_type/amount",
                    value={"type": d.event_type, "amount": d.amount, "timestamp": d.timestamp.isoformat()},
                    comparison=f"Overlapping {d.event_type} event",
                )
            )

        return ExceptionClassification(
            exception_type=ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP,
            is_legitimate_observation=False,
            exposure=exposure,
            severity=severity,
            description=f"Refund and chargeback double-dip on payment {entity.payment.payment_id} with dual debit exposure.",
            evidence_items=evidence,
        )

    return None


def classify_settlement_sla_breach(
    entity: CorrelatedEntity,
    severity_config: Optional[SeverityConfig] = None,
) -> Optional[ExceptionClassification]:
    """Detects genuine settlement SLA breach where settlement clearance exceeded allowable window."""
    if not entity.payment or entity.payment.status != PaymentStatus.CAPTURED.value:
        return None

    # Exclude missing settlements (handled by missing settlement classifier)
    if not entity.settlements:
        return None

    # Inspect deterministic control results from Prompt 3
    for ctrl in entity.control_results:
        timing_status = ctrl.calculated_values.get("timing_status")
        if timing_status == SLATimingStatus.SLA_BREACH.value:
            exposure = calculate_exception_exposure(ExceptionType.SETTLEMENT_SLA_BREACH, payment=entity.payment)
            severity = assign_exception_severity(ExceptionType.SETTLEMENT_SLA_BREACH, exposure, severity_config)

            evidence = [
                EvidenceItem(
                    source="gateway_transactions",
                    record_id=entity.payment.payment_id,
                    field="created_at",
                    value=entity.payment.created_at.isoformat(),
                ),
                EvidenceItem(
                    source="bank_settlement_batches",
                    record_id=entity.settlements[0].settlement_id,
                    field="clearing_timestamp",
                    value=entity.settlements[0].clearing_timestamp.isoformat(),
                    comparison=f"Cleared {ctrl.calculated_values.get('elapsed_raw_hours')}h after capture (SLA breach)",
                ),
            ]

            return ExceptionClassification(
                exception_type=ExceptionType.SETTLEMENT_SLA_BREACH,
                is_legitimate_observation=False,
                exposure=exposure,
                severity=severity,
                description=f"Settlement SLA breach on payment {entity.payment.payment_id}: Cleared {ctrl.calculated_values.get('elapsed_raw_hours')}h post-capture.",
                evidence_items=evidence,
            )

    return None


def classify_legitimate_partial_settlement(
    entity: CorrelatedEntity,
) -> Optional[ExceptionClassification]:
    """Recognizes legitimate multi-tranche partial settlements as clean reconciled observations (exposure = 0)."""
    if not entity.payment or entity.payment.status != PaymentStatus.CAPTURED.value:
        return None

    if len(entity.settlements) > 1:
        agg = aggregate_settlements_for_payment(entity.payment, entity.settlements)
        if agg.status == SettlementReconciliationStatus.PARTIAL_SETTLEMENT_COMPLETE:
            evidence = [
                EvidenceItem(
                    source="gateway_transactions",
                    record_id=entity.payment.payment_id,
                    field="amount",
                    value=entity.payment.amount,
                )
            ]
            for s in entity.settlements:
                evidence.append(
                    EvidenceItem(
                        source="bank_settlement_batches",
                        record_id=s.settlement_id,
                        field="gross_amount",
                        value=s.net_amount + s.interchange_fee_deducted + s.tax_deducted,
                    )
                )

            return ExceptionClassification(
                exception_type=ExceptionType.PARTIAL_SETTLEMENT,
                is_legitimate_observation=True,
                exposure=0,
                severity=ExceptionSeverity.LOW,
                description=f"Legitimate partial settlement: Payment {entity.payment.payment_id} split across {len(entity.settlements)} reconciled tranches.",
                evidence_items=evidence,
            )

    return None


def classify_missing_settlement(
    entity: CorrelatedEntity,
    severity_config: Optional[SeverityConfig] = None,
) -> Optional[ExceptionClassification]:
    """Detects missing settlement for a captured payment with zero clearing records."""
    if not entity.payment or entity.payment.status != PaymentStatus.CAPTURED.value:
        return None

    if len(entity.settlements) == 0:
        exposure = calculate_exception_exposure(
            ExceptionType.MISSING_UNALLOCATED_SETTLEMENT,
            payment=entity.payment,
            sub_type="MISSING_SETTLEMENT",
        )
        severity = assign_exception_severity(ExceptionType.MISSING_UNALLOCATED_SETTLEMENT, exposure, severity_config)

        evidence = [
            EvidenceItem(
                source="gateway_transactions",
                record_id=entity.payment.payment_id,
                field="status",
                value=entity.payment.status,
                comparison="Captured payment has 0 downstream settlement records",
            )
        ]

        return ExceptionClassification(
            exception_type=ExceptionType.MISSING_UNALLOCATED_SETTLEMENT,
            sub_type="MISSING_SETTLEMENT",
            is_legitimate_observation=False,
            exposure=exposure,
            severity=severity,
            description=f"Missing settlement: Captured payment {entity.payment.payment_id} has zero bank settlement batches.",
            evidence_items=evidence,
        )

    return None


def classify_unallocated_settlement(
    entity: CorrelatedEntity,
    severity_config: Optional[SeverityConfig] = None,
) -> Optional[ExceptionClassification]:
    """Detects orphan bank settlement inflows with payment_id = NULL."""
    # Entity without payment or explicitly orphan settlement
    if not entity.payment and len(entity.settlements) > 0:
        orphan = entity.settlements[0]
        exposure = calculate_exception_exposure(
            ExceptionType.MISSING_UNALLOCATED_SETTLEMENT,
            settlements=[orphan],
            sub_type="UNALLOCATED_SETTLEMENT",
        )
        severity = assign_exception_severity(ExceptionType.MISSING_UNALLOCATED_SETTLEMENT, exposure, severity_config)

        evidence = [
            EvidenceItem(
                source="bank_settlement_batches",
                record_id=orphan.settlement_id,
                field="payment_id",
                value=orphan.payment_id,
                comparison="Bank settlement inflow exists with no payment mapping (unallocated)",
            ),
            EvidenceItem(
                source="bank_settlement_batches",
                record_id=orphan.settlement_id,
                field="net_amount",
                value=orphan.net_amount,
            ),
        ]

        return ExceptionClassification(
            exception_type=ExceptionType.MISSING_UNALLOCATED_SETTLEMENT,
            sub_type="UNALLOCATED_SETTLEMENT",
            is_legitimate_observation=False,
            exposure=exposure,
            severity=severity,
            description=f"Unallocated settlement: Batch {orphan.settlement_id} (UTR: {orphan.utr_number}) has no mapped payment.",
            evidence_items=evidence,
        )

    return None


def classify_legitimate_timing_exception(
    entity: CorrelatedEntity,
) -> Optional[ExceptionClassification]:
    """Recognizes weekend/post-cutoff payments clearing in next window as legitimate (exposure = 0)."""
    if not entity.payment or entity.payment.status != PaymentStatus.CAPTURED.value:
        return None

    for ctrl in entity.control_results:
        timing_status = ctrl.calculated_values.get("timing_status")
        if timing_status == SLATimingStatus.LATE_BUT_VALID.value:
            evidence = [
                EvidenceItem(
                    source="gateway_transactions",
                    record_id=entity.payment.payment_id,
                    field="created_at",
                    value=entity.payment.created_at.isoformat(),
                )
            ]
            if entity.settlements:
                evidence.append(
                    EvidenceItem(
                        source="bank_settlement_batches",
                        record_id=entity.settlements[0].settlement_id,
                        field="clearing_timestamp",
                        value=entity.settlements[0].clearing_timestamp.isoformat(),
                        comparison="Cleared within next valid processing window despite raw delay",
                    )
                )

            return ExceptionClassification(
                exception_type=ExceptionType.LEGITIMATE_TIMING_EXCEPTION,
                is_legitimate_observation=True,
                exposure=0,
                severity=ExceptionSeverity.LOW,
                description=f"Legitimate timing exception: Payment {entity.payment.payment_id} cleared during next valid window.",
                evidence_items=evidence,
            )

    return None
