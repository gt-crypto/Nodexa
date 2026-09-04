# Nodexa Synthetic Operational Dataset & Finance-Ops Loop

## 1. Overview & Buildathon Compliance

This repository directory contains the canonical **50+ record synthetic financial batch** for **Nodexa (AI Finance Controller)**, fulfilling the Razorpay AI Finance Controller buildathon requirement:

> *"Build an agent that closes one finance-ops loop across a 50+ record batch of synthetic data, reporting its match rate and the exceptions it could not resolve."*

- **Dataset File Formats**:
  - `nodexa_synthetic_dataset.csv`: Flat tabular operational ledger for quick audit, spreadsheet inspection, and reconciliation testing.
  - `nodexa_synthetic_dataset.json`: Complete relational dataset containing relational objects across all 5 financial source systems (Gateway, Orders, Bank Settlements, Disputes, and Nodal Ledger).
- **Batch Seed**: `Seed 42` (deterministic pseudo-random generation with invariant guarantees).
- **Gateway Transactions**: **60 records** (strictly $\ge 50$ requirement).
- **Total Operational Records**: **269 records** across 5 distinct financial systems.

---

## 2. Dataset Record Count Breakdown

| Record Type | Count | Description | Primary Key / Foreign Key Link |
| :--- | :---: | :--- | :--- |
| **Gateway Transactions** | **60** | Payment attempts at the payment gateway | `payment_id` (`PAY-000001` - `PAY-000060`) |
| **Merchant Orders** | **60** | Merchant e-commerce order fulfillment state | `order_id` $\leftrightarrow$ `payment_id_reference` |
| **Bank Settlement Batches** | **63** | Acquirer clearing and settlement batches | `settlement_id` $\leftrightarrow$ `payment_id` |
| **Nodal Ledger Entries** | **76** | Double-entry nodal escrow ledger postings | `ledger_id` $\leftrightarrow$ `transaction_id` |
| **Dispute & Refund Events** | **13** | Chargebacks, reversals, and customer refunds | `event_id` $\leftrightarrow$ `payment_id` |
| **Total Operational Records** | **272** | **Full financial pipeline volume** | — |

---

## 3. Data Dictionary (`nodexa_synthetic_dataset.csv`)

