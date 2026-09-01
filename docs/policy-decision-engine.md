# Nodal Sentinel - Risk Policy Gating & Decision Engine

This document specifies the technical architecture, decision models, multi-stage policy gates, allowlisted action taxonomy, and safety constraints for **Prompt 7 — Risk Policy Gating & Decision Engine**.

---

## 1. Core Architectural Principle: Decision vs. Execution Separation

The Policy Engine serves as the authoritative decision layer governing what actions are permissible, prohibited, or gated under human/role approval:

$$\text{DATA} \longrightarrow \text{CONTROLS} \longrightarrow \text{EXCEPTION} \longrightarrow \text{AI INVESTIGATION} \longrightarrow \text{EXPOSURE} \longrightarrow \text{MATERIALITY} \longrightarrow \text{RISK} \longrightarrow \text{PRIORITY} \longrightarrow \mathbf{POLICY\ GATING} \longrightarrow \mathbf{DECISION}$$

- **Policy Answers "May Happen", NOT "Does Happen"**: The policy engine evaluates whether a requested action (e.g. `REFUND`, `ALLOCATE_SETTLEMENT`, `RECONCILE`) is allowed under current operational and risk conditions. It records approval and escalation mandates but **DOES NOT execute financial transactions or state mutations**.
- **Deterministic & LLM-Free**: All policy rules, gates, and decisions are evaluated 100% deterministically from structured metadata. Zero LLM calls are made during policy gating.
- **Ground-Truth Independence**: Operational policy calculations never query `evaluation_ground_truth`.

---

## 2. Decision States Taxonomy

| Decision State | Meaning | Operational Consequence |
| :--- | :--- | :--- |
| **`ALLOW`** | Action is fully permitted under current policy. | Action may proceed directly without human gating. |
| **`ALLOW_WITH_CONDITIONS`** | Action is permitted subject to specific non-blocking operational requirements. | Action may proceed once conditions are acknowledged. |
| **`REQUIRE_APPROVAL`** | Action requires designated role sign-off before proceeding. | Action is held pending explicit review (`FINANCE`, `RISK`, `OPERATIONS`, `ADMIN`). |
| **`REQUIRE_ESCALATION`** | Action or exception requires immediate stakeholder notification. | Escalation level assigned (`EXECUTIVE`, `FINANCE`, `RISK`, `OPERATIONS`). |
| **`BLOCK`** | Action is strictly prohibited by lifecycle, safety, or domain rules. | Action cannot proceed under any circumstances. |
| **`INSUFFICIENT_EVIDENCE`** | Action lacks mandatory diagnostic or evidence linkage. | System requires further investigation or evidence ingestion. |

---

## 3. Allowlisted Action Taxonomy

All evaluated actions must strictly belong to the allowlisted enum:

1. **`NO_ACTION`**: Default observational state for legitimate cases or closed exceptions.
2. **`INVESTIGATE`**: Spawns or resumes AI multi-source investigation.
3. **`RECONCILE`**: Re-evaluates deterministic settlement matching or timeline windows.
4. **`ALLOCATE_SETTLEMENT`**: Links unallocated bank credits to merchant orders.
5. **`REFUND`**: Issues credit adjustment to customer for double-charge or failed order.
6. **`REVERSE_REFUND`**: Reverses unauthorized or duplicate refund credit.
7. **`RESOLVE_EXCEPTION`**: Formally closes exception after successful verified remediation.
8. **`ESCALATE`**: Flags exception for manual executive, risk, or finance review.
9. **`REQUEST_APPROVAL`**: Solicits sign-off from designated authority.
10. **`REQUEST_MORE_EVIDENCE`**: Solicits bank statements, gateway logs, or order records.

*Any arbitrary or non-allowlisted action string is automatically rejected with `BLOCK`.*

---

## 4. Multi-Stage Policy Gates

```
[Incoming Request: Exception + Requested Action]
       │
       ▼
1. Allowlist Validation Gate (Is action supported?)
       │
       ▼
2. Lifecycle State Gate (DETECTED / INVESTIGATING / DIAGNOSED / FAILED_ESCALATED)
       │
       ▼
3. Legitimate Case Protection Gate (Is exposure == 0 on legitimate timing/partial split?)
       │
       ▼
4. Risk & Materiality Gate (P1-P4, Materiality Level, Financial Mutation rules)
       │
       ▼
5. Investigation Confidence Gate (AI confidence >= 0.60 for financial mutations)
       │
       ▼
6. Evidence Completeness Gate (Payment IDs, Settlement Batch IDs, UTR numbers)
       │
       ▼
7. Irreversible Action Safety Gate (Remediation & verification safety lock)
       │
       ▼
[Synthesize PolicyDecisionRecord & Audit Log]
```

### A. Lifecycle State Gates

| Exception State | Permitted Actions | Prohibited Actions | Policy Rationale |
| :--- | :--- | :--- | :--- |
| **`DETECTED`** | `INVESTIGATE`, `REQUEST_MORE_EVIDENCE`, `NO_ACTION` | `REFUND`, `REVERSE_REFUND`, `ALLOCATE_SETTLEMENT`, `RESOLVE_EXCEPTION`, `RECONCILE` | Investigation must complete before remediation or closure. |
| **`INVESTIGATING`** | `INVESTIGATE`, `REQUEST_MORE_EVIDENCE`, `NO_ACTION` | `REFUND`, `REVERSE_REFUND`, `ALLOCATE_SETTLEMENT`, `RESOLVE_EXCEPTION` | Actions blocked while investigation is running. |
| **`DIAGNOSED`** | `RECONCILE`, `ALLOCATE_SETTLEMENT`, `REFUND`, `REVERSE_REFUND`, `ESCALATE`, `REQUEST_APPROVAL`, `NO_ACTION` | `RESOLVE_EXCEPTION` | Remediations permitted subject to risk/approval gates; closure blocked until verified. |
| **`FAILED_ESCALATED`** | `ESCALATE`, `REQUEST_MORE_EVIDENCE`, `INVESTIGATE`, `NO_ACTION` | `REFUND`, `REVERSE_REFUND`, `ALLOCATE_SETTLEMENT`, `RESOLVE_EXCEPTION`, `RECONCILE` | Remediation prohibited without successful re-diagnosis. |

