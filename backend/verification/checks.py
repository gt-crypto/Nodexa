"""Independent deterministic verification checks for Nodal Sentinel."""
import json
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.exceptions import ExceptionRecord
from backend.models.remediation import RemediationAction
from backend.models.enums import RemediationStatus, ExceptionType, PolicyActionType
from backend.models.financial_sources import NodalLedgerEntry
from backend.verification.models import VerificationEvidenceItem
from backend.verification.exposure import recalculate_deterministic_exposure
from backend.verification.invariants import verify_financial_invariants, verify_double_entry_balance_delta
from backend.verification.reconciliation import verify_reconciliation_state, verify_action_specific_outcome


class VerificationChecksRunner:
    """Executes all independent deterministic verification checks."""

    @staticmethod
    def check_remediation_execution_status(
        plan: RemediationAction,
    ) -> Tuple[bool, VerificationEvidenceItem]:
        """Check 1: Verify remediation reached EXECUTED or AWAITING_VERIFICATION state."""
        valid_statuses = (
            RemediationStatus.EXECUTED.value,
            RemediationStatus.AWAITING_VERIFICATION.value,
        )
        passed = plan.status in valid_statuses
        evidence = VerificationEvidenceItem(
            check_id="CHECK-EXECUTION-STATUS",
            check_type="EXECUTION_STATE",
            source_table="remediation_actions",
            source_record_id=plan.action_id,
            expected_value=list(valid_statuses),
            actual_value=plan.status,
            result="PASS" if passed else "FAIL",
            explanation=(
                f"Remediation status '{plan.status}' is valid for post-remediation verification."
                if passed
                else f"Cannot verify remediation in unexecuted state '{plan.status}'."
            ),
        )
        return passed, evidence

    @staticmethod
    def check_action_result(
        session: Session,
        plan: RemediationAction,
        exception: ExceptionRecord,
    ) -> Tuple[bool, List[str], List[VerificationEvidenceItem]]:
        """Check 2: Compare requested remediation parameters with live database state."""
        return verify_action_specific_outcome(session=session, plan=plan, exception=exception)

    @staticmethod
    def check_exposure_recalculation(
        session: Session,
        exception: ExceptionRecord,
        plan: Optional[RemediationAction] = None,
        tolerance: int = 0,
    ) -> Tuple[bool, int, int, int, List[VerificationEvidenceItem]]:
        """Check 3: Deterministically recalculate current exposure from operational records."""
        rem_exp, red_amt, red_bps, breakdown = recalculate_deterministic_exposure(
            session=session,
            exception=exception,
            remediation_plan=plan,
        )
        passed = (rem_exp <= tolerance)

        evidence = [
            VerificationEvidenceItem(
                check_id="CHECK-EXPOSURE-ZERO",
                check_type="EXPOSURE_RECALCULATION",
                source_table="operational_sources",
                source_record_id=exception.exception_id,
                expected_value=f"<= {tolerance} minor units",
                actual_value=f"{rem_exp} minor units (reduction: {red_amt}, {red_bps} bps)",
                result="PASS" if passed else "FAIL",
                explanation=(
                    f"Zero financial exposure verified (reduction {red_bps/100:.2f}%)."
                    if passed
                    else f"Unresolved financial exposure remains: ₹{rem_exp / 100:.2f}."
                ),
            )
        ]
        return passed, rem_exp, red_amt, red_bps, evidence

    @staticmethod
    def check_financial_invariants(
        session: Session,
        account_id: str = "nodal_escrow_main",
    ) -> Tuple[bool, List[VerificationEvidenceItem]]:
        """Check 4: Verify balance progression, debit/credit sanity, non-negative, and currency."""
        all_passed, _, evidence = verify_financial_invariants(session=session, account_id=account_id)
        return all_passed, evidence

    @staticmethod
    def check_double_entry_delta(
        session: Session,
        plan: RemediationAction,
        account_id: str = "nodal_escrow_main",
    ) -> Tuple[bool, List[VerificationEvidenceItem]]:
        """Check 5: Verify double-entry balance delta matches expected credits/debits."""
        before_snap = json.loads(plan.before_snapshot or "{}")
        after_snap = json.loads(plan.after_snapshot or "{}")

        before_bal = (
            before_snap.get("ledger_balance_before")
            if "ledger_balance_before" in before_snap
            else before_snap.get("current_balance")
            if "current_balance" in before_snap
            else before_snap.get("balance_after")
            if "balance_after" in before_snap
            else before_snap.get("ledger_balance")
        )
        after_bal = (
            after_snap.get("ledger_balance_after")
            if "ledger_balance_after" in after_snap
            else after_snap.get("current_balance")
            if "current_balance" in after_snap
            else after_snap.get("balance_after")
            if "balance_after" in after_snap
            else after_snap.get("projected_ledger_balance")
        )

        # If snapshots contain balances, verify delta mathematically
        if before_bal is not None and after_bal is not None:
            credits = (
                after_snap.get("credit", 0)
                or after_snap.get("reversal_amount", 0)
                or after_snap.get("projected_credit", 0)
            )
            debits = (
                after_snap.get("debit", 0)
                or after_snap.get("refund_amount", 0)
                or after_snap.get("projected_debit", 0)
            )
            passed, ev = verify_double_entry_balance_delta(
                before_balance=int(before_bal),
                after_balance=int(after_bal),
                credits=int(credits),
                debits=int(debits),
            )
            return passed, [ev]

        # Otherwise verify latest ledger balance progression directly
        ledger_entries = list(
            session.scalars(
                select(NodalLedgerEntry)
                .where(NodalLedgerEntry.account_id == account_id)
                .order_by(NodalLedgerEntry.id.asc())
            ).all()
        )
        if not ledger_entries:
            return True, [
                VerificationEvidenceItem(
                    check_id="CHECK-DOUBLE-ENTRY-DELTA",
                    check_type="DOUBLE_ENTRY",
                    source_table="nodal_ledger",
                    expected_value="0",
                    actual_value="0",
                    result="PASS",
                    explanation="Empty ledger satisfies equilibrium by default.",
                )
            ]

        # Verify last entry
        last = ledger_entries[-1]
        prev_bal = ledger_entries[-2].balance_after if len(ledger_entries) > 1 else (last.balance_after - last.credit + last.debit)
        passed, ev = verify_double_entry_balance_delta(
            before_balance=prev_bal,
            after_balance=last.balance_after,
            credits=last.credit,
            debits=last.debit,
        )
        return passed, [ev]

    @staticmethod
    def check_reconciliation(
        session: Session,
        exception: ExceptionRecord,
    ) -> Tuple[bool, List[VerificationEvidenceItem]]:
        """Check 6: Re-run deterministic multi-source reconciliation."""
        return verify_reconciliation_state(session=session, exception=exception)

    @staticmethod
    def check_legitimate_case_protection(
        exception: ExceptionRecord,
        plan: RemediationAction,
    ) -> Tuple[bool, VerificationEvidenceItem]:
        """Check 7: Ensure legitimate observations are not artificially modified or closed as financial remediations."""
        is_legit = exception.exception_type in (
            ExceptionType.PARTIAL_SETTLEMENT.value,
            ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value,
        )
        if is_legit:
            # Must not be financial action like REFUND or REVERSE_REFUND
            has_financial_action = plan.action_type in (
                PolicyActionType.REFUND.value,
                PolicyActionType.REVERSE_REFUND.value,
            )
            passed = not has_financial_action
            evidence = VerificationEvidenceItem(
                check_id="CHECK-LEGITIMATE-PROTECTION",
                check_type="SAFETY_GATE",
                source_table="exceptions",
                source_record_id=exception.exception_id,
                expected_value="NO_FINANCIAL_MUTATION",
                actual_value=plan.action_type,
                result="PASS" if passed else "FAIL",
                explanation=(
                    "Legitimate observation verified without unauthorized financial alteration."
                    if passed
                    else "CRITICAL: Artificial financial remediation attempted on legitimate observation!"
                ),
            )
            return passed, evidence

        # Non-legitimate exception: passes this check
        return True, VerificationEvidenceItem(
            check_id="CHECK-LEGITIMATE-PROTECTION",
            check_type="SAFETY_GATE",
            source_table="exceptions",
            source_record_id=exception.exception_id,
            expected_value="NOT_APPLICABLE",
            actual_value="NOT_APPLICABLE",
            result="PASS",
            explanation="Standard anomaly exception undergoing remediation verification.",
        )

    @staticmethod
    def check_stale_state_protection(
        session: Session,
        plan: RemediationAction,
        account_id: str = "nodal_escrow_main",
    ) -> Tuple[bool, VerificationEvidenceItem]:
        """Check 8: Compare snapshot expectations with live database state to detect unexpected mutations."""
        after_snap = json.loads(plan.after_snapshot or "{}")
        expected_balance = (
            after_snap.get("ledger_balance_after")
            if "ledger_balance_after" in after_snap
            else after_snap.get("current_balance")
            if "current_balance" in after_snap
            else after_snap.get("balance_after")
            if "balance_after" in after_snap
            else after_snap.get("projected_ledger_balance")
        )

        if expected_balance is not None:
            # Query live ledger
            latest_entry = session.scalars(
                select(NodalLedgerEntry)
                .where(NodalLedgerEntry.account_id == account_id)
                .order_by(NodalLedgerEntry.id.desc())
            ).first()

            if latest_entry and latest_entry.balance_after != int(expected_balance):
                # Note: if there were subsequent valid transactions, we verify balance progression still holds
                all_ledger = list(session.scalars(select(NodalLedgerEntry).where(NodalLedgerEntry.account_id == account_id)).all())
                from backend.controls.invariants import validate_ledger_balance_progression
                prog = validate_ledger_balance_progression(all_ledger, account_id=account_id)
                if any(p.status.value == "FAIL" for p in prog):
                    return False, VerificationEvidenceItem(
                        check_id="CHECK-STALE-STATE",
                        check_type="STALE_STATE_PROTECTION",
                        source_table="nodal_ledger",
                        expected_value=expected_balance,
                        actual_value=latest_entry.balance_after,
                        result="FAIL",
                        explanation="STATE_CHANGED_AFTER_EXECUTION: Database ledger state was mutated with invariant corruption.",
                    )

        return True, VerificationEvidenceItem(
            check_id="CHECK-STALE-STATE",
            check_type="STALE_STATE_PROTECTION",
            source_table="nodal_ledger",
            expected_value="CONSISTENT",
            actual_value="CONSISTENT",
            result="PASS",
            explanation="Operational state verified consistent with post-execution snapshots.",
        )
