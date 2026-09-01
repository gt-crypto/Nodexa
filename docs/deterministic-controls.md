# Nodal Sentinel - Deterministic Financial Control & Nodal Health Engine

This document specifies the architecture, mathematical formulations, monetary precision guarantees, SLA processing calendar rules, invariant verifications, identifier matching algorithms, and control result models for **Prompt 3 — Deterministic Nodal Health & Financial Control Engine**.

---

## 1. Core Principle: Deterministic Controls First, AI Reasoning Later

The primary architectural tenet of Nodal Sentinel is strict separation of concerns:

> **Deterministic controls produce immutable facts and evidence.**  
> **AI investigation will later interpret distributed, temporal, or ambiguous facts.**

- Monetary balances, variance calculations, double-entry integrity, settlement SLA timers, and duplicate record detections are executed **100% deterministically in pure Python**.
- The Large Language Model (LLM) is **never** involved in mathematical arithmetic, ledger balance evaluations, or financial state validation.
- All control outputs are structured as verified deterministic facts with source-attributed evidence items.

---

## 2. Architecture & Directory Organization

The deterministic control layer is structured into modular packages under `backend/`:

```
backend/
├── controls/
│   ├── control_result.py     # ControlResult, ControlStatus, EvidenceItem models
│   ├── invariants.py         # Financial & double-entry ledger invariants
│   ├── settlement_sla.py     # Processing calendar, cutoffs & SLA timers
│   ├── nodal_health.py       # Expected balance, actual balance & throughput
│   ├── engine.py             # ControlEngine orchestrator
│   └── state_machine.py      # Exception state machine transition validator
├── reconciliation/
│   ├── matching.py           # Multi-source identifier matching service
│   ├── amounts.py            # Exact integer monetary amount validations
│   ├── settlements.py        # Multi-tranche settlement aggregation
│   ├── duplicates.py         # Duplicate event and ledger posting detector
│   └── service.py            # ReconciliationService (Payment/Settlement/Account)
└── api/
    ├── health.py             # General system health endpoint (GET /health)
    └── nodal.py              # Real-time nodal account health API (GET /health/nodal)
```

---

## 3. Financial Precision: Integer Minor Units

All monetary values are calculated and stored strictly using **integer minor units**:

- **Currency**: ISO 4217 code (default: `"INR"`).
- **Scale**: `1 INR = 100 minor units` (paisa).
- **Examples**:
  - `₹10.00` = `1,000` minor units.
  - `₹10,000.00` = `1,000,000` minor units.
  - `₹45,000.00` = `4,500,000` minor units.
- **Precision Guarantee**: Complete elimination of IEEE-754 binary floating-point drift. All balance and variance additions, subtractions, and aggregations preserve exact integer values.

---

## 4. Expected Nodal Balance Formulation

Expected nodal balance is derived deterministically from operational business source events:

$$\text{Expected Inflows} = \sum \text{net\_amount}(\text{BankSettlementBatches for Valid Captured \& Fulfilled Payments})$$

$$\text{Expected Outflows} = \sum \text{amount}(\text{DisputeRefundEvents for Valid Captured Payments})$$

$$\text{Expected Nodal Balance} = \text{Expected Inflows} - \text{Expected Outflows}$$

### Breakdown:
1. **Valid Captured Inflows**: Payments marked `CAPTURED` with corresponding fulfilled merchant orders whose bank settlement batches have cleared. (Excludes ghost settlements on failed payments).
2. **Valid Dispute Outflows**: Customer refunds (`REFUND` event) and chargeback dispute holds (`CHARGEBACK` event) issued against legitimate payments.

---

## 5. Actual Nodal Balance & Variance

Actual nodal balance is derived directly from the source of truth ledger (`nodal_ledger`):

$$\text{Actual Nodal Balance} = \text{Latest } \text{balance\_after}(\text{nodal\_ledger for account})$$

$$\text{Ledger Net Change} = \sum \text{credits} - \sum \text{debits}$$

### Internal Consistency Assertion:
$$\text{Ledger Net Change} \equiv \text{Latest } \text{balance\_after}$$

### Balance Variance:
$$\text{Variance} = \text{Actual Nodal Balance} - \text{Expected Nodal Balance}$$

$$\text{Absolute Variance} = |\text{Variance}|$$

When a **Ghost Settlement** occurs (where funds clear for a failed transaction), Actual Balance includes the erroneous credit while Expected Balance excludes it, producing a positive balance variance equal to the ghost amount.

---

## 6. Nodal Health Status & Configurable Thresholds

The overall nodal health status is deterministically classified based on configurable financial thresholds:

