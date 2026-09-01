# Nodal Sentinel - Synthetic Financial Dataset Generator

This document details the architecture, scenario definitions, reproducibility mechanics, ground-truth isolation, and generation procedures for the **Nodal Sentinel Synthetic Financial Dataset Generator**.

---

## 1. Core Principle: 100% Synthetic Data

Nodal Sentinel MVP operates exclusively on synthetic financial data. No live payment gateway credentials, production bank APIs, or real customer/merchant financial records are accessed.

---

## 2. Generator Architecture

The generator is structured under `backend/data/`:

```
backend/data/
├── generator/
│   ├── config.py             # GeneratorConfig with configurable counts & SLA windows
│   ├── ids.py                # Deterministic IdGenerator for business identifiers
│   ├── context.py            # GenerationContext managing PRNG state & entity accumulators
│   ├── normal_transactions.py# Realistic normal payment lifecycle generator
│   └── service.py            # Main generate_dataset orchestrator & repository persistence
└── scenarios/
    ├── ghost_settlement.py   # Scenario 1: Ghost Settlement
    ├── refund_chargeback.py  # Scenario 2: Refund + Chargeback Double-Dip
    ├── sla_breach.py         # Scenario 3: Genuine Settlement SLA Breach
    ├── partial_settlement.py # Scenario 4: Legitimate Partial/Async Settlement
    ├── missing_unallocated.py# Scenario 5: Missing & Unallocated Settlements
    └── timing_exception.py   # Scenario 6: Legitimate Timing Exception
```

---

## 3. Deterministic Seed Reproducibility

- **Controlled Randomness**: The generator uses an isolated, instance-scoped pseudo-random number generator (`random.Random(seed)`).
- **Exact Idempotence**: Executing `generate_dataset(session, record_count=60, seed=42)` across any environment always produces the exact same payment IDs, order IDs, settlement batches, timestamps, monetary amounts, and ground-truth cases.
- **Dataset Metadata**: Each generation run records metadata in the `dataset_metadata` table (`dataset_id`, `dataset_version`, `seed`, `record_count`, `generated_at`, `description`).

---

## 4. Financial Precision: Integer Minor Units

All monetary values strictly use **integer minor units** (`BigInteger`):
- `₹1.00 = 100 minor units` (paisa).
- `₹45,000.00 = 4,500,000 minor units`.
- Zero floating-point drift ensures that reconciliation calculations remain mathematically exact.

---

## 5. Synthetic Identifier Formatting

Identifiers are generated sequentially and deterministically:
- Payments: `PAY-000001`
- Orders: `ORD-000001`
- Settlements: `SET-000001`
- Bank UTRs: `UTR-SYN-HDFC-000001`
- Dispute Events: `EVT-000001`
- Nodal Ledger: `LED-000001`
- Ground Truth Cases: `CASE-GHOST-0001`, `CASE-REFUND-CB-0001`, `CASE-SLA-0001`, etc.

---

## 6. Supported Scenarios & Ground Truth Specifications

### A. Normal Transactions (Baseline)
- Captures normal multi-stage lifecycles:
  1. `MerchantOrder` (FULFILLED)
  2. `GatewayTransaction` (CAPTURED)
  3. `BankSettlementBatch` (Clears in 4–18 hours)
  4. `NodalLedgerEntry` (Double-entry SETTLEMENT_CREDIT)
- Also generates clean failed payment attempts with no contradictory downstream bank entries, single normal refunds, and single chargebacks.

---

### B. Scenario 1 — Ghost Settlement
- **Planted Inconsistency**: Gateway payment is `FAILED` and Order is `CANCELLED`, yet an acquirer `BankSettlementBatch` credit exists and funds are posted to `NodalLedgerEntry`.
- **Ground Truth**:
  - `anomaly_type`: `GHOST_SETTLEMENT`
  - `expected_root_cause`: `"Gateway/order state indicates failure or cancellation while bank and nodal records show settlement funds."`
  - `expected_exposure`: `amount` (e.g. ₹45,000)
  - `expected_resolution_class`: `EVIDENCE_DISPUTE_PACKET`
  - `expected_verification_state`: `VERIFIED_CLOSED`

