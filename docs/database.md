# Nodal Sentinel - Financial Data Model & Database Architecture

This document specifies the database foundation, financial entity models, state machine transitions, precision guarantees, and repository access layers for **Nodal Sentinel**.

---

## 1. Database Technology & Strategy

- **ORM & Dialect**: SQLAlchemy 2.x declarative mapping.
- **Engine**: SQLite for MVP with `PRAGMA foreign_keys = ON;` and WAL mode. Structured so PostgreSQL can be adopted seamlessly with minimal connection string adjustments.
- **Access Pattern**: Centralized database engine and session management in `backend/models/database.py` with repository-level access abstraction in `backend/services/repositories/`.
- **Zero Raw SQL Scattering**: All persistence operations pass through typed SQLAlchemy models and dedicated repositories.

---

## 2. Financial Precision: Integer Minor Units

> [!IMPORTANT]
> **No floating-point numbers are used for monetary storage or calculations.**
> All monetary values are represented as `BigInteger` integer minor units (e.g., paisa for INR, cents for USD).
> - Example: `₹1,500.50` is stored as `150050`.
> - This completely eliminates IEEE-754 binary floating-point drift and rounding anomalies in reconciliation.
> - ISO 4217 currency codes are stored alongside transaction amounts (defaulting to `"INR"`).

---

## 3. Schema Overview & Entity Models

### A. Financial Source Tables (Operational Layer)

1. **`gateway_transactions`**:
   - `id`: Internal autoincrement primary key.
   - `payment_id`: Indexed unique business identifier.
   - `merchant_id`: Indexed merchant identifier.
   - `amount`: `BigInteger` minor units.
   - `currency`: String(3), e.g., `"INR"`.
   - `status`: `AUTHORIZED`, `CAPTURED`, `FAILED`, `REFUNDED`, `PARTIALLY_REFUNDED`, `DISPUTED`.
   - `created_at`: Timestamp (UTC).
   - `method`: `CARD`, `UPI`, `NETBANKING`, `WALLET`.
   - `card_type`: `CREDIT`, `DEBIT`, or `NULL`.
   - `auth_code`, `error_code`: Gateway authorization and gateway error references.

2. **`bank_settlement_batches`**:
   - `id`: Internal primary key.
   - `settlement_id`: Indexed settlement identifier.
   - `utr_number`: Indexed bank UTR reference.
   - `acquirer_id`: Indexed bank/acquirer identifier.
   - `raw_payment_reference`: Acquirer raw reference string.
   - `payment_id`: Foreign key referencing `gateway_transactions.payment_id` (nullable to allow many-to-one / unallocated settlements).
   - `net_amount`, `interchange_fee_deducted`, `tax_deducted`: Minor integer units.
   - `clearing_timestamp`: UTC settlement clearing timestamp.

3. **`merchant_orders`**:
   - `id`: Internal primary key.
   - `order_id`: Indexed unique order identifier.
   - `payment_id_reference`: Foreign key referencing `gateway_transactions.payment_id` (nullable).
   - `customer_id`: Customer identifier.
   - `fulfillment_status`: `PENDING`, `FULFILLED`, `CANCELLED`, `RETURNED`.
   - `order_amount`: `BigInteger` minor units.

4. **`dispute_refund_events`**:
   - `id`: Internal primary key.
   - `event_id`: Indexed unique event identifier.
   - `payment_id`: Foreign key referencing `gateway_transactions.payment_id`.
   - `event_type`: `REFUND`, `REVERSAL`, `CHARGEBACK`, `CHARGEBACK_REVERSAL`.
   - `amount`: Minor integer units.
   - `timestamp`: UTC event timestamp.
   - `reason_code`: Gateway/card network chargeback or refund reason code.

5. **`nodal_ledger`**:
   - `id`: Internal primary key.
   - `ledger_id`: Indexed unique ledger entry identifier.
   - `transaction_id`: Foreign key referencing `gateway_transactions.payment_id` (nullable).
   - `account_id`: Escrow or nodal account identifier (`nodal_escrow_main`, `merchant_payable_escrow`).
   - `debit`, `credit`: Minor integer units (`0` if non-applicable).
   - `balance_after`: Snapshot balance after posting.
   - `timestamp`: UTC posting timestamp.
   - `entry_type`: `SETTLEMENT_CREDIT`, `SETTLEMENT_DEBIT`, `DISPUTE_HOLD`, `REFUND_DEBIT`, `FEE_DEBIT`, `REVERSAL`, `ADJUSTMENT`.
   - `reference`: Audit memo reference.

---

### B. Exception Management & State Machine