### B. Legitimate Case Protection Gate
For confirmed legitimate observations (`PARTIAL_SETTLEMENT` and `LEGITIMATE_TIMING_EXCEPTION` with `exposure = 0`):
- Default allowed action: **`NO_ACTION`**
- Prohibited actions: `REFUND`, `REVERSE_REFUND`, `ALLOCATE_SETTLEMENT`, `ESCALATE`, `RESOLVE_EXCEPTION`.
- Policy Outcome: **`ALLOW`** for `NO_ACTION`, **`BLOCK`** for financial remediation or escalation.

### C. Risk & Materiality Gating

- **$P1$ / `MATERIAL` / `SEVERE` Exposure**:
  - Financial mutations require **`REQUIRE_APPROVAL`** (Role: `FINANCE`).
  - Mandatory **`REQUIRE_ESCALATION`** (Level: `EXECUTIVE`).
- **$P2$ / `HIGH` Exposure**:
  - Financial mutations require **`REQUIRE_APPROVAL`** (Role: `FINANCE`).
  - Mandatory **`REQUIRE_ESCALATION`** (Level: `FINANCE`).
- **$P3$ / `MEDIUM` Exposure**:
  - Financial mutations require **`REQUIRE_APPROVAL`** (Role: `OPERATIONS`).
- **$P4$ / `NONE` Exposure**:
  - `ALLOW` for operational tracking and `NO_ACTION`.

### D. Irreversible Action Safety Gate
Until Prompt 8 (Remediation Actions) and Prompt 9 (Post-Action Double-Entry Verification) are implemented:
- Financial mutations (`REFUND`, `REVERSE_REFUND`, `ALLOCATE_SETTLEMENT`) require strict `REQUIRE_APPROVAL`.
- Direct exception resolution (`RESOLVE_EXCEPTION`) is **`BLOCK`ed** because verification engine is not yet active.

---

## 5. Worked Examples (Seed-42 Benchmark)

### 1. Ghost Settlement (`EXC-GHOST_SETTLEMENT-PAY-000001`)
- **Requested Action**: `REFUND`
- **Context**: State `DIAGNOSED`, Exposure ₹50,986.29, Priority `P1`, Materiality `MATERIAL`.
- **Policy Decision**: **`REQUIRE_APPROVAL`**
- **Approval Mandate**: Role `FINANCE` (*"P1 / Material financial mutation requires explicit Finance Controller approval."*)
- **Escalation Mandate**: Level `EXECUTIVE` (*"Ghost settlement requires immediate executive escalation."*)

### 2. Refund + Chargeback Double-Dip (`EXC-REFUND_CHARGEBACK_DOUBLE_DIP-PAY-000003`)
- **Requested Action**: `REVERSE_REFUND`
- **Context**: State `DIAGNOSED`, Exposure ₹20,697.00, Priority `P2`, Materiality `MATERIAL`.
- **Policy Decision**: **`REQUIRE_APPROVAL`**
- **Approval Mandate**: Role `FINANCE` (*"P2 High-materiality financial mutation requires Finance approval."*)

### 3. Settlement SLA Breach (`EXC-SETTLEMENT_SLA_BREACH-PAY-000005`)
- **Requested Action**: `RECONCILE`
- **Context**: State `DIAGNOSED`, Exposure ₹13,750.00, Priority `P2`, Materiality `HIGH`.
- **Policy Decision**: **`ALLOW_WITH_CONDITIONS`**
- **Rationale**: Re-reconciliation is permitted to verify late settlement receipt.

### 4. Unallocated Settlement (`EXC-UNALLOCATED_SETTLEMENT-TXN-000010`)
- **Requested Action**: `ALLOCATE_SETTLEMENT`
- **Context**: State `DIAGNOSED`, Exposure ₹14,847.00, Priority `P2`, Materiality `HIGH`.
- **Policy Decision**: **`REQUIRE_APPROVAL`**
- **Approval Mandate**: Role `FINANCE` (*"Unallocated settlement manual allocation requires Finance sign-off."*)

### 5. Legitimate Partial Settlement (`EXC-PARTIAL_SETTLEMENT-PAY-000007`)
- **Requested Action**: `NO_ACTION`
- **Context**: State `DIAGNOSED`, Exposure ₹0.00, Priority `P4`, Materiality `NONE`.
- **Policy Decision**: **`ALLOW`**
- **Requested Action**: `REFUND` $\longrightarrow$ **`BLOCK`** (*"Legitimate zero-exposure observation strictly prohibits financial correction or escalation."*)

---

## 6. REST API Endpoints

- `POST /exceptions/{exception_id}/policy-check`: Evaluates policy and persists decision (supports `simulation: true`).
- `GET /exceptions/{exception_id}/policy-decisions`: Retrieves decision history for an exception.
- `GET /policy/decisions/{decision_id}`: Retrieves single decision record.
- `GET /policy/config`: Returns active policy configuration parameters.
