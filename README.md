# Nodal Sentinel

**AI Finance Controller for Nodal & Escrow Account Health**

Nodal Sentinel is a production-hardened finance controller architecture enforcing strict separation between **deterministic financial control** (balance arithmetic, double-entry verification, reconciliation, settlement SLA monitoring, invariant enforcement) and **AI-driven investigation** (cross-source reasoning, root-cause analysis, temporal trace synthesis).

---

## 🏛️ System Architecture

```
USER / OPERATOR
       │ (Web UI / REST API)
       ▼
FRONTEND (Next.js 15 App Router / Tailwind CSS)
       │ (HTTP with X-Request-ID Correlation)
       ▼
FASTAPI BACKEND
 ├── RequestContextMiddleware (UUID Correlation Tracking)
 ├── RateLimitMiddleware (Sliding-window compute protection)
 └── Centralized Error Handlers (Unified JSON payloads, zero stack leaks)
       │
 ┌─────┴────────────────────────────────────────────────────────┐
 │                   OPERATIONAL SYSTEM                         │
 │                                                              │
 │  1. Deterministic Controls & Reconciliation Engine           │
 │     └── Balance arithmetic, double-entry checks, SLA rules   │
 │                                                              │
 │  2. Exception Detection Engine                               │
 │     └── 14 anomaly families, state transitions               │
 │                                                              │
 │  3. AI-Driven Root-Cause Investigation                       │
 │     └── Read-only tools, injection-sanitized evidence       │
 │                                                              │
 │  4. Exposure Quantification & Risk Materiality Engine        │
 │     └── Integer paise calculations, priority sorting         │
 │                                                              │
 │  5. Policy Gating & Human Approval Engine                    │
 │     └── Separation of duties, expiry, amount limits          │
 │                                                              │
 │  6. Remediation Execution Engine                             │
 │     └── Transactional double-entry rollback protection       │
 │                                                              │
 │  7. Post-Remediation Verification Engine                     │
 │     └── 7 invariant checks, zero false closure guarantee     │
 └──────────────────────────────┬───────────────────────────────┘
                                │ (Read-Only Telemetry)
                                ▼
 ┌──────────────────────────────────────────────────────────────┐
 │                      EVALUATION LAYER                        │
 │  EvaluationGroundTruth (Isolated Reader)                     │
 │  Deterministic Matcher (5-step explainable pairing)          │
 │  Scorer & Benchmark Reporter (Paise error, F1, 0-tolerance)  │
 └──────────────────────────────────────────────────────────────┘
```

---

## 🔒 Core Invariants & Safety Guarantees

1. **Zero LLM Mutation Rights**: The AI agent operates via strictly read-only inspection tools (`lookup_payment`, `lookup_settlements`, `lookup_disputes`, `lookup_ledger`). The AI cannot mutate financial records, bypass policies, or directly resolve exceptions.
2. **Integer Minor Units (Paise)**: All financial amounts, exposures, and ledger balances are computed in integer paise ($₹1 = 100\text{ paise}$) to completely eliminate floating-point inaccuracies.
3. **Double-Entry Invariants**: Ledger entries enforce strict debit/credit exclusivity ($Debit > 0 \oplus Credit > 0$) and continuous balance progression ($Balance[i] = Balance[i-1] + Credit[i] - Debit[i]$).
4. **Dual-Controller Governance & Separation of Duties**: The operator requesting a remediation cannot approve it. Approvals expire after 24 hours.
5. **Zero False Closures**: Post-remediation verification deterministically recalculates residual exposure across bank, gateway, and ledger records before permitting closure (`VERIFIED_CLOSED`).
6. **Ground-Truth Isolation**: Operational modules have zero knowledge or dependency on `evaluation_ground_truth`.

---

## 🚀 Quickstart Guide

### Prerequisites
- Python 3.11+
- Node.js 18+ / npm

### 1. Backend Setup & Startup
```powershell
# Create and activate virtual environment
cd backend
python -m venv .venv
.\.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run backend API server
uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload
```

### 2. Frontend Setup & Startup
```powershell
cd frontend
npm install
npm run dev
```
Access the operator dashboard at: `http://localhost:3000`

---

## 🧪 Testing & Verification

### Running the Backend Test Suite (188 Tests)
```powershell
.\backend\.venv\Scripts\pytest -v
```

### Running Specific Hardening Test Suites
```powershell
# End-to-End 12-Stage Pipeline & Traceability
.\backend\.venv\Scripts\pytest backend/tests/test_end_to_end_pipeline.py -v

# Safety Boundaries & Invariant Rejection
.\backend\.venv\Scripts\pytest backend/tests/test_final_safety_boundaries.py -v

# Disaster Recovery & Fault Tolerance
.\backend\.venv\Scripts\pytest backend/tests/test_disaster_recovery.py -v
```

### Building the Frontend Production Bundle
```powershell
cmd /c npm --prefix frontend run build
```

---

## 📡 REST API Reference

| Method | Path | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Lightweight non-blocking liveness probe |
| `GET` | `/ready` | Readiness probe (database connectivity & configuration check) |
| `GET` | `/metrics` | Safe operational telemetry counters |
| `POST` | `/data/generate` | Generates synthetic financial dataset with seeded anomalies |
| `GET` | `/nodal/health` | Computes live nodal account health score and SLA metrics |
| `POST` | `/exceptions/detect` | Runs deterministic detection rules across 14 anomaly types |
| `GET` | `/exceptions/{id}` | Detailed exception summary with affected record linkage |
| `GET` | `/exceptions/{id}/lineage` | Full entity provenance trace (Payment $\to$ Exception $\to$ Verification) |
| `GET` | `/exceptions/diagnostics/integrity` | Read-only database diagnostic runner |
| `POST` | `/exceptions/{id}/investigate` | Triggers AI agent root-cause investigation |
| `GET` | `/risk/queue` | Returns exposure-quantified and prioritized exception queue |
| `POST` | `/policy/evaluate` | Evaluates policy rules and determines required approval roles |
| `POST` | `/remediations/plan` | Creates controlled remediation action plan |
| `POST` | `/remediations/{id}/approve` | Records separation-of-duties controller approval |
| `POST` | `/remediations/{id}/execute` | Atomically executes approved remediation |
| `POST` | `/verifications/verify` | Executes 7 deterministic post-remediation invariant checks |
| `POST` | `/evaluation/run` | Executes accuracy benchmark evaluation against ground truth |
| `GET` | `/evaluation/benchmark` | Retrieves latest benchmark summary report |

---

## 📊 Benchmark Accuracy & Seed 42 Results

| Metric | Result | Target |
| :--- | :---: | :---: |
| **Detection Precision** | **100.00%** (10,000 bps) | $\ge 90.00\%$ |
| **Detection Recall** | **100.00%** (10,000 bps) | $\ge 90.00\%$ |
| **Detection F1 Score** | **100.00%** (10,000 bps) | $\ge 90.00\%$ |
| **False Positive Count** | **0** | $0$ |
| **False Negative Count** | **0** | $0$ |
| **False Closure Count** | **0** | **0 (Strict)** |
| **Critical Safety Status** | **PASSED** | **PASSED** |
| **Total Test Suite** | **188 / 188 Passing** | **100%** |
| **Frontend Production Build** | **Exit Code: 0** | **0 Errors** |

---

## 📄 Documentation Links
- [Production Readiness Audit](docs/production-readiness.md)
- [Benchmark Evaluation Engine](docs/evaluation.md)
