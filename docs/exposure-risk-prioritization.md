# Nodal Sentinel - Financial Exposure, Materiality & Risk Prioritization Engine

This document specifies the technical architecture, exposure models, deterministic materiality thresholds, risk scoring components, priority mapping, escalation logic, account aggregation, and queue ordering for **Prompt 6 — Financial Exposure, Materiality & Risk Prioritization Engine**.

---

## 1. Core Architectural Principle: Deterministic Risk & Exposure Authority

The Risk Prioritization layer transforms deterministic exceptions, authoritative Prompt 4 financial exposures, Prompt 5 AI root-cause diagnostics, and operational account context into deterministic decision metrics:

$$\text{DETERMINISTIC FINANCIAL CONTROLS} \longrightarrow \text{EXCEPTION} \longrightarrow \text{AI INVESTIGATION} \longrightarrow \text{EXPOSURE} \longrightarrow \text{MATERIALITY} \longrightarrow \text{RISK PRIORITIZATION} \longrightarrow \text{DECISION INPUT}$$

- **Authoritative Exposure Source**: Prompt 4 deterministic integer exposure is 100% authoritative. The AI investigator provides root-cause reasoning but CANNOT modify, override, or recalculate the numerical exposure.
- **Integer Minor Units**: All monetary values are strictly stored and computed as integer minor units (`BigInteger`, paise for INR). No floating-point math is used for financial balances or exposures.
- **Zero LLM Scoring**: Materiality classification, 0–100 risk scoring, P1–P4 priorities, and escalation recommendations are evaluated entirely deterministically. Zero LLM calls are used for risk scoring.
- **Ground-Truth Independence**: Operational risk calculations never access `evaluation_ground_truth`.

---

## 2. Exposure Types Taxonomy

Exceptions are mapped deterministically into financial exposure types:

| Exception Family | Sub-type | Exposure Type | Description |
| :--- | :--- | :--- | :--- |
| **`GHOST_SETTLEMENT`** | Ghost Settlement | `FUNDS_AT_RISK` | Uncaptured settlement credited into escrow without gateway authorization. |
| **`REFUND_CHARGEBACK_DOUBLE_DIP`** | Double-Dip Liability | `DIRECT_FINANCIAL_LOSS` | Dual debit liability causing unrecoverable cash drain. |
| **`SETTLEMENT_SLA_BREACH`** | Settlement SLA Breach | `SLA_DELAY_IMPACT` | Inflow delayed beyond contractual clearance window. |
| **`MISSING_UNALLOCATED_SETTLEMENT`** | Missing Settlement | `FUNDS_AT_RISK` | Expected settlement tranche not received from acquirer. |
| **`MISSING_UNALLOCATED_SETTLEMENT`** | Unallocated Settlement | `FUNDS_AT_RISK` | Bank credit received without matching gateway transaction. |
| **`PARTIAL_SETTLEMENT`** | Legitimate Multi-Tranche Split | `NO_FINANCIAL_EXPOSURE` | Multi-tranche settlement summing to exact net expected. |
| **`LEGITIMATE_TIMING_EXCEPTION`** | Legitimate Weekend Timing | `NO_FINANCIAL_EXPOSURE` | Clearance occurred within next valid business processing window. |

---

## 3. Materiality Classification & Thresholds

Configured in `backend/exposure/config.py` in integer minor units (paise, 100 paise = 1 INR):

| Materiality Level | Lower Bound (Minor Units) | Upper Bound (Minor Units) | Equivalent (INR) |
| :--- | :---: | :---: | :--- |
| **`NONE`** | 0 | 0 | ₹0.00 |
| **`LOW`** | 1 | 99,999 | < ₹1,000.00 |
| **`MEDIUM`** | 100,000 | 499,999 | ₹1,000.00 – ₹4,999.99 |
| **`HIGH`** | 500,000 | 1,999,999 | ₹5,000.00 – ₹19,999.99 |
| **`MATERIAL`** | 2,000,000 | 9,999,999 | ₹20,000.00 – ₹99,999.99 |
| **`SEVERE`** | 10,000,000 | $\infty$ | $\ge$ ₹100,000.00 |

### Relative Materiality
Relative materiality is computed in integer basis points ($1 \text{ bps} = 0.01\%$):
$$\text{Relative Materiality (bps)} = \min\left(10000, \frac{\text{Exposure} \times 10000}{\text{Account Balance}}\right)$$

---

## 4. Deterministic Risk Scoring Model

The risk score is a deterministic integer normalized to **0–100** computed from 8 inspectable components:

$$\text{Risk Score} = S_{\text{exposure}} + S_{\text{severity}} + S_{\text{controls}} + S_{\text{confidence}} + S_{\text{complexity}} + S_{\text{sla}} + S_{\text{ledger}} + S_{\text{allocation}}$$

### Component Weights & Scoring Breakdown:

