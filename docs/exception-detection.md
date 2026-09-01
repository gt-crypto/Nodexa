# Nodal Sentinel - Deterministic Exception Detection & Lifecycle Engine

This document specifies the architecture, deterministic anomaly classifiers, correlation algorithms, exact integer exposure formulas, deduplication mechanisms, state machine lifecycles, and audit logging for **Prompt 4 — Deterministic Exception Detection & Exception Lifecycle Engine**.

---

## 1. Core Architectural Principle: Facts to Exceptions

The exception detection layer serves as the deterministic bridge between low-level financial control assertions and structured business exceptions:

> **Controls establish deterministic facts.**  
> **Exception detection converts correlated facts into deterministic exception records.**  
> **AI investigation comes after detection and is NOT part of this phase.**

- Detection is purely rule-based and operates strictly over operational database records (`gateway_transactions`, `merchant_orders`, `bank_settlement_batches`, `dispute_refund_events`, `nodal_ledger`) and Prompt 3 control results.
- Zero LLM or AI involvement in detection, exposure calculation, severity assignment, or state tracking.
- **Zero Ground-Truth Leakage**: The operational exception detector has no dependency on `evaluation_ground_truth`.

---

## 2. Detection Architecture & Flow

```
OPERATIONAL FINANCIAL TABLES & REPOSITORIES
                 │
                 ▼
DETERMINISTIC CONTROLS & RECONCILIATION (Prompt 3)
   - Financial Invariants
   - SLA Window Evaluation
   - Partial Settlement Aggregation
   - Identifier Matching
                 │
                 ▼
ENTITY CORRELATOR (correlator.py)
   - Groups operational records and control findings by primary financial entity
                 │
                 ▼
MVP EXCEPTION CLASSIFIERS (classifiers.py)
   - Ghost Settlement Classifier
   - Refund + Chargeback Double-Dip Classifier
   - Settlement SLA Breach Classifier
   - Legitimate Partial Settlement Classifier
   - Missing Settlement Classifier
   - Unallocated Settlement Classifier
   - Legitimate Timing Exception Classifier
                 │
                 ▼
DETERMINISTIC EXPOSURE & SEVERITY (exposure.py / severity.py)
   - Exact integer minor-unit calculation
   - Materiality threshold classification
                 │
                 ▼
LIFECYCLE & AUDIT PERSISTENCE (lifecycle.py / service.py)
   - Idempotent Deduplication (EXC-{TYPE}-{ID})
   - State Transition: None -> DETECTED (actor_type = SYSTEM)
   - Affected Records Linkage (exception_affected_records)
   - Immutable Audit Event: EXCEPTION_DETECTED
```

---

## 3. Supported MVP Exception Families

All detected exceptions strictly follow the PRD top-level taxonomy defined in `ExceptionType`:

### 1. `GHOST_SETTLEMENT`
- **Deterministic Detection Rule**: Gateway payment status is `FAILED` OR associated merchant order is `CANCELLED`, while downstream acquirer `BankSettlementBatch` records or `NodalLedgerEntry` credits exist.
- **Exposure Formula**: Sum of contradictory settlement net amounts credited to the account.
- **Severity**: `CRITICAL` if exposure $\ge$ ₹30,000 else `HIGH`.

### 2. `REFUND_CHARGEBACK_DOUBLE_DIP`
- **Deterministic Detection Rule**: Payment is captured and has both a `REFUND` event and a `CHARGEBACK` event in `dispute_refund_events`, causing dual ledger debits that exceed the initial settlement credit.
- **Exposure Formula**: Minor-unit sum of the overlapping chargeback event(s).
- **Severity**: `CRITICAL` if exposure $\ge$ ₹30,000 else `HIGH`.

### 3. `SETTLEMENT_SLA_BREACH`
- **Deterministic Detection Rule**: Captured transaction where Prompt 3 settlement SLA evaluation classified timing as `SLA_BREACH` (clearing timestamp exceeded the expected SLA deadline calculated from the next valid processing window). Excludes `LATE_BUT_VALID` calendar timings.
- **Exposure Formula**: Full payment gross amount pending beyond SLA.
- **Severity**: `HIGH` if exposure $\ge$ ₹20,000 else `MEDIUM`.

### 4. `PARTIAL_SETTLEMENT` (Legitimate Observability Case)
- **Deterministic Detection Rule**: Payment is captured and distributed across multiple settlement batches ($n > 1$) whose gross sum exactly matches the payment amount (`PARTIAL_SETTLEMENT_COMPLETE`).
- **Exposure Formula**: `0` minor units (Clean legitimate split).
- **Severity**: `LOW` (Persisted purely as a legitimate operational observation).