| Status | Conditions |
| :--- | :--- |
| **`HEALTHY`** | Zero critical control failures, zero warning failures, and $\text{Absolute Variance} < \text{warning\_threshold}$. |
| **`WARNING`** | Non-critical control failures present, unresolved SLA breaches, or $\text{warning\_threshold} \le \text{Absolute Variance} < \text{critical\_threshold}$. |
| **`CRITICAL`** | Any critical invariant/control failure, ledger progression mismatch, or $\text{Absolute Variance} \ge \text{critical\_threshold}$. |

### Default Synthetic Thresholds (`NodalHealthConfig`):
- `warning_variance_threshold`: `100,000` minor units (₹1,000.00).
- `critical_variance_threshold`: `5,000,000` minor units (₹50,000.00).
- `max_critical_failures_allowed`: `0`.

---

## 7. Settlement Throughput Metrics

Operational synthetic throughput is computed deterministically:

1. **Total Captured Payments**: Count and minor-unit sum of all captured gateway transactions.
2. **Total Settled Payments**: Count and gross minor-unit sum of captured payments having full settlement clearance.
3. **Total Unsettled Payments**: Count and gross minor-unit sum of captured payments with missing or partial settlement clearance.
4. **Settlement Completion Ratio**: $\frac{\text{Total Settled Count}}{\text{Total Captured Count}}$ (bounded $[0.0000, 1.0000]$).
5. **Settlement Batches Count & Net Sum**: Total count and net minor-unit sum across all bank clearing batches.

---

## 8. Settlement SLA & Processing Windows

### Calendar & Processing Hours
- **Processing Window**: `09:00:00` to `18:00:00` UTC on business days (Mon–Fri).
- **Daily Cutoff**: `18:00:00` UTC.
- **Non-Processing Periods**: Saturdays, Sundays, and weekday evenings (after 18:00 UTC).
- **Next Valid Processing Window Start**:
  - Friday after 18:00 UTC $\rightarrow$ Monday 09:00:00 UTC.
  - Weekday after 18:00 UTC $\rightarrow$ Next business day 09:00:00 UTC.
  - Saturday / Sunday $\rightarrow$ Next Monday 09:00:00 UTC.

### SLA Timing Evaluation Logic
$$\text{Effective Start Time} = \text{GetNextValidProcessingWindowStart}(\text{Payment Created At})$$

$$\text{Expected SLA Deadline} = \text{Effective Start Time} + \text{SLA Hours (e.g. 24h)}$$

### Timing Classifications:
1. **`WITHIN_SLA`**: Raw elapsed clearing time $\le 24$ hours.
2. **`LATE_BUT_VALID`**: Raw elapsed clearing time $> 24$ hours (e.g., weekend/post-cutoff transaction), but clearing timestamp $\le \text{Expected SLA Deadline}$.
3. **`SLA_BREACH`**: Clearing timestamp exceeds the expected SLA deadline.
4. **`MISSING`**: Captured transaction has zero settlement batches and current timestamp $> \text{Expected SLA Deadline}$.
5. **`NOT_APPLICABLE`**: Non-captured or failed transaction.

---

## 9. Multi-Tranche Partial Settlement Aggregation

Payments may be settled asynchronously across multiple bank clearing batches:

$$\text{Total Gross Settled} = \sum_{i=1}^{n} (\text{net\_amount}_i + \text{interchange\_fee}_i + \text{tax\_deducted}_i)$$

- **`FULL_SETTLEMENT`**: Exactly 1 batch where $\text{Total Gross} = \text{Payment Amount}$.
- **`PARTIAL_SETTLEMENT_COMPLETE`**: $n > 1$ batches where $\sum \text{Gross} = \text{Payment Amount}$ (e.g., ₹4,000 + ₹3,000 + ₹3,000 = ₹10,000). Treated as **financially reconciled (`PASS`)**.
- **`UNDER_SETTLED`**: $\sum \text{Gross} < \text{Payment Amount}$.
- **`OVER_SETTLED`**: $\sum \text{Gross} > \text{Payment Amount}$.

---

## 10. Exact Identifier Matching

Provides cross-source entity linkage with deterministic match classifications:

| Source Identifier | Target Entity | Match Statuses |
| :--- | :--- | :--- |
| `payment_id` | `merchant_orders` | `EXACT_MATCH`, `NO_MATCH`, `MULTIPLE_MATCHES` |
| `payment_id` | `bank_settlement_batches` | `EXACT_MATCH`, `NO_MATCH`, `MULTIPLE_MATCHES`, `AMBIGUOUS_MATCH` |
| `settlement_id` | `gateway_transactions` | `EXACT_MATCH`, `NO_MATCH`, `AMBIGUOUS_MATCH` |