1. **`exceptions`**:
   - `exception_id`: Indexed unique business identifier.
   - `exception_type`: `GHOST_SETTLEMENT`, `REFUND_CHARGEBACK_DOUBLE_DIP`, `SETTLEMENT_SLA_BREACH`, `PARTIAL_SETTLEMENT`, `MISSING_UNALLOCATED_SETTLEMENT`, `LEGITIMATE_TIMING_EXCEPTION`, `UNKNOWN_DISCREPANCY`.
   - `severity`: `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
   - `state`: Lifecycle state (see State Machine below).
   - `exposure`: Minor integer units.
   - `confidence`: Decimal confidence score (0.0000 - 1.0000).
   - `primary_payment_id`, `primary_order_id`: Indexed business identifiers.
   - `detected_at`, `resolved_at`, `created_at`, `updated_at`: UTC timestamps.

2. **`exception_state_transitions`**:
   - Immutable record of every state transition.
   - `transition_id`, `exception_id`, `from_state`, `to_state`, `timestamp`, `reason`, `actor_type` (`SYSTEM`, `AI_AGENT`, `FINANCE_CONTROLLER`), `actor_id`.

3. **`exception_affected_records`**:
   - Many-to-many link table associating multiple payments, orders, settlements, disputes, and ledger entries with an exception.

---

### C. Investigation, Remediation, Verification & Audit

1. **`investigation_runs`**:
   - `investigation_id`, `exception_id`, `status` (`CREATED`, `RUNNING`, `COMPLETED`, `FAILED`), `started_at`, `completed_at`, `agent_version`, `final_classification`, `root_cause`, `confidence`, `recommended_action`, `human_approval_required`, `error_info`.

2. **`remediation_actions`**:
   - `action_id`, `exception_id`, `action_type` (`LEDGER_ADJUSTMENT_PROPOSAL`, `EVIDENCE_DISPUTE_PACKET`, `CLEAR_LEGITIMATE_EXCEPTION`, `APPROVED_RESOLUTION`, `ESCALATE`), `status` (`PROPOSED`, `PENDING_APPROVAL`, `APPROVED`, `REJECTED`, `EXECUTED`, `FAILED`), `action_payload` (JSON), timestamps, approval signatures.

3. **`verification_results`**:
   - `verification_id`, `exception_id`, `action_id`, `status` (`PENDING`, `PASSED`, `FAILED`), `pre_action_state` (JSON), `post_action_state` (JSON), `expected_value`, `actual_value`, `controls_checked` (JSON), `reconciliation_result` (JSON).

4. **`audit_events`**:
   - Strictly append-only.
   - `audit_event_id`, `exception_id`, `investigation_id`, `event_type`, `timestamp`, `actor_type`, `actor_id`, `event_summary`, `event_payload` (JSON), `previous_event_hash`, `event_hash`.

5. **`dataset_metadata`**:
   - `dataset_id`, `dataset_version`, `seed`, `record_count`, `generated_at`, `description`.

---

### D. Evaluation Ground Truth (Strictly Isolated)

**`evaluation_ground_truth`**:
- `case_id`, `anomaly_type`, `expected_root_cause`, `expected_exposure`, `expected_resolution_class`, `expected_verification_state`.
- **Isolation Principle**: Ground truth records are stored in a dedicated benchmark table without foreign key dependencies to operational tables. The future AI agent has zero access to this table.

---

## 4. Exception State Machine

```
DETECTED
  └── INVESTIGATING
        └── DIAGNOSED
              └── AWAITING_ACTION
                    └── RESOLVING
                          └── VERIFYING
                                ├── VERIFIED_CLOSED (Success Terminal)
                                └── FAILED_ESCALATED (Failure Terminal)
```

- Any illegal transition (e.g. `DETECTED → VERIFIED_CLOSED` or `VERIFIED_CLOSED → INVESTIGATING`) is deterministically rejected by `backend/controls/state_machine.py` with `InvalidStateTransitionError`.

---

## 5. Repository Layer Pattern

All data access is encapsulated in `backend/services/repositories/`:
- `FinancialSourceRepository`: Append-only source record creation and multi-entity queries.
- `ExceptionRepository`: Exception lifecycle and affected records.
- `InvestigationRepository`: Investigation run lifecycle.
- `AuditRepository`: Strictly append-only audit trail logging.
- `RemediationRepository`: Remediation proposal and status tracking.
- `VerificationRepository`: Post-action assertions and double-entry validation records.
- `DatasetRepository`: Synthetic dataset metadata tracking.
- `GroundTruthRepository`: Isolated evaluation benchmark storage.

---

## 6. How to Initialize, Reset, and Test

### Database Initialization / Reset
```python
from backend.models.database import init_db, reset_db

# Create tables
init_db()

# Reset schema (drops and recreates tables for testing)
reset_db()
```

### Running Database Tests
```powershell
# From workspace root with .venv active
pytest backend/tests -v
```
