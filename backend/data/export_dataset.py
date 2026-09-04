"""Nodexa - Export Canonical Synthetic Dataset.

Extracts the canonical 60-transaction synthetic dataset from the database
(or generates it deterministically) and saves:
1. deployment_artifacts/nodexa_synthetic_dataset.csv
2. deployment_artifacts/nodexa_synthetic_dataset.json
"""
import os
import sys
import csv
import json
from pathlib import Path
from typing import Dict, Any, List

# Ensure project root in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.models.database import SessionLocal, init_db
from backend.models.financial_sources import (
    GatewayTransaction,
    MerchantOrder,
    BankSettlementBatch,
    DisputeRefundEvent,
    NodalLedgerEntry,
)
from backend.models.exceptions import ExceptionRecord
from backend.models.ground_truth import EvaluationGroundTruth
from backend.data.seed_clean import ensure_canonical_seed


def export_canonical_dataset(output_dir: str = "deployment_artifacts") -> Dict[str, Any]:
    """Extracts operational records and exports CSV and JSON artifacts."""
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    init_db()
    db = SessionLocal()
    try:
        # Ensure canonical seed is active
        seed_result = ensure_canonical_seed(db)

        # 1. Fetch all financial source records
        transactions: List[GatewayTransaction] = (
            db.query(GatewayTransaction).order_by(GatewayTransaction.id).all()
        )
        orders: List[MerchantOrder] = (
            db.query(MerchantOrder).order_by(MerchantOrder.id).all()
        )
        settlements: List[BankSettlementBatch] = (
            db.query(BankSettlementBatch).order_by(BankSettlementBatch.id).all()
        )
        ledgers: List[NodalLedgerEntry] = (
            db.query(NodalLedgerEntry).order_by(NodalLedgerEntry.id).all()
        )
        disputes: List[DisputeRefundEvent] = (
            db.query(DisputeRefundEvent).order_by(DisputeRefundEvent.id).all()
        )
        exceptions: List[ExceptionRecord] = (
            db.query(ExceptionRecord).order_by(ExceptionRecord.id).all()
        )
        ground_truth: List[EvaluationGroundTruth] = (
            db.query(EvaluationGroundTruth).order_by(EvaluationGroundTruth.id).all()
        )

        # Build lookup maps
        orders_by_pmt = {o.payment_id_reference: o for o in orders if o.payment_id_reference}
        settlements_by_pmt = {}
        for s in settlements:
            if s.payment_id:
                settlements_by_pmt.setdefault(s.payment_id, []).append(s)

        disputes_by_pmt = {}
        for d in disputes:
            disputes_by_pmt.setdefault(d.payment_id, []).append(d)

        ledgers_by_pmt = {}
        for l in ledgers:
            if l.transaction_id:
                ledgers_by_pmt.setdefault(l.transaction_id, []).append(l)

        exceptions_by_pmt = {e.primary_payment_id: e for e in exceptions if e.primary_payment_id}

        # 2. Build Tabular Rows for CSV
        csv_rows = []
        for tx in transactions:
            mo = orders_by_pmt.get(tx.payment_id)
            sb_list = settlements_by_pmt.get(tx.payment_id, [])
            df_list = disputes_by_pmt.get(tx.payment_id, [])
            ld_list = ledgers_by_pmt.get(tx.payment_id, [])
            exc = exceptions_by_pmt.get(tx.payment_id)

            total_settled_paise = sum(s.net_amount for s in sb_list)
            total_fee_deducted = sum(s.interchange_fee_deducted for s in sb_list)
            total_tax_deducted = sum(s.tax_deducted for s in sb_list)

            is_anomalous = exc is not None
            anomaly_type = exc.exception_type if exc else "NORMAL"
            severity = exc.severity if exc else "NONE"
            lifecycle_state = exc.state if exc else "RECONCILED"
            exposure_paise = exc.exposure if exc else 0

            csv_rows.append({
                "payment_id": tx.payment_id,
                "merchant_id": tx.merchant_id,
                "order_id": mo.order_id if mo else "N/A",
                "payment_method": tx.method,
                "gateway_status": tx.status,
                "order_fulfillment": mo.fulfillment_status if mo else "N/A",
                "amount_paise": tx.amount,
                "amount_inr": round(tx.amount / 100.0, 2),
                "order_amount_paise": mo.order_amount if mo else 0,
                "order_amount_inr": round((mo.order_amount or 0) / 100.0, 2) if mo else 0.0,
                "settlement_count": len(sb_list),
                "settled_net_amount_inr": round(total_settled_paise / 100.0, 2),
                "interchange_fee_inr": round(total_fee_deducted / 100.0, 2),
                "tax_inr": round(total_tax_deducted / 100.0, 2),
                "dispute_event_count": len(df_list),
                "ledger_entry_count": len(ld_list),
                "is_anomalous": "TRUE" if is_anomalous else "FALSE",
                "anomaly_type": anomaly_type,
                "severity": severity,
                "finance_ops_state": lifecycle_state,
                "exposure_inr": round(exposure_paise / 100.0, 2),
                "created_at": tx.created_at.isoformat() if tx.created_at else "",
            })

        # Write CSV
        csv_file = out_path / "nodexa_synthetic_dataset.csv"
        fieldnames = [
            "payment_id",
            "merchant_id",
            "order_id",
            "payment_method",
            "gateway_status",
            "order_fulfillment",
            "amount_paise",
            "amount_inr",
            "order_amount_paise",
            "order_amount_inr",
            "settlement_count",
            "settled_net_amount_inr",
            "interchange_fee_inr",
            "tax_inr",
            "dispute_event_count",
            "ledger_entry_count",
            "is_anomalous",
            "anomaly_type",
            "severity",
            "finance_ops_state",
            "exposure_inr",
            "created_at",
        ]

        with open(csv_file, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(csv_rows)

        # 3. Build Full Structured JSON
        json_data = {
            "metadata": {
                "dataset_name": "Nodexa Canonical Synthetic Finance Dataset",
                "seed": 42,
                "record_counts": {
                    "gateway_transactions": len(transactions),
                    "merchant_orders": len(orders),
                    "settlement_batches": len(settlements),
                    "ledger_entries": len(ledgers),
                    "dispute_events": len(disputes),
                    "total_operational_records": (
                        len(transactions) + len(orders) + len(settlements) + len(ledgers) + len(disputes)
                    ),
                    "exceptions_detected": len(exceptions),
                    "ground_truth_cases": len(ground_truth),
                },
                "finance_ops_loop_status": {
                    "total_exceptions": len(exceptions),
                    "closed_and_verified": sum(1 for e in exceptions if e.state in ["VERIFIED_CLOSED", "REMEDIATED"]),
                    "unresolved_or_escalated": sum(1 for e in exceptions if e.state not in ["VERIFIED_CLOSED", "REMEDIATED"]),
                },
            },
            "gateway_transactions": [
                {
                    "id": t.id,
                    "payment_id": t.payment_id,
                    "merchant_id": t.merchant_id,
                    "amount_paise": t.amount,
                    "amount_inr": round(t.amount / 100.0, 2),
                    "currency": t.currency,
                    "status": t.status,
                    "method": t.method,
                    "card_type": t.card_type,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                }
                for t in transactions
            ],
            "merchant_orders": [
                {
                    "id": o.id,
                    "order_id": o.order_id,
                    "payment_id_reference": o.payment_id_reference,
                    "customer_id": o.customer_id,
                    "fulfillment_status": o.fulfillment_status,
                    "order_amount_paise": o.order_amount,
                    "order_amount_inr": round(o.order_amount / 100.0, 2),
                    "created_at": o.created_at.isoformat() if o.created_at else None,
                }
                for o in orders
            ],
            "settlement_batches": [
                {
                    "id": s.id,
                    "settlement_id": s.settlement_id,
                    "payment_id": s.payment_id,
                    "acquirer_id": s.acquirer_id,
                    "net_amount_paise": s.net_amount,
                    "net_amount_inr": round(s.net_amount / 100.0, 2),
                    "interchange_fee_paise": s.interchange_fee_deducted,
                    "tax_paise": s.tax_deducted,
                    "clearing_timestamp": s.clearing_timestamp.isoformat() if s.clearing_timestamp else None,
                }
                for s in settlements
            ],
            "dispute_events": [
                {
                    "id": d.id,
                    "event_id": d.event_id,
                    "payment_id": d.payment_id,
                    "event_type": d.event_type,
                    "amount_paise": d.amount,
                    "amount_inr": round(d.amount / 100.0, 2),
                    "reason_code": d.reason_code,
                    "timestamp": d.timestamp.isoformat() if d.timestamp else None,
                }
                for d in disputes
            ],
            "ledger_entries": [
                {
                    "id": l.id,
                    "ledger_id": l.ledger_id,
                    "transaction_id": l.transaction_id,
                    "account_id": l.account_id,
                    "debit_paise": l.debit,
                    "credit_paise": l.credit,
                    "balance_after_paise": l.balance_after,
                    "entry_type": l.entry_type,
                    "timestamp": l.timestamp.isoformat() if l.timestamp else None,
                }
                for l in ledgers
            ],
            "exceptions_detected": [
                {
                    "exception_id": e.exception_id,
                    "exception_type": e.exception_type,
                    "severity": e.severity,
                    "state": e.state,
                    "exposure_paise": e.exposure,
                    "exposure_inr": round(e.exposure / 100.0, 2),
                    "primary_payment_id": e.primary_payment_id,
                    "primary_order_id": e.primary_order_id,
                    "description": e.description,
                    "detected_at": e.detected_at.isoformat() if e.detected_at else None,
                }
                for e in exceptions
            ],
        }

        json_file = out_path / "nodexa_synthetic_dataset.json"
        with open(json_file, mode="w", encoding="utf-8") as f:
            json.dump(json_data, f, indent=2)

        print(f"Successfully exported {len(transactions)} gateway transactions to:")
        print(f" - CSV:  {csv_file} ({os.path.getsize(csv_file)} bytes)")
        print(f" - JSON: {json_file} ({os.path.getsize(json_file)} bytes)")

        return {
            "csv_path": str(csv_file),
            "json_path": str(json_file),
            "gateway_transactions_count": len(transactions),
            "orders_count": len(orders),
            "settlement_batches_count": len(settlements),
            "ledger_entries_count": len(ledgers),
            "dispute_events_count": len(disputes),
            "total_records": len(transactions) + len(orders) + len(settlements) + len(ledgers) + len(disputes),
            "exceptions_count": len(exceptions),
        }

    finally:
        db.close()


if __name__ == "__main__":
    export_canonical_dataset()
