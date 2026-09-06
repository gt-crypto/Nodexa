"""Deterministic natural language Q&A engine grounded strictly on uploaded sandbox datasets."""
import re
from typing import Any, Dict, List, Optional
from backend.sandbox.models import (
    FinancialAnalytics,
    SandboxAnalysisReport,
    SandboxQueryResponse,
)
from backend.sandbox.service import format_inr


class SandboxDatasetQAEngine:
    """Answers queries strictly based on ephemeral uploaded dataset analytics and report findings."""

    @classmethod
    def answer_query(
        cls,
        query: str,
        report: SandboxAnalysisReport,
    ) -> SandboxQueryResponse:
        q_lower = query.strip().lower()
        analytics = report.analytics or FinancialAnalytics()
        grounded_data: Dict[str, Any] = {}
        capabilities_used: List[str] = []

        # 1. Total Volume queries
        if any(term in q_lower for term in ("total volume", "gross volume", "total transaction volume", "how much money", "sum of transactions")):
            capabilities_used.append("TRANSACTION_METRICS")
            grounded_data = {
                "total_volume_minor_units": analytics.total_volume_minor_units,
                "total_volume_formatted": analytics.total_volume_inr_formatted,
                "total_records": report.dataset_summary.total_records,
            }
            answer = (
                f"The total transaction volume in this dataset is {analytics.total_volume_inr_formatted} "
                f"across {report.dataset_summary.gateway_transactions or report.dataset_summary.total_records} transactions."
            )
            return SandboxQueryResponse(
                query=query,
                answer=answer,
                grounded_data=grounded_data,
                confidence="HIGH",
                capabilities_used=capabilities_used,
            )

        # 2. Average / Mean queries
        if any(term in q_lower for term in ("average amount", "mean amount", "average transaction", "avg transaction", "typical amount")):
            capabilities_used.append("TRANSACTION_METRICS")
            if analytics.average_amount_inr_formatted:
                grounded_data = {
                    "average_amount_formatted": analytics.average_amount_inr_formatted,
                    "average_amount_minor_units": analytics.average_amount_minor_units,
                }
                answer = f"The average transaction amount in this dataset is {analytics.average_amount_inr_formatted}."
            else:
                answer = "Average amount could not be computed because valid numeric amounts were not detected."
            return SandboxQueryResponse(
                query=query,
                answer=answer,
                grounded_data=grounded_data,
                confidence="HIGH",
                capabilities_used=capabilities_used,
            )

        # 3. Largest / Maximum queries
        if any(term in q_lower for term in ("largest transaction", "maximum transaction", "biggest transaction", "highest amount", "maximum amount")):
            capabilities_used.append("TRANSACTION_METRICS")
            if analytics.largest_amount_inr_formatted:
                grounded_data = {
                    "largest_amount_formatted": analytics.largest_amount_inr_formatted,
                    "largest_amount_minor_units": analytics.largest_amount_minor_units,
                }
                answer = f"The largest transaction in this dataset is {analytics.largest_amount_inr_formatted}."
            else:
                answer = "Largest amount could not be computed because valid amounts were not detected."
            return SandboxQueryResponse(
                query=query,
                answer=answer,
                grounded_data=grounded_data,
                confidence="HIGH",
                capabilities_used=capabilities_used,
            )

        # 4. Top merchant queries
        if any(term in q_lower for term in ("top merchant", "highest volume merchant", "most volume", "biggest vendor", "biggest merchant", "who processed the most")):
            capabilities_used.append("MERCHANT_CONCENTRATION")
            if analytics.top_merchants_by_volume:
                top = analytics.top_merchants_by_volume[0]
                grounded_data = {
                    "top_merchant_id": top.merchant_id,
                    "volume_formatted": top.volume_inr_formatted,
                    "transaction_count": top.transaction_count,
                    "all_top_merchants": [m.model_dump() for m in analytics.top_merchants_by_volume[:5]],
                }
                answer = (
                    f"The top merchant by volume is '{top.merchant_id}' with {top.volume_inr_formatted} "
                    f"across {top.transaction_count} transaction(s)."
                )
            else:
                answer = "Merchant concentration data is not available (no merchant column was identified in this dataset)."
            return SandboxQueryResponse(
                query=query,
                answer=answer,
                grounded_data=grounded_data,
                confidence="HIGH",
                capabilities_used=capabilities_used,
            )

        # 5. Failed / Status queries
        if any(term in q_lower for term in ("failed", "failures", "declined", "failure rate", "how many failed")):
            capabilities_used.append("STATUS_DISTRIBUTION")
            failed_count = analytics.status_breakdown.get("FAILED", 0)
            success_count = analytics.status_breakdown.get("SUCCESS", 0)
            total = failed_count + success_count + analytics.status_breakdown.get("PENDING", 0)
            grounded_data = {
                "status_breakdown": analytics.status_breakdown,
                "failed_count": failed_count,
                "total_records": total,
            }
            if total > 0 and "FAILED" in analytics.status_breakdown:
                fail_pct = round((failed_count / total) * 100, 1)
                answer = f"There are {failed_count} failed transaction(s) out of {total} total ({fail_pct}% failure rate)."
            elif "status" not in [m.canonical_field for m in (report.profile.mapped_fields if report.profile else [])]:
                answer = "Transaction status information is not present in this dataset; failure counts cannot be determined."
            else:
                answer = f"There are 0 failed transactions in this dataset ({success_count} successful)."
            return SandboxQueryResponse(
                query=query,
                answer=answer,
                grounded_data=grounded_data,
                confidence="HIGH",
                capabilities_used=capabilities_used,
            )

        # 6. Settlement / Partial Settlement queries
        if any(term in q_lower for term in ("settlement", "partial settlement", "ghost settlement", "deficit", "clearing")):
            capabilities_used.append("SETTLEMENT_RECONCILIATION")
            # Check for ghost settlements in exceptions
            ghosts = [e for e in report.exceptions if e.exception_type == "GHOST_SETTLEMENT"]
            partials = [e for e in report.exceptions if e.exception_type == "PARTIAL_SETTLEMENT"]
            grounded_data = {
                "settlement_discrepancy_count": analytics.settlement_discrepancy_count,
                "settlement_deficit_formatted": analytics.settlement_total_deficit_inr_formatted,
                "ghost_settlements_found": len(ghosts),
                "partial_settlements_found": len(partials),
            }
            ans_parts = []
            if ghosts:
                ans_parts.append(f"{len(ghosts)} ghost settlement(s) detected (unverified bank settlement without valid successful payment).")
            if partials:
                ans_parts.append(f"{len(partials)} partial settlement(s) detected with deficit totaling {analytics.settlement_total_deficit_inr_formatted}.")
            if not ans_parts:
                if analytics.settlement_discrepancy_count > 0:
                    ans_parts.append(f"{analytics.settlement_discrepancy_count} settlement discrepancies detected.")
                elif "settlement_amount" not in [m.canonical_field for m in (report.profile.mapped_fields if report.profile else [])]:
                    ans_parts.append("Settlement data is not present in this dataset; settlement reconciliation cannot be evaluated.")
                else:
                    ans_parts.append("Zero settlement discrepancies or partial settlements were found in this dataset.")
            answer = " ".join(ans_parts)
            return SandboxQueryResponse(
                query=query,
                answer=answer,
                grounded_data=grounded_data,
                confidence="HIGH",
                capabilities_used=capabilities_used,
            )

        # 7. Refund / Dispute queries
        if any(term in q_lower for term in ("refund", "dispute", "chargeback", "double dip")):
            capabilities_used.append("REFUND_ANALYSIS")
            dd_exceptions = [e for e in report.exceptions if "DOUBLE_DIP" in e.exception_type]
            grounded_data = {
                "refund_total_formatted": analytics.refund_total_inr_formatted,
                "refund_total_minor_units": analytics.refund_total_minor_units,
                "double_dip_count": len(dd_exceptions),
            }
            if analytics.refund_total_minor_units > 0:
                answer = f"Total refunds recorded in this dataset: {analytics.refund_total_inr_formatted}."
                if dd_exceptions:
                    answer += f" Additionally, {len(dd_exceptions)} potential double-dip dispute exception(s) were flagged."
            elif "refund_amount" not in [m.canonical_field for m in (report.profile.mapped_fields if report.profile else [])]:
                answer = "Dispute and refund data is not present in this dataset; refund analysis is unavailable."
            else:
                answer = "Zero refunds or dispute chargebacks were recorded in this dataset."
            return SandboxQueryResponse(
                query=query,
                answer=answer,
                grounded_data=grounded_data,
                confidence="HIGH",
                capabilities_used=capabilities_used,
            )

        # 8. Exceptions & Anomalies general query
        if any(term in q_lower for term in ("exception", "anomaly", "anomalies", "issues", "exposure", "risk")):
            capabilities_used.append("DETERMINISTIC_EXCEPTIONS")
            grounded_data = {
                "exceptions_detected": report.exceptions_detected,
                "high_risk_cases": report.high_risk_cases,
                "total_exposure_formatted": report.total_exposure_inr_formatted,
                "recurring_patterns_count": report.recurring_patterns_count,
            }
            if report.exceptions_detected > 0:
                answer = (
                    f"Nodexa detected {report.exceptions_detected} exception(s) ({report.high_risk_cases} high-risk) "
                    f"with total financial exposure of {report.total_exposure_inr_formatted} and "
                    f"{report.recurring_patterns_count} recurring pattern cluster(s)."
                )
            else:
                answer = "Zero financial exceptions or anomalies were discovered in this dataset."
            return SandboxQueryResponse(
                query=query,
                answer=answer,
                grounded_data=grounded_data,
                confidence="HIGH",
                capabilities_used=capabilities_used,
            )

        # 9. Fallback summary answer
        capabilities_used.append("TRANSACTION_METRICS")
        grounded_data = {
            "total_records": report.dataset_summary.total_records,
            "total_volume_formatted": analytics.total_volume_inr_formatted,
            "exceptions_count": report.exceptions_detected,
        }
        answer = (
            f"Based on the analyzed dataset '{report.dataset_name}': {report.dataset_summary.total_records} records "
            f"were evaluated with total volume of {analytics.total_volume_inr_formatted}. "
            f"A total of {report.exceptions_detected} exception(s) were identified."
        )
        return SandboxQueryResponse(
            query=query,
            answer=answer,
            grounded_data=grounded_data,
            confidence="MEDIUM",
            capabilities_used=capabilities_used,
        )