---

## 11. Amount Validation Rules

Deterministic cross-record amount assertions:

1. **Gateway vs Order**: `payment.amount == order.order_amount`.
2. **Settlement Deduction Consistency**: `batch.net_amount + batch.interchange_fee_deducted + batch.tax_deducted == calculated_gross`.
3. **Payment vs Settlement Gross**: `payment.amount == sum(batch.gross_amount)`.
4. **Ledger vs Settlement Net**: `batch.net_amount == ledger.credit` (for `SETTLEMENT_CREDIT`).
5. **Ledger vs Dispute Outflow**: `dispute.amount == ledger.debit` (for `REFUND_DEBIT` / `DISPUTE_HOLD`).

---

## 12. Duplicate Event Detection

Identifies redundant or anomalous repeated financial records:

1. **Duplicate Settlements**: Same `settlement_id` or duplicate `utr_number` across multiple batches.
2. **Duplicate Disputes**: Multiple `REFUND` or `CHARGEBACK` events with identical amount on the same payment within a 1-hour window.
3. **Duplicate Ledger Postings**: Identical transaction ID, entry type, debit, and credit posted within a 2-minute window.

---

## 13. Financial Invariants

Mandatory assertions across operational records:

1. **Ledger Balance Progression**: $\text{Balance}_{i} = \text{Balance}_{i-1} + \text{Credit}_i - \text{Debit}_i$ for all chronological entries.
2. **Debit/Credit Sanity**: No entry may have simultaneous $\text{debit} > 0$ and $\text{credit} > 0$.
3. **Non-Negative Constraints**: All monetary fields ($\text{amount}, \text{net}, \text{fee}, \text{tax}, \text{debit}, \text{credit}, \text{balance\_after}$) must be $\ge 0$.
4. **Currency Consistency**: All records must match standard system ISO currency (`"INR"`).
5. **Reference Integrity**: Non-null `transaction_id` in `nodal_ledger` must resolve to an existing `payment_id` in `gateway_transactions`.

---

## 14. Structured Control Result Model

Every control outputs a structured `ControlResult`:

```python
@dataclass
class ControlResult:
    control_id: str
    control_name: str
    status: ControlStatus        # PASS | FAIL | WARNING | NOT_APPLICABLE
    severity: Optional[str]      # LOW | MEDIUM | HIGH | CRITICAL | None
    affected_record_ids: List[str]
    calculated_values: Dict[str, Any]
    expected_values: Dict[str, Any]
    actual_values: Dict[str, Any]
    evidence: List[EvidenceItem]
    rule: str
    evaluated_at: datetime
```

### Evidence Structure:
```python
@dataclass
class EvidenceItem:
    source: str         # Table name (e.g. 'bank_settlement_batches')
    record_id: str      # Business ID (e.g. 'SET-000012')
    field: str          # Attribute (e.g. 'net_amount')
    value: Any          # Exact value (e.g. 4500000)
    comparison: str     # Comparison statement
```

---

## 15. Nodal Health API

### `GET /health/nodal`
Returns real-time account health, balance variance, and throughput metrics:

```json
{
  "overall_status": "CRITICAL",
  "account_id": "nodal_escrow_main",
  "expected_balance": 85000000,
  "actual_balance": 89500000,
  "variance": 4500000,
  "absolute_variance": 4500000,
  "settlement_throughput": {
    "total_captured_payments_count": 48,
    "total_captured_amount": 92000000,
    "total_settled_payments_count": 42,
    "total_settled_amount": 85000000,
    "total_unsettled_payments_count": 6,
    "total_unsettled_amount": 7000000,
    "settlement_completion_ratio": 0.875,
    "settlement_batches_count": 46,
    "total_net_settlement_amount": 88000000
  },
  "settlement_sla_health": {
    "within_sla_count": 42,
    "late_but_valid_count": 2,
    "sla_breach_count": 2,
    "not_applicable_count": 12
  },
  "open_exception_count": 0,
  "total_exposure": 0,
  "controls_summary": {
    "total_controls_evaluated": 240,
    "passed_count": 228,
    "warning_count": 4,
    "failed_count": 8,
    "not_applicable_count": 0
  },
  "reasons": [
    "Balance variance 4500000 minor units exceeds warning threshold (100000)."
  ],
  "evaluated_at": "2026-08-31T21:30:00Z"
}
```

*Note: `open_exception_count` and `total_exposure` report honest zero values until the exception detection and management engine is activated in subsequent prompts.*
