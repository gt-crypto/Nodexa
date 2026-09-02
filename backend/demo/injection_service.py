"""Live Digital-Twin Synthetic Anomaly Injection Service for Nodal Sentinel v2.0.

Provides deterministic runtime injection of fresh synthetic anomalies directly into
live operational data tables, routing them through the exact same invariant controls,
detection algorithms, AI investigation, risk scoring, and policy evaluation pipelines.
"""
import json
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.data.generator.config import GeneratorConfig
from backend.data.generator.context import GenerationContext
from backend.data.scenarios.ghost_settlement import generate_ghost_settlement_scenario
from backend.data.scenarios.refund_chargeback import generate_refund_chargeback_scenario
from backend.data.scenarios.sla_breach import generate_sla_breach_scenario
from backend.data.scenarios.missing_unallocated import (
    generate_missing_settlement_scenario,
    generate_unallocated_settlement_scenario,
)
from backend.data.scenarios.partial_settlement import generate_partial_settlement_scenario
from backend.data.scenarios.timing_exception import generate_timing_exception_scenario

from backend.models.enums import ExceptionType
from backend.models.injected_cases import InjectedCase
from backend.models.exceptions import ExceptionRecord
from backend.models.financial_sources import NodalLedgerEntry
from backend.models.audit import AuditEvent

from backend.controls.engine import ControlEngine
from backend.exceptions.service import ExceptionDetectionService
from backend.agent.service import InvestigationService
from backend.exposure.service import RiskAssessmentService
from backend.policy.service import PolicyService

from backend.services.repositories.financial_source_repository import FinancialSourceRepository
from backend.services.repositories.audit_repository import AuditRepository


SUPPORTED_INJECTION_FAMILIES = {
    "GHOST_SETTLEMENT": {
        "family": "GHOST_SETTLEMENT",
        "description": "Gateway payment failed / cancelled but bank settlement and nodal credit cleared.",
        "category": "ANOMALY",
        "severity": "CRITICAL",
        "is_legitimate": False,
    },
    "REFUND_CHARGEBACK_DOUBLE_DIP": {
        "family": "REFUND_CHARGEBACK_DOUBLE_DIP",
        "description": "Merchant issued a refund, followed by an overlapping chargeback debit.",
        "category": "ANOMALY",
        "severity": "HIGH",
        "is_legitimate": False,
    },
    "SETTLEMENT_SLA_BREACH": {
        "family": "SETTLEMENT_SLA_BREACH",
        "description": "Captured transaction settlement delayed past the synthetic SLA window.",
        "category": "ANOMALY",
        "severity": "MEDIUM",
        "is_legitimate": False,
    },
    "MISSING_SETTLEMENT": {
        "family": "MISSING_SETTLEMENT",
        "description": "Captured payment has no matching bank settlement batch or ledger credit.",
        "category": "ANOMALY",
        "severity": "HIGH",
        "is_legitimate": False,
    },
    "UNALLOCATED_SETTLEMENT": {
        "family": "UNALLOCATED_SETTLEMENT",
        "description": "Bank settlement inflow received with no corresponding gateway transaction.",
        "category": "ANOMALY",
        "severity": "MEDIUM",
        "is_legitimate": False,
    },
    "PARTIAL_SETTLEMENT": {
        "family": "PARTIAL_SETTLEMENT",
        "description": "Legitimate multi-tranche settlement whose aggregate matches payment gross.",
        "category": "LEGITIMATE_EDGE_CASE",
        "severity": "LOW",
        "is_legitimate": True,
    },
    "LEGITIMATE_TIMING_EXCEPTION": {
        "family": "LEGITIMATE_TIMING_EXCEPTION",
        "description": "Settlement delayed across weekend/cutoff but cleared inside next valid window.",
        "category": "LEGITIMATE_EDGE_CASE",
        "severity": "LOW",
        "is_legitimate": True,
    },
}