| Column Name | Type | Description |
| :--- | :--- | :--- |
| `payment_id` | `String` | Unique gateway transaction identifier (`PAY-000001` to `PAY-000060`). |
| `merchant_id` | `String` | Merchant identifier (e.g., `mer_retail_kart`, `mer_fashion_hub`, `mer_tech_gadgets`). |
| `order_id` | `String` | Associated e-commerce merchant order identifier (`ORD-000001` to `ORD-000060`). |
| `payment_method` | `String` | Payment rail used (`CARD`, `UPI`, `NETBANKING`). |
| `gateway_status` | `String` | Gateway authorization status (`CAPTURED`, `FAILED`, `DISPUTED`, `REFUNDED`). |
| `order_fulfillment` | `String` | Merchant order fulfillment state (`FULFILLED`, `CANCELLED`). |
| `amount_paise` | `Integer` | Gross payment amount in Indian Paise (minor currency units). |
| `amount_inr` | `Float` | Gross payment amount formatted in INR (`amount_paise / 100`). |
| `order_amount_paise`| `Integer` | Merchant order amount in Indian Paise. |
| `order_amount_inr` | `Float` | Merchant order amount formatted in INR. |
| `settlement_count` | `Integer` | Number of bank settlement batch lines matched to this payment. |
| `settled_net_amount_inr` | `Float` | Net settlement amount credited by bank in INR. |
| `interchange_fee_inr` | `Float` | Interchange / processing fee deducted by acquirer. |
| `tax_inr` | `Float` | GST/service tax deducted on processing fee. |
| `dispute_event_count` | `Integer` | Number of dispute, refund, or reversal events attached. |
| `ledger_entry_count` | `Integer` | Number of double-entry nodal ledger postings. |
| `is_anomalous` | `Boolean` | `TRUE` if transaction triggered an invariant control check; `FALSE` if clean. |
| `anomaly_type` | `String` | Exception category (or `NORMAL` if reconciled). |
| `severity` | `String` | Risk severity level (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`, `NONE`). |
| `finance_ops_state` | `String` | State in the finance-ops loop (`DETECTED`, `INVESTIGATED`, `ACTION_PLANNED`, `APPROVED`, `REMEDIATED`, `VERIFIED_CLOSED`, or `RECONCILED`). |
| `exposure_inr` | `Float` | Outstanding nodal account exposure in INR. |
| `created_at` | `DateTime` | ISO-8601 transaction timestamp. |

---

## 4. Anomaly Taxonomy & Invariant Checks

The synthetic batch includes **14 canonical anomalous cases** designed to trigger strict financial invariant controls:

| Scenario / Anomaly Type | Case Count | Violated Invariant & Operational Pathology |
| :--- | :---: | :--- |
| **GHOST_SETTLEMENT** | 2 | **Bank credited settlement for a failed transaction.** Gateway status is `FAILED` / order `CANCELLED`, but bank credited nodal account funds. |
| **REFUND_CHARGEBACK_DOUBLE_DIP**| 2 | **Concurrent refund and chargeback executed on the same transaction.** Customer received both a merchant refund and a bank chargeback reversal. |
| **SETTLEMENT_SLA_BREACH** | 2 | **Settlement delay exceeded contractual $T+2$ window.** Captured transaction remained un-cleared past regulatory SLA. |
| **PARTIAL_SETTLEMENT** | 2 | **Settlement batch net amount differs from gateway captured amount minus fee.** Multiple tranches or unexplained residual variance. |
| **MISSING_UNALLOCATED_SETTLEMENT** | 2 | **Bank settlement record exists with invalid or missing payment reference.** Unclaimed funds sitting in nodal buffer. |
| **LEGITIMATE_TIMING_EXCEPTION** | 2 | **Valid transit delay across weekend/clearing cutoff.** Invariant triggers alert, but investigation safely confirms normal in-flight transit. |
| **FEE_CALCULATION_DRIFT / DEFICIT** | 2 | **Acquirer deducted interchange fees exceeding contractual rate.** Fee drift causing erosion of nodal float balance. |

---

## 5. Finance-Ops Loop Execution & Unresolved Reporting

In accordance with buildathon specifications, Nodexa actively processes these records through its complete **Sense $\rightarrow$ Investigate $\rightarrow$ Assess $\rightarrow$ Gate $\rightarrow$ Remediate $\rightarrow$ Verify** loop:

### Closed Finance-Ops Loop:
- **Case**: `GHOST_SETTLEMENT` (`PAY-000001` / `exc_ghost_1`)
- **Action**: Safe refund plan drafted to return erroneously credited bank funds.
- **Dual Approval**: Human-in-the-loop approved by dual controller policy (`controller-bob`).
- **Execution**: Automated reversal transaction dispatched to nodal ledger.
- **Verification**: 8 independent deterministic verifiers checked nodal balance, fee conservation, idempotency, and ledger balance.
- **Final Status**: `VERIFIED_CLOSED` (Exposure reduced from ₹50,986.29 to ₹0.00).

### Honestly Reported Unresolved Exceptions:
- **13 Exceptions Remain Unresolved / In-Flight / Escalated**:
  - 1 `GHOST_SETTLEMENT` (Escalated to Bank Ops for manual UTR trace).
  - 2 `REFUND_CHARGEBACK_DOUBLE_DIP` (Escalated to Risk & Merchant Dispute Desk).
  - 2 `SETTLEMENT_SLA_BREACH` (Logged for partner bank SLA penalty assessment).
  - 2 `PARTIAL_SETTLEMENT` (Waiting for next clearing cycle tranche).
  - 2 `MISSING_UNALLOCATED_SETTLEMENT` (Awaiting bank recon MT940 statement match).
  - 2 `LEGITIMATE_TIMING_EXCEPTION` (Marked cleared/timing harmless).
  - 2 `FEE_CALCULATION_DRIFT` (Escalated to Acquirer Account Manager for fee credit note).

**Loop Closure Rate**: **1 / 14 Closed & Verified (7.14%)**, with **13 / 14 (92.86%)** legitimately and transparently held in governance / human escalation state.

---

## 6. Strict Ground-Truth Isolation Architecture

Nodexa strictly separates the **Operational Financial Dataset** from the **Evaluation Ground Truth**:
1. Operational tables (`gateway_transactions`, `merchant_orders`, `bank_settlement_batches`, etc.) are the **only** sources queried by the Reconciliation Engine, Risk Assessor, AI Copilot, and Remediation Verifier.
2. Ground truth benchmark expectations are stored in the isolated `evaluation_ground_truth` table.
3. The AI agent has zero access to `evaluation_ground_truth`.
4. Only the `BenchmarkEvaluationService` reads both to compute mathematical Precision, Recall, F1 score, and Invariant Pass Rates.