---

### C. Scenario 2 — Refund + Chargeback Double-Dip
- **Planted Inconsistency**: Payment is captured and settled. Merchant issues a full refund (`REFUND` event + ledger debit). Subsequently, an overlapping chargeback debit (`CHARGEBACK` event + dispute hold) appears for the same payment.
- **Ground Truth**:
  - `anomaly_type`: `REFUND_CHARGEBACK_DOUBLE_DIP`
  - `expected_root_cause`: `"Refund and chargeback financial liabilities overlap for the same payment."`
  - `expected_exposure`: `chargeback_amount`
  - `expected_resolution_class`: `RECOMMEND_ONLY`
  - `expected_verification_state`: `VERIFIED_CLOSED`

---

### D. Scenario 3 — Genuine Settlement SLA Breach
- **Planted Inconsistency**: Captured payment has a settlement clearing timestamp delayed by >54 hours (when synthetic SLA is 24 hours).
- **Ground Truth**:
  - `anomaly_type`: `SETTLEMENT_SLA_BREACH`
  - `expected_root_cause`: `"Captured payment has no valid settlement within the configured synthetic processing window."`
  - `expected_exposure`: `amount`
  - `expected_resolution_class`: `ESCALATE`
  - `expected_verification_state`: `FAILED_ESCALATED`

---

### E. Scenario 4 — Legitimate Partial / Asynchronous Settlement
- **Structural Integrity**: Payment of ₹10,000 is settled in three separate batches: ₹4,000 + ₹3,000 + ₹3,000.
- **Ground Truth**:
  - `anomaly_type`: `PARTIAL_SETTLEMENT`
  - `expected_root_cause`: `"Settlement is legitimately distributed across multiple records whose aggregate matches the payment."`
  - `expected_exposure`: `0` (Clean legitimate case; zero anomaly liability)
  - `expected_resolution_class`: `NO_ACTION`
  - `expected_verification_state`: `NO_ACTION_REQUIRED`

---

### F. Scenario 5 — Missing & Unallocated Settlements
- **Missing Settlement (5A)**: Captured payment exists with zero downstream settlement batches.
  - `expected_root_cause`: `"Captured payment has no valid downstream settlement."`
  - `expected_exposure`: `amount`
  - `expected_resolution_class`: `ESCALATE`
- **Unallocated Settlement (5B)**: Bank settlement batch exists with `payment_id = NULL` and an unmapped reference string (`RAW-UNMAPPED-ORPHAN-...`).
  - `expected_root_cause`: `"Bank inflow exists but cannot be cleanly associated with a payment."`
  - `expected_exposure`: `net_amount`
  - `expected_resolution_class`: `HUMAN_APPROVAL_REQUIRED`

---

### G. Scenario 6 — Legitimate Timing Exception
- **Structural Integrity**: Payment captured Friday evening after the 18:00 cutoff. Settlement clears Monday morning during the next valid processing window.
- **Ground Truth**:
  - `anomaly_type`: `LEGITIMATE_TIMING_EXCEPTION`
  - `expected_root_cause`: `"Settlement occurs within the configured next-valid-processing window despite appearing late."`
  - `expected_exposure`: `0`
  - `expected_resolution_class`: `NO_ACTION`
  - `expected_verification_state`: `NO_ACTION_REQUIRED`

---

## 7. Ground Truth Isolation

All benchmark ground truth cases are stored exclusively in the `evaluation_ground_truth` table using `GroundTruthRepository`. They are isolated from operational financial source repositories (`FinancialSourceRepository`) so that future AI investigation agents have zero data leakage.

---

## 8. Generation Usage & Execution

### Python API
```python
from backend.models.database import SessionLocal
from backend.data.generator.service import generate_dataset

with SessionLocal() as session:
    summary = generate_dataset(session=session, record_count=60, seed=42)
    session.commit()
    print("Generated Dataset ID:", summary["dataset_id"])
```

### HTTP Endpoint
```bash
POST /data/generate
Content-Type: application/json

{
  "record_count": 60,
  "seed": 42
}
```

### Running Dataset Tests
```powershell
pytest backend/tests/test_generator.py -v
```