class LiveDigitalTwinInjectionService:
    """Orchestrates live digital-twin synthetic anomaly generation and full pipeline routing."""

    def __init__(self):
        self.control_engine = ControlEngine()
        self.detection_service = ExceptionDetectionService()
        self.investigation_service = InvestigationService()
        self.risk_engine = RiskAssessmentService()
        self.policy_service = PolicyService()

    @staticmethod
    def get_supported_families() -> List[Dict[str, Any]]:
        """Returns metadata for all supported injection families."""
        return list(SUPPORTED_INJECTION_FAMILIES.values())

    @staticmethod
    def validate_family(family: str) -> str:
        """Validates that the requested anomaly family is supported."""
        normalized = family.strip().upper()
        if normalized not in SUPPORTED_INJECTION_FAMILIES:
            raise ValueError(
                f"Unsupported injection family '{family}'. Supported families: "
                f"{list(SUPPORTED_INJECTION_FAMILIES.keys())}"
            )
        return normalized

    def execute_injection(
        self,
        session: Session,
        exception_family: str,
        triggered_by: str = "demo-operator",
        idempotency_key: Optional[str] = None,
        account_id: str = "nodal_escrow_main",
    ) -> Dict[str, Any]:
        """Synchronously executes the full live injection and returns structured results."""
        stages_log = []
        final_result = None

        for event in self.stream_injection_progress(
            session=session,
            exception_family=exception_family,
            triggered_by=triggered_by,
            idempotency_key=idempotency_key,
            account_id=account_id,
        ):
            stages_log.append(event)
            if event.get("stage") == "INJECTION_COMPLETE":
                final_result = event.get("data")

        if final_result:
            final_result["stages"] = stages_log
            return final_result

        return {
            "status": "FAILED",
            "message": "Injection execution failed to complete all stages.",
            "stages": stages_log,
        }

    def stream_injection_progress(
        self,
        session: Session,
        exception_family: str,
        triggered_by: str = "demo-operator",
        idempotency_key: Optional[str] = None,
        account_id: str = "nodal_escrow_main",
    ) -> Generator[Dict[str, Any], None, None]:
        """Executes injection step-by-step, yielding genuine real-time progress events."""
        # 1. Validation & Idempotency Check
        valid_family = self.validate_family(exception_family)
        now = datetime.now(timezone.utc)

        if idempotency_key:
            existing_inj = session.scalars(
                select(InjectedCase).where(InjectedCase.idempotency_key == idempotency_key)
            ).first()
            if existing_inj:
                details = json.loads(existing_inj.details_json or "{}")
                gen_ids = json.loads(existing_inj.generated_identifiers or "{}")
                yield {
                    "stage": "INJECTION_ACCEPTED",
                    "timestamp": now.isoformat(),
                    "message": f"Idempotent request matched previous injection {existing_inj.injection_id}.",
                    "injection_id": existing_inj.injection_id,
                }
                yield {
                    "stage": "INJECTION_COMPLETE",
                    "timestamp": now.isoformat(),
                    "message": "Injection retrieved from idempotency store.",
                    "data": {
                        "injection_id": existing_inj.injection_id,
                        "exception_family": existing_inj.exception_family,
                        "source_flag": existing_inj.source_flag,
                        "triggered_by": existing_inj.triggered_by,
                        "triggered_at": existing_inj.triggered_at.isoformat(),
                        "generated_record_identifiers": gen_ids,
                        "processing_status": existing_inj.status,
                        "linked_exception_id": existing_inj.linked_exception_id,
                        "exception_state": details.get("exception_state", "UNKNOWN"),
                        "message": "Idempotent injection replay",
                    },
                }
                return

        injection_id = f"inj_live_{secrets.token_hex(8)}"
        id_tag = secrets.token_hex(4).upper()

        yield {
            "stage": "INJECTION_ACCEPTED",
            "timestamp": now.isoformat(),
            "message": f"Accepted live injection request for family '{valid_family}'.",
            "injection_id": injection_id,
            "exception_family": valid_family,
            "triggered_by": triggered_by,
        }

        # 2. Generate Fresh Synthetic Operational Records
        seed = secrets.randbits(32)
        gen_config = GeneratorConfig(total_target_records=5, base_timestamp=now)
        ctx = GenerationContext(seed=seed, config=gen_config, id_prefix=f"INJ{id_tag}-")

        # Sync ledger baseline if existing ledger entries exist
        latest_ledger = session.scalars(
            select(NodalLedgerEntry).order_by(NodalLedgerEntry.id.desc())
        ).first()
        if latest_ledger and latest_ledger.balance_after:
            ctx.current_ledger_balance = latest_ledger.balance_after

        # Invoke the exact same scenario generator functions
        if valid_family == "GHOST_SETTLEMENT":
            generate_ghost_settlement_scenario(ctx, index=0)
        elif valid_family == "REFUND_CHARGEBACK_DOUBLE_DIP":
            generate_refund_chargeback_scenario(ctx, index=0)
        elif valid_family == "SETTLEMENT_SLA_BREACH":
            generate_sla_breach_scenario(ctx, index=0)
        elif valid_family == "MISSING_SETTLEMENT":
            generate_missing_settlement_scenario(ctx, index=0)
        elif valid_family == "UNALLOCATED_SETTLEMENT":
            generate_unallocated_settlement_scenario(ctx, index=0)
        elif valid_family == "PARTIAL_SETTLEMENT":
            generate_partial_settlement_scenario(ctx, index=0)
        elif valid_family == "LEGITIMATE_TIMING_EXCEPTION":
            generate_timing_exception_scenario(ctx, index=0)

        # 3. Persist Operational Records ONLY (Ground Truth is Strictly Isolated)
        fin_repo = FinancialSourceRepository(session)
        gen_identifiers: Dict[str, Any] = {
            "payments": [tx.payment_id for tx in ctx.gateway_transactions],
            "orders": [o.order_id for o in ctx.merchant_orders],
            "settlements": [s.settlement_id for s in ctx.settlement_batches],
            "disputes": [d.event_id for d in ctx.dispute_events],
            "ledgers": [l.ledger_id for l in ctx.ledger_entries],
        }

        for tx in ctx.gateway_transactions:
            fin_repo.add_gateway_transaction(tx)
        for order in ctx.merchant_orders:
            fin_repo.add_merchant_order(order)
        for settlement in ctx.settlement_batches:
            fin_repo.add_settlement_batch(settlement)
        for event in ctx.dispute_events:
            fin_repo.add_dispute_event(event)
        for ledger in ctx.ledger_entries:
            fin_repo.add_ledger_entry(ledger)

        session.flush()

        yield {
            "stage": "RECORDS_GENERATED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"Generated fresh operational records with prefix 'INJ{id_tag}-'.",
            "generated_identifiers": gen_identifiers,
            "counts": {
                "gateway_transactions": len(ctx.gateway_transactions),
                "merchant_orders": len(ctx.merchant_orders),
                "settlement_batches": len(ctx.settlement_batches),
                "dispute_events": len(ctx.dispute_events),
                "ledger_entries": len(ctx.ledger_entries),
            },
        }

        # 4. Create InjectedCase Record
        injected_case = InjectedCase(
            injection_id=injection_id,
            exception_family=valid_family,
            triggered_by=triggered_by,
            triggered_at=now,
            source_flag="live-injected",
            idempotency_key=idempotency_key,
            status="PROCESSING",
            generated_identifiers=json.dumps(gen_identifiers),
        )
        session.add(injected_case)
        session.flush()

        # 5. Run Deterministic Controls
        yield {
            "stage": "CONTROLS_RUNNING",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Executing deterministic financial invariants and reconciliation engine.",
        }

        control_report = self.control_engine.run_all_controls(session=session, account_id=account_id)

        # 6. Run Exception Detection Pipeline
        yield {
            "stage": "DETECTION_RUNNING",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Running deterministic exception detection across operational findings.",
        }

        det_report = self.detection_service.detect_exceptions(session=session, account_id=account_id)
        session.flush()

        # Identify linked exception corresponding to the injected records
        linked_exc: Optional[ExceptionRecord] = None
        target_payment_ids = set(gen_identifiers["payments"])
        target_settlement_ids = set(gen_identifiers["settlements"])

        all_exceptions = list(session.scalars(select(ExceptionRecord)).all())
        for exc in all_exceptions:
            if exc.primary_payment_id and exc.primary_payment_id in target_payment_ids:
                linked_exc = exc
                break
            # For unallocated settlements without payment_id, match by settlement ID
            if not linked_exc and exc.primary_payment_id is None:
                if any(target_id in (exc.description or "") or target_id in exc.exception_id for target_id in target_settlement_ids):
                    linked_exc = exc
                    break

        if linked_exc:
            # Mark ExceptionRecord as live-injected
            linked_exc.source_flag = "live-injected"
            injected_case.linked_exception_id = linked_exc.exception_id
            session.flush()

            yield {
                "stage": "EXCEPTION_DETECTED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": f"Deterministic engine detected exception '{linked_exc.exception_id}' ({linked_exc.exception_type}).",
                "exception_id": linked_exc.exception_id,
                "exception_type": linked_exc.exception_type,
                "severity": linked_exc.severity,
                "exposure": linked_exc.exposure,
                "state": linked_exc.state,
            }

            # 7. Run AI Investigation Pipeline (if anomalous)
            yield {
                "stage": "INVESTIGATION_RUNNING",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Initiating AI root-cause investigation and evidence reconstruction.",
            }

            inv_res = self.investigation_service.investigate_exception(
                session=session,
                exception_id=linked_exc.exception_id,
                reinvestigate=True,
            )
            session.flush()

            yield {
                "stage": "INVESTIGATION_COMPLETED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": f"Investigation completed with root cause diagnosis.",
                "root_cause": inv_res.get("structured_output", {}).get("root_cause_explanation") if inv_res else None,
                "diagnosis_status": inv_res.get("status") if inv_res else None,
            }

            # 8. Run Exposure & Risk Prioritization
            yield {
                "stage": "RISK_EVALUATION_RUNNING",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Calculating deterministic multi-factor risk assessment and queue priority.",
            }

            risk_assessment = self.risk_engine.assess_exception_risk(
                session=session,
                exception_id=linked_exc.exception_id,
                force_recalculate=True,
            )
            session.flush()

            yield {
                "stage": "RISK_EVALUATED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": f"Risk assessed: Priority {risk_assessment.priority} (Score {risk_assessment.risk_score}).",
                "priority": risk_assessment.priority,
                "risk_score": float(risk_assessment.risk_score),
            }

            # 9. Run Policy Engine Evaluation
            yield {
                "stage": "POLICY_EVALUATION_RUNNING",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Evaluating deterministic governance policy rules and gating matrix.",
            }

            policy_decision = self.policy_service.evaluate_policy(
                session=session,
                exception_id=linked_exc.exception_id,
                requested_action="INVESTIGATE",
                simulation=False,
            )
            session.flush()

            yield {
                "stage": "POLICY_DECIDED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": f"Policy decision: {policy_decision.decision} for INVESTIGATE action.",
                "decision": policy_decision.decision,
                "action_type": "INVESTIGATE",
            }
        else:
            yield {
                "stage": "NO_EXCEPTION_REQUIRED",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Deterministic controls verified state as clean or within acceptable thresholds.",
            }

        # 10. Persist Audit Record
        injected_case.status = "COMPLETED"
        injected_case.details_json = json.dumps({
            "linked_exception_id": linked_exc.exception_id if linked_exc else None,
            "exception_state": linked_exc.state if linked_exc else "NO_EXCEPTION",
            "exception_type": linked_exc.exception_type if linked_exc else valid_family,
            "exposure": linked_exc.exposure if linked_exc else 0,
            "generated_identifiers": gen_identifiers,
        })

        audit_repo = AuditRepository(session)
        audit_payload = {
            "injection_id": injection_id,
            "exception_family": valid_family,
            "triggered_by": triggered_by,
            "source_flag": "live-injected",
            "generated_identifiers": gen_identifiers,
            "linked_exception_id": linked_exc.exception_id if linked_exc else None,
            "exception_state": linked_exc.state if linked_exc else None,
            "processing_status": "COMPLETED",
        }

        audit_event = AuditEvent(
            audit_event_id=f"audit_inj_{secrets.token_hex(8)}",
            exception_id=linked_exc.exception_id if linked_exc else None,
            event_type="LIVE_CASE_INJECTED",
            timestamp=datetime.now(timezone.utc),
            actor_type="DEMO_OPERATOR",
            actor_id=triggered_by,
            event_summary=f"Live Digital-Twin Injection: {valid_family} (ID: {injection_id})",
            event_payload=json.dumps(audit_payload),
        )
        audit_repo.append_audit_event(audit_event)

        session.commit()

        yield {
            "stage": "AUDIT_RECORDED",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": f"Immutable audit record logged (Event: LIVE_CASE_INJECTED).",
            "audit_event_id": audit_event.audit_event_id,
        }

        # 11. Final Completion Event
        yield {
            "stage": "INJECTION_COMPLETE",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Live Digital-Twin case successfully processed through the end-to-end pipeline.",
            "data": {
                "injection_id": injection_id,
                "exception_family": valid_family,
                "source_flag": "live-injected",
                "triggered_by": triggered_by,
                "triggered_at": now.isoformat(),
                "generated_record_identifiers": gen_identifiers,
                "processing_status": "COMPLETED",
                "linked_exception_id": linked_exc.exception_id if linked_exc else None,
                "exception_state": linked_exc.state if linked_exc else None,
                "exception_type": linked_exc.exception_type if linked_exc else valid_family,
                "exposure": linked_exc.exposure if linked_exc else 0,
                "message": "Live synthetic anomaly successfully injected and fully processed.",
            },
        }
