# Nodal Sentinel - Architecture Overview

Nodal Sentinel is an AI-powered Finance Controller designed to ensure nodal-account health across continuous financial operations.

## Core Architectural Principle: Separation of Concerns

The LLM must **NEVER** have unrestricted access to financial mutations. The system maintains a strict boundary between deterministic controls and AI reasoning.

### Control Loop Lifecycle

```
MONITOR 
  └── DETECT 
        └── RECONSTRUCT 
              └── INVESTIGATE 
                    └── EXPLAIN 
                          └── QUANTIFY 
                                └── PRIORITIZE 
                                      └── DECIDE 
                                            └── RESOLVE/ESCALATE 
                                                  └── VERIFY 
                                                        └── AUDIT
```

### Layer Isolation

1. **Data Layer**: Synthetic financial schemas, transactions, nodal accounts, settlements.
2. **Deterministic Financial-Control Layer**: Monetary arithmetic, reconciliation, balance tracking, SLA timers, double-entry verification, and invariant assertions.
3. **AI Investigation Layer**: Cross-source evidence collection, temporal anomaly investigation, root-cause reasoning, and hypothesis generation via structured tools.
4. **Policy & Safety Layer**: Risk thresholds, permission gates, human-in-the-loop escalation rules.
5. **Remediation Layer**: Controlled financial actions executed solely through verified deterministic services.
6. **Verification Layer**: Post-action double-entry balance check and invariant validation.
7. **Audit Layer**: Append-only immutable log of every detection, reasoning step, decision, and financial action.
8. **Evaluation Layer**: Automated benchmark scenarios assessing agent investigation precision and control compliance.
9. **UI Layer**: Operator dashboard presenting real-time account health, discrepancy timelines, AI explanations, and approval queues.
