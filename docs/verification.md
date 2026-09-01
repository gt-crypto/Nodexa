# Post-Remediation Verification & Self-Verification Engine

**Module**: `backend/verification/`  
**API Router**: `/remediations/{id}/verify`, `/verifications/{id}`, `/exceptions/{id}/verifications`  
**Version**: `1.0.0`

---

## 1. Executive Summary & Objective

The **Post-Remediation Verification & Self-Verification Engine** is the final deterministic gating layer of **Nodal Sentinel**. It provides zero-trust verification that an executed remediation plan has successfully resolved an anomaly in live nodal escrow operations.

### Zero-Trust Principle
The verifier **never** trusts the remediation executor's return status alone. A remediation marked `EXECUTED` or `AWAITING_VERIFICATION` is not assumed successful. The verification engine independently inspects fresh database records across:
* Gateway transactions (`gateway_transactions`)
* Dispute and refund logs (`dispute_refund_events`)
* Bank settlement clearing batches (`bank_settlement_batches`)
* Merchant fulfillment records (`merchant_orders`)
* Double-entry nodal escrow ledger (`nodal_ledger`)
* Live deterministic financial controls & invariants

```
┌──────────────────────────────────────────────────────────────────────────────────────────┐
│                             POST-REMEDIATION VERIFICATION FLOW                           │
│                                                                                          │
│  [Prompt 8: EXECUTED]                                                                    │
│         │                                                                                │
│         ▼                                                                                │
│  Remediation: AWAITING_VERIFICATION                                                      │
│  Exception:   DIAGNOSED                                                                  │
│         │                                                                                │
│         ▼                                                                                │
│  [Prompt 9: VERIFICATION SERVICE]                                                        │
│         │                                                                                │
│         ├── Check 1: Remediation Execution Status (Snapshots Present)                    │
│         ├── Check 2: Action-Specific State Outcome (Refund/Reversal/Allocation)          │
│         ├── Check 3: Deterministic Exposure Recalculation (Remaining = 0 paise)          │
│         ├── Check 4: Deterministic Financial Invariant Suite                             │
│         ├── Check 5: Double-Entry Balance Delta Math (Credits - Debits)                  │
│         ├── Check 6: Deterministic Multi-Source Reconciliation Verification              │
│         ├── Check 7: Legitimate Case Safeguard (No Artificial Observation Closures)      │
│         └── Check 8: Stale State Protection (Detect Concurrent Mutations)                │
│         │                                                                                │
│         ├──────────────────────────┬──────────────────────────────────────────┐          │
│         │ All 9 Conditions Met     │ Verification Fails (attempt < max)       │          │
│         ▼                          ▼                                          ▼          │
│  Record: VERIFIED           Record: FAILED                             Record: ESCALATED │
│  Action: VERIFIED           Exception: DIAGNOSED (Retriable)           Action: FAILED    │
│  Exception: VERIFIED_CLOSED                                            Exception:        │
│                                                                        FAILED_ESCALATED  │
└──────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. The 8 Independent Verification Checks

| Check ID | Verification Gate | Deterministic Rule & Validation |
| :--- | :--- | :--- |
| **`CHECK-1`** | **Execution Status** | Remediation status must be `AWAITING_VERIFICATION`, with non-empty `before_snapshot` and `after_snapshot`. |
| **`CHECK-2`** | **Action State** | Action-specific state transitions: `REFUND` updates status to `REFUNDED`, creates `DisputeRefundEvent` and ledger debit; `REVERSE_REFUND` creates `CHARGEBACK_REVERSAL` and ledger credit; `ALLOCATE_SETTLEMENT` links settlement UTR to payment. |
| **`CHECK-3`** | **Exposure Recalculation** | Deterministically recomputes exposure in integer paise minor units. Must reach 0 for full closure. |
| **`CHECK-4`** | **Financial Invariants** | Re-executes the invariant suite: Balance Progression ($B_i = B_{i-1} + C_i - D_i$), Debit/Credit Sanity, Non-Negative Constraints, Currency Consistency, Reference Integrity. |
| **`CHECK-5`** | **Double-Entry Delta** | Validates that $\Delta \text{Balance} = \text{Balance}_{\text{after}} - \text{Balance}_{\text{before}} \equiv \text{Credits} - \text{Debits}$. |
| **`CHECK-6`** | **Multi-Source Reconciliation** | Re-runs deterministic matching and amount reconciliation across all affected sources. |
| **`CHECK-7`** | **Legitimate Case Protection** | Ensures `PARTIAL_SETTLEMENT` and `LEGITIMATE_TIMING_EXCEPTION` with 0 initial exposure are preserved as legitimate observations and never falsely closed as remediated anomalies. |
| **`CHECK-8`** | **Stale State Protection** | Validates that no subsequent corrupting ledger mutation occurred between execution snapshot time and verification time. |

---

## 3. Deterministic Integer Exposure Recalculation

All financial amounts are represented strictly as **integer minor units (paise)**. No floating-point numbers are used in mathematical calculations:

$$\text{Remaining Exposure} = \max(0, \text{Original Exposure} - \text{Executed Offsets})$$

$$\text{Exposure Reduction (bps)} = \begin{cases} \left( \frac{\text{Exposure Reduction} \times 10000}{\text{Original Exposure}} \right) & \text{if } \text{Original Exposure} > 0 \\ 10000 & \text{if } \text{Original Exposure} = 0 \end{cases}$$

---

## 4. Strict 9-Condition Closure Policy

For an exception to transition to `VERIFIED_CLOSED`, **all 9** conditions must evaluate to `TRUE`:
1. **Remediation Executed**: Plan was executed and is in `AWAITING_VERIFICATION`.
2. **Action-Specific Check Passed**: Target database mutations are confirmed.
3. **Deterministic Controls Pass**: All active operational controls evaluate to `PASS` or `NOT_APPLICABLE`.
4. **Reconciliation Passes**: Multi-source reconciliation confirms consistency.
5. **Financial Invariants Pass**: Ledger balance progression and equilibrium hold.
6. **Remaining Exposure is Zero**: $\text{Remaining Exposure} \equiv 0 \text{ paise}$.
7. **No Unresolved Linked Exceptions**: No blocking child/linked exceptions exist.
8. **Verification Record Verified**: Verification status evaluates to `VERIFIED`.
9. **Policy Allows Closure**: Governance policy grants closure authority.

If **any** condition fails, closure is refused.

---

## 5. Failure Handling, Retries & Concurrency Locking

### Worker Concurrency Locking
To prevent race conditions during distributed or parallel verification, the engine maintains in-process mutexes keyed by remediation ID (`_WORKER_LOCKS`).

### Bounded Retries
* **Max Attempts**: Configured by default to 3 attempts.
* **Transient Failures (Attempts 1 & 2)**: Verification record marked `FAILED`. Exception remains in `DIAGNOSED` state to allow operator correction and subsequent retry.
* **Exhausted Attempts (Attempt $\ge$ 3)**: Verification record marked `ESCALATED`. Exception transitions to `FAILED_ESCALATED`. Audit event `VERIFICATION_ESCALATED` emitted.

---

## 6. Zero Ground-Truth Isolation

The Post-Remediation Verification Engine operates with **complete isolation** from `evaluation_ground_truth`. All assertions and state evaluations are derived purely from operational financial records and deterministic control formulas.
Deleting the `evaluation_ground_truth` table causes 0 failures in the verification engine.

---

## 7. REST API Reference

### `POST /remediations/{remediation_id}/verify`
Executes verification for a remediation plan.
* **Query Parameters**:
  * `dry_run` (bool, default: `false`): Run simulation without persisting records or mutating lifecycle states.
  * `actor_type` (string, default: `"SYSTEM"`): Initiator category.
  * `actor_id` (string, default: `"verifier-v1"`): Actor identity.
* **Response (Live)**: `VerificationRecordResponse` (HTTP 200)
* **Response (Dry Run)**: `VerificationDryRunResponse` (HTTP 200)

### `GET /remediations/{remediation_id}/verification`
Fetches the latest verification record for a remediation plan.

### `GET /verifications/{verification_id}`
Fetches a specific verification record by its unique identifier.

### `POST /verifications/{verification_id}/retry`
Retries verification for a previously `FAILED` verification record, incrementing the attempt counter.

### `GET /exceptions/{exception_id}/verifications`
Lists all historical verification attempts and evidence trails for a given exception.

---

## 8. Immutable Audit Trail Events

| Audit Event Type | Trigger | Key Payload Metadata |
| :--- | :--- | :--- |
| `VERIFICATION_STARTED` | Verification run initiated | `remediation_id`, `exception_id`, `mode`, `attempt_number` |
| `VERIFICATION_CHECK_PASSED` | Individual check passes | `check_id`, `source_table`, `expected`, `actual` |
| `VERIFICATION_COMPLETED` | All checks evaluated | `status`, `remaining_exposure`, `reduction_bps` |
| `EXCEPTION_VERIFIED_CLOSED` | All 9 conditions met | `exception_id`, `remediation_id`, `closed_at` |
| `VERIFICATION_FAILED` | Check failed (< max retries) | `failure_reasons`, `attempt_number` |
| `VERIFICATION_ESCALATED` | Retries exhausted ($\ge 3$) | `exception_id`, `action_id`, `escalated_to_risk` |
