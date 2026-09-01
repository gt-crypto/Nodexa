# Nodal Sentinel - Remediation Planning & Controlled Action Workflow

This document specifies the technical architecture, capability registry, parameter schemas, approval workflows, atomic execution engine, and safety invariants for **Prompt 8 — Remediation Planning & Controlled Action Workflow**.

---

## 1. Core Architectural Principle: Plan $\longrightarrow$ Approve $\longrightarrow$ Controlled Execute $\longrightarrow$ Await Verification

The Remediation Engine translates diagnosed exceptions and approved policy decisions into structured operational plans, enforces separation of duties and role approvals, and executes safe financial mutations with complete transactional rollback protection:

$$\text{DATA} \longrightarrow \text{CONTROLS} \longrightarrow \text{EXCEPTION} \longrightarrow \text{INVESTIGATION} \longrightarrow \text{EXPOSURE} \longrightarrow \text{RISK} \longrightarrow \text{POLICY} \longrightarrow \mathbf{REMEDIATION\ PLAN} \longrightarrow \mathbf{APPROVAL} \longrightarrow \mathbf{CONTROLLED\ EXECUTE} \longrightarrow \mathbf{AWAIT\ VERIFICATION}$$

- **No Autonomous Execution**: Remediation actions must be explicitly requested and parameter-validated against authoritative Prompt 4 exposures and Prompt 7 policy gates.
- **Transactional & Invariant-Checked**: Every financial mutation verifies double-entry ledger balance progressions ($Credits - Debits = BalanceDelta$) before committing. Any failure triggers a complete database rollback and marks the remediation as `FAILED`.
- **Scope Separation (Verification Belongs to Prompt 9)**: Executed remediations transition to `AWAITING_VERIFICATION`. The exception itself remains `DIAGNOSED` until the Prompt 9 verification engine formally asserts financial invariants and closes the exception.

---

## 2. Action Taxonomy & Capability Registry

| Action | Financial Mutation | Required State | Required Policy Decision | Approval Mandate | Verification Mandatory |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`REFUND`** | **Yes** | `DIAGNOSED` | `REQUIRE_APPROVAL` / `ALLOW` | Role: `FINANCE` | **Yes** |
| **`REVERSE_REFUND`** | **Yes** | `DIAGNOSED` | `REQUIRE_APPROVAL` / `ALLOW` | Role: `FINANCE` | **Yes** |
| **`ALLOCATE_SETTLEMENT`** | **Yes** | `DIAGNOSED` | `REQUIRE_APPROVAL` / `ALLOW` | Role: `FINANCE` | **Yes** |
| **`RECONCILE`** | **Yes** | `DIAGNOSED` | `ALLOW` / `ALLOW_WITH_CONDITIONS` | Operational | **Yes** |
| **`ESCALATE`** | No | `DIAGNOSED` | `REQUIRE_ESCALATION` / `ALLOW` | None | No |
| **`RESOLVE_EXCEPTION`** | No | `DIAGNOSED` | `ALLOW` | Role: `ADMIN` | **Yes** (Blocked until Verification) |

*Arbitrary or non-allowlisted action strings are strictly rejected with validation errors.*

---

## 3. Financial Parameter Validation & Exposure Bounds

All monetary parameters are strictly typed as **integer minor units** (paise for INR, 100 paise = 1 INR):
- **Amount Boundary Rule**: Requested mutation amounts cannot exceed the authoritative Prompt 4 deterministic exposure:
  $$\text{amount\_minor\_units} \le \text{exception.exposure}$$
- **Zero Floating-Point Arithmetic**: Prevents fractional precision leaks across all ledger adjustments and dispute events.
- **Legitimate Case Protection**: Confirmed legitimate observations (`PARTIAL_SETTLEMENT` and `LEGITIMATE_TIMING_EXCEPTION` with `exposure = 0`) strictly prohibit financial remediation plans (`REFUND`, `REVERSE_REFUND`, `ALLOCATE_SETTLEMENT`).

---

## 4. Approval Workflow & Separation of Duties

- **Separation of Duties**: Requesters are strictly prohibited from approving their own remediation plans:
  $$\text{plan.requested\_by} \neq \text{approval.approved\_by}$$
