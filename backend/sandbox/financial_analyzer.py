"""Deterministic financial analytics calculator across canonical records."""
from collections import defaultdict
from typing import Dict, List, Optional
from backend.sandbox.models import (
    CapabilityItem,
    FinancialAnalytics,
    MerchantVolumeItem,
)
from backend.sandbox.canonical import CanonicalFinancialRow
from backend.sandbox.service import format_inr


class FinancialAnalyticsEngine:
    """Computes comprehensive deterministic financial metrics across canonical rows."""

    @staticmethod
    def compute(
        canonical_rows: List[CanonicalFinancialRow],
        capabilities: List[CapabilityItem],
    ) -> FinancialAnalytics:
        if not canonical_rows:
            return FinancialAnalytics(
                unavailable_capabilities_disclaimer=["Dataset contains 0 records; no metrics could be computed."]
            )

        # 1. Volume & Extremes
        amounts = [r.amount_paise for r in canonical_rows if r.amount_paise is not None and r.amount_paise > 0]
        total_vol = sum(amounts)
        avg_amt = int(round(total_vol / len(amounts))) if amounts else None
        largest_amt = max(amounts) if amounts else None
        smallest_amt = min(amounts) if amounts else None

        # 2. Status Breakdown
        status_counts: Dict[str, int] = defaultdict(int)
        for r in canonical_rows:
            status_counts[r.status] += 1

        # 3. Settlement Discrepancy & Deficit
        reconciled_count = 0
        discrepancy_count = 0
        total_deficit = 0

        for r in canonical_rows:
            if r.settlement_amount_paise is not None:
                if r.settlement_amount_paise == r.amount_paise:
                    reconciled_count += 1
                else:
                    discrepancy_count += 1
                    if r.settlement_amount_paise < r.amount_paise:
                        total_deficit += (r.amount_paise - r.settlement_amount_paise)

        # 4. Refunds
        refund_total = sum(r.refund_amount_paise for r in canonical_rows if r.refund_amount_paise)

        # 5. Merchant Concentration
        merchant_vols: Dict[str, int] = defaultdict(int)
        merchant_counts: Dict[str, int] = defaultdict(int)
        for r in canonical_rows:
            merchant_vols[r.merchant_id] += r.amount_paise
            merchant_counts[r.merchant_id] += 1

        sorted_merchants = sorted(merchant_vols.items(), key=lambda x: x[1], reverse=True)
        top_merchants: List[MerchantVolumeItem] = [
            MerchantVolumeItem(
                merchant_id=m_id,
                volume_minor_units=m_vol,
                volume_inr_formatted=format_inr(m_vol),
                transaction_count=merchant_counts[m_id],
            )
            for m_id, m_vol in sorted_merchants[:10]
        ]

        # 6. Sample size notice
        sample_notice = None
        if len(canonical_rows) < 10:
            sample_notice = (
                f"Sample size notice: Dataset contains {len(canonical_rows)} records ({len(canonical_rows)} rows). "
                "Statistical concentration metrics may have high variance."
            )

        # 7. Unavailable capabilities honest disclaimers
        unavail_disclaimers: List[str] = []
        for cap in capabilities:
            if not cap.available:
                unavail_disclaimers.append(f"{cap.name}: {cap.reason}")

        return FinancialAnalytics(
            total_volume_minor_units=total_vol,
            total_volume_inr_formatted=format_inr(total_vol),
            average_amount_minor_units=avg_amt,
            average_amount_inr_formatted=format_inr(avg_amt) if avg_amt is not None else None,
            largest_amount_minor_units=largest_amt,
            largest_amount_inr_formatted=format_inr(largest_amt) if largest_amt is not None else None,
            smallest_amount_minor_units=smallest_amt,
            smallest_amount_inr_formatted=format_inr(smallest_amt) if smallest_amt is not None else None,
            status_breakdown=dict(status_counts),
            settlement_reconciled_count=reconciled_count,
            settlement_discrepancy_count=discrepancy_count,
            settlement_total_deficit_minor_units=total_deficit,
            settlement_total_deficit_inr_formatted=format_inr(total_deficit),
            refund_total_minor_units=refund_total,
            refund_total_inr_formatted=format_inr(refund_total),
            top_merchants_by_volume=top_merchants,
            sample_size_notice=sample_notice,
            unavailable_capabilities_disclaimer=unavail_disclaimers,
            unavailable_capabilities=unavail_disclaimers,
        )