| Component | Max Weight | Evaluation Criteria |
| :--- | :---: | :--- |
| **Financial Exposure ($S_{\text{exposure}}$)** | **30** | $\ge 10\text{M} \rightarrow 30$, $\ge 2\text{M} \rightarrow 25$, $\ge 500\text{k} \rightarrow 18$, $\ge 100\text{k} \rightarrow 10$, $>0 \rightarrow 5$, $0 \rightarrow 0$ |
| **Severity ($S_{\text{severity}}$)** | **20** | $\text{CRITICAL} \rightarrow 20$, $\text{HIGH} \rightarrow 15$, $\text{MEDIUM} \rightarrow 10$, $\text{LOW} \rightarrow 5$ |
| **Control Failure ($S_{\text{controls}}$)** | **15** | $\min(15, \text{failed\_controls} \times 7)$ |
| **Investigation Confidence ($S_{\text{confidence}}$)** | **10** | $\text{HIGH} \rightarrow 10$, $\text{MEDIUM} \rightarrow 6$, $\text{LOW} \rightarrow 2$, $\text{None} \rightarrow 5$ |
| **Operational Complexity ($S_{\text{complexity}}$)** | **5** | $>2 \text{ records} \rightarrow 5$, $2 \text{ records} \rightarrow 3$, $1 \text{ record} \rightarrow 1$ |
| **SLA Impact ($S_{\text{sla}}$)** | **10** | $\text{SLA Breached} \rightarrow 10$, $\text{Within SLA} \rightarrow 0$ |
| **Ledger Risk ($S_{\text{ledger}}$)** | **5** | $\text{Ghost settlement / ledger contradiction} \rightarrow 5$, $\text{None} \rightarrow 0$ |
| **Allocation / Double-Dip Risk ($S_{\text{allocation}}$)** | **5** | $\text{Unallocated funds or double-dip liability} \rightarrow 5$, $\text{None} \rightarrow 0$ |

---

## 5. Priority Mapping & Escalation Recommendations

### Priority Levels

| Priority Level | Score Range | Description |
| :--- | :---: | :--- |
| **`P1`** | **75 – 100** | **Critical Action**: Severe exposure, critical severity, or ghost settlement requiring immediate intervention. |
| **`P2`** | **50 – 74** | **High Priority**: Material exposure or multi-source contradiction. |
| **`P3`** | **25 – 49** | **Moderate Priority**: SLA delay or minor unallocated variance. |
| **`P4`** | **0 – 24** | **Low Priority / Informational**: Zero-exposure legitimate observations or low materiality. |

### Special Invariant for Legitimate Cases
For `PARTIAL_SETTLEMENT` and `LEGITIMATE_TIMING_EXCEPTION` with `exposure = 0`:
- $\text{Materiality} = \text{NONE}$
- $\text{Risk Score} = 0$
- $\text{Priority} = \text{P4}$
- $\text{Escalation} = \text{NO\_ESCALATION}$

### Escalation Recommendations

- **`IMMEDIATE_ESCALATION`**: $P1$ priority, `CRITICAL` severity, or Ghost Settlement.
- **`FINANCE_REVIEW`**: Unallocated bank funds or reconciliation discrepancy.
- **`RISK_REVIEW`**: Refund + Chargeback double-dip liability.
- **`OPERATIONS_REVIEW`**: $P2$ / $P3$ priority operational discrepancies.
- **`NO_ESCALATION`**: Legitimate observations and $P4$ items.

---

## 6. Top-Risk Prioritization Queue & Deterministic Tie Breaking

The queue sorts exceptions deterministically using a 5-level tuple:
1. **Priority Rank** (`P1 (4) > P2 (3) > P3 (2) > P4 (1)`)
2. **Risk Score** (`DESC`)
3. **Financial Exposure** (`DESC`)
4. **Severity Rank** (`CRITICAL (4) > HIGH (3) > MEDIUM (2) > LOW (1)`)
5. **Detected Timestamp** (`ASC`, oldest first)

---

## 7. Worked Examples (Seed-42 Benchmark)

### 1. Ghost Settlement (`EXC-GHOST_SETTLEMENT-PAY-000001`)
- **Exposure**: ₹50,986.29 (5,098,629 minor units)
- **Materiality**: `MATERIAL`
- **Component Breakdown**: Exposure (25) + Severity (20) + Controls (14) + Confidence (10) + Complexity (3) + SLA (0) + Ledger (5) + Alloc (0) = **77/100**
- **Priority**: `P1`
- **Escalation**: `IMMEDIATE_ESCALATION`
- **Explanation**: *"Priority P1 assigned with total risk score 77/100. Deterministic financial exposure is ₹50,986.29 (MATERIAL materiality, contributing 25/30 pts). Exception severity is CRITICAL. AI diagnostic root-cause category is PAYMENT_STATE_CONTRADICTION. Elevated risk due to ledger contradiction and invalid settlement credit. Recommended escalation: IMMEDIATE_ESCALATION."*

### 2. Refund + Chargeback Double-Dip (`EXC-REFUND_CHARGEBACK_DOUBLE_DIP-PAY-000003`)
- **Exposure**: ₹27,500.00 (2,750,000 minor units)
- **Materiality**: `MATERIAL`
- **Component Breakdown**: Exposure (25) + Severity (15) + Controls (14) + Confidence (10) + Complexity (3) + SLA (0) + Ledger (0) + Alloc (5) = **72/100**
- **Priority**: `P2`
- **Escalation**: `RISK_REVIEW`

### 3. Legitimate Partial Settlement (`EXC-PARTIAL_SETTLEMENT-PAY-000007`)
- **Exposure**: ₹0.00
- **Materiality**: `NONE`
- **Risk Score**: **0/100**
- **Priority**: `P4`
- **Escalation**: `NO_ESCALATION`
- **Explanation**: *"Priority P4 (Risk Score: 0/100). Zero financial exposure detected. Case classified as legitimate operational observation with materiality NONE and escalation recommendation NO_ESCALATION."*

---

## 8. REST API Endpoints

- `POST /exceptions/{exception_id}/assess-risk`: Calculates and idempotently persists risk assessment.
- `GET /exceptions/{exception_id}/risk`: Returns latest risk assessment for an exception.
- `GET /risk/queue`: Returns prioritized risk queue with filters (`priority`, `severity`, `materiality`, `exception_type`, `min_exposure`, `max_exposure`, `escalation`, `limit`, `offset`).
- `GET /risk/account`: Returns account-level open exposure, material exposure, priority distribution, top exposure exceptions, and exposure concentration.