- **Human Authority Requirement**: Financial approvals must be recorded by human actors; system actors cannot approve financial plans.
- **Approval Expiry**: Approvals expire after a configurable window (default 24 hours). Stale approvals block execution.
- **Status Lifecycle**:
  ```
  PLANNED ──► PENDING_APPROVAL ──► APPROVED ──► EXECUTING ──► EXECUTED / AWAITING_VERIFICATION
                  │
                  ▼
               REJECTED
  ```

---

## 5. Execution Engine, Invariants & Rollback Protection

1. **Safety Pre-Checks**:
   - Re-checks that exception is in `DIAGNOSED` state.
   - Re-checks that latest policy decision permits execution.
   - Re-checks that approval is valid, active, and unexpired.
   - Re-checks that requested amount $\le$ authoritative exposure.
2. **Atomic Locking & State Transition**:
   - Updates status from `APPROVED`/`PLANNED` $\longrightarrow$ `EXECUTING`.
3. **Execution & Ledger Mutation**:
   - Executes dedicated handler (`RefundHandler`, `ReverseRefundHandler`, `AllocateSettlementHandler`, etc.).
   - Captures structured `before_snapshot` and `after_snapshot`.
4. **Double-Entry Balance Invariant Check**:
   - Evaluates all `NodalLedgerEntry` records against `validate_ledger_balance_progression()`.
   - Formula: $Balance[i] = Balance[i-1] + Credit[i] - Debit[i]$.
   - If invariant fails: **ROLLBACK** transaction, mark status as `FAILED`, and record error.
5. **Transition to `AWAITING_VERIFICATION`**:
   - For all mutating actions, the plan status is updated to `AWAITING_VERIFICATION`.

---

## 6. Worked Examples (Seed-42 Benchmark)

### 1. Ghost Settlement (`EXC-GHOST_SETTLEMENT-PAY-000001`)
- **Remediation Plan**: `REFUND` for payment `PAY-000001` (Amount: ₹50,986.29).
- **Approval**: Reviewed and approved by `finance-controller-01` (Role: `FINANCE`).
- **Execution**: Updates gateway transaction to `REFUNDED`, creates `DisputeRefundEvent` (`REFUND`), posts ledger debit entry `NLE-REF-...`, verifies invariant, moves to `AWAITING_VERIFICATION`.

### 2. Refund + Chargeback Double-Dip (`EXC-REFUND_CHARGEBACK_DOUBLE_DIP-PAY-000003`)
- **Remediation Plan**: `REVERSE_REFUND` for payment `PAY-000003` (Amount: ₹20,697.00).
- **Approval**: Approved by `risk-controller-01` (Role: `FINANCE`).
- **Execution**: Posts offsetting ledger credit entry `NLE-REV-...`, updates transaction status, moves to `AWAITING_VERIFICATION`.

### 3. Settlement SLA Breach (`EXC-SETTLEMENT_SLA_BREACH-PAY-000005`)
- **Remediation Plan**: `RECONCILE` for payment `PAY-000005`.
- **Execution**: Updates reconciliation reference, moves to `AWAITING_VERIFICATION`.

### 4. Unallocated Settlement (`EXC-UNALLOCATED_SETTLEMENT-TXN-000010`)
- **Remediation Plan**: `ALLOCATE_SETTLEMENT` for batch `BATCH-000010` to payment `PAY-000010` (Amount: ₹14,847.00).
- **Approval**: Approved by `finance-controller-01`.
- **Execution**: Links settlement batch and ledger description to payment, moves to `AWAITING_VERIFICATION`.

### 5. Legitimate Partial Settlement (`EXC-PARTIAL_SETTLEMENT-PAY-000007`)
- **Remediation Plan Attempt**: `REFUND` $\longrightarrow$ **`REJECTED / BLOCKED`** (*"Legitimate zero-exposure observation prohibits financial remediation."*)

---

## 7. REST API Endpoints

- `POST /exceptions/{exception_id}/remediation-plan`: Creates validated remediation plan.
- `GET /exceptions/{exception_id}/remediations`: Retrieves all remediation plans for an exception.
- `GET /remediations/{remediation_id}`: Retrieves single plan details.
- `POST /remediations/{remediation_id}/approve`: Records human role approval (`decision: "APPROVED"`).
- `POST /remediations/{remediation_id}/reject`: Rejects plan (`decision: "REJECTED"`).
- `POST /remediations/{remediation_id}/execute`: Transactionally executes plan.
- `POST /remediations/{remediation_id}/cancel`: Cancels pending plan.
- `POST /remediations/{remediation_id}/dry-run`: Simulates projected before/after states without database mutations.