### 5. `MISSING_UNALLOCATED_SETTLEMENT`
Supports two deterministic sub-classifications:
- **`MISSING_SETTLEMENT`**: Captured transaction with zero downstream bank settlement batches past the SLA deadline.
  - **Exposure Formula**: Expected payment gross amount.
  - **Severity**: `HIGH`.
- **`UNALLOCATED_SETTLEMENT`**: Inflow `BankSettlementBatch` with `payment_id = NULL` (or ambiguous match) that cannot be mapped to any gateway transaction.
  - **Exposure Formula**: Net amount of the unallocated settlement batch.
  - **Severity**: `HIGH` if exposure $\ge$ ₹20,000 else `MEDIUM`.

### 6. `LEGITIMATE_TIMING_EXCEPTION` (Legitimate Observability Case)
- **Deterministic Detection Rule**: Payment captured near a weekend or after the daily 18:00 UTC cutoff that cleared within the next valid processing window (`LATE_BUT_VALID`).
- **Exposure Formula**: `0` minor units (Clean calendar timing).
- **Severity**: `LOW` (Persisted purely as a legitimate operational observation).

---

## 4. Financial Precision: Integer Minor Units

All exposure values are calculated and stored strictly as **integer minor units** (`BigInteger`, e.g. paisa for INR: `₹45,000.00` = `4,500,000` minor units).

- Legitimate cases (`PARTIAL_SETTLEMENT`, `LEGITIMATE_TIMING_EXCEPTION`) always have `exposure = 0`.
- Zero floating-point arithmetic.

---

## 5. Correlation & Deduplication

- **Entity Grouping**: `correlate_operational_entities()` links payments, orders, settlements, disputes, and ledger entries by primary identifiers to ensure that multi-source findings for a single transaction do not produce fragmented exceptions.
- **Deduplication Key**: Generated deterministically:
  $$\text{Deduplication Key} = \text{"EXC-" } + \text{Type/Subtype} + \text{"-" } + \text{EntityID}$$
  Examples: `EXC-GHOST-PAY-000001`, `EXC-UNALLOCATED-SET-000008`, `EXC-SLA_BREACH-PAY-000006`.
- **Idempotency Guarantee**: Executing `POST /exceptions/detect` multiple times on the same dataset updates existing records in-place without creating duplicate rows, duplicate state transitions, or duplicate audit records.

---

## 6. Exception Lifecycle & State Transitions

- All newly detected exceptions enter the state machine initialized at:
  $$\text{State} = \text{DETECTED}$$
- An initial immutable `ExceptionStateTransition` record is created:
  - `from_state`: `"NONE"`
  - `to_state`: `"DETECTED"`
  - `actor_type`: `"SYSTEM"`
  - `actor_id`: `"deterministic_detection_engine"`
  - `reason`: `"Deterministic exception detected from operational controls."`
- The detector **never** automatically advances an exception beyond `DETECTED`. AI investigation in future prompts will be responsible for transitioning `DETECTED` $\rightarrow$ `INVESTIGATING`.

---

## 7. Audit Trail Logging

Every detection run logs tamper-evident records to `audit_events` via `AuditRepository`:
- `event_type`: `"EXCEPTION_DETECTED"`
- `actor_type`: `"SYSTEM"`
- `event_summary`: Human-readable summary of detection.
- `event_payload`: JSON payload capturing `exception_id`, `exception_type`, `sub_type`, `severity`, `exposure`, `primary_payment_id`, and structured `evidence` items.

---

## 8. REST API Specifications

### 1. `POST /exceptions/detect`
Executes deterministic detection and returns a consolidated `DetectionReportResponse`:
```json
{
  "status": "success",
  "dataset_id": "ds_seed42_7f8a9b1c2d3e",
  "evaluated_at": "2026-08-31T22:00:00Z",
  "controls_run_count": 240,
  "findings_count": 8,
  "total_detected_count": 12,
  "new_exception_count": 12,
  "existing_exception_count": 0,
  "legitimate_case_count": 4,
  "total_exposure": 32500000,
  "severity_breakdown": {
    "LOW": 4,
    "MEDIUM": 2,
    "HIGH": 4,
    "CRITICAL": 2
  },
  "exception_type_breakdown": {
    "GHOST_SETTLEMENT": 2,
    "REFUND_CHARGEBACK_DOUBLE_DIP": 2,
    "SETTLEMENT_SLA_BREACH": 2,
    "PARTIAL_SETTLEMENT": 2,
    "MISSING_UNALLOCATED_SETTLEMENT": 4,
    "LEGITIMATE_TIMING_EXCEPTION": 2
  },
  "exceptions": [...]
}
```

### 2. `GET /exceptions`
Lists persisted exceptions with filtering (`state`, `exception_type`, `severity`, `min_exposure`, `limit`, `offset`).

### 3. `GET /exceptions/{exception_id}`
Returns full details for a single exception including `affected_records`, `transitions`, and `audit_events`.
