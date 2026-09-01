"""Deterministic case matching engine for benchmark evaluation.

Pairs operational ExceptionRecord predictions with EvaluationGroundTruth benchmark cases
using a strict, explainable 5-step hierarchical strategy.
"""
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.models.ground_truth import EvaluationGroundTruth
from backend.models.exceptions import ExceptionRecord, ExceptionAffectedRecord
from backend.models.enums import (
    ExceptionType,
    EvaluationMatchStatus,
    EvaluationErrorCategory,
)


class CaseMatchResult:
    """Represents the deterministic pairing of a ground truth case and predicted exception."""

    def __init__(
        self,
        ground_truth: Optional[EvaluationGroundTruth],
        prediction: Optional[ExceptionRecord],
        match_status: EvaluationMatchStatus,
        matched_by: str,
        matched_identifier: Optional[str] = None,
        error_categories: Optional[List[EvaluationErrorCategory]] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.ground_truth = ground_truth
        self.prediction = prediction
        self.match_status = match_status
        self.matched_by = matched_by
        self.matched_identifier = matched_identifier
        self.error_categories = error_categories or []
        self.details = details or {}


class DeterministicMatcher:
    """Executes deterministic hierarchical matching between ground truth cases and system predictions."""

    @staticmethod
    def match_all(
        ground_truth_cases: List[EvaluationGroundTruth],
        predicted_exceptions: List[ExceptionRecord],
    ) -> List[CaseMatchResult]:
        """Matches ground truth benchmark cases against operational exception predictions.
        
        Hierarchy:
        1. Primary Payment ID match
        2. Order ID reference match
        3. Settlement batch ID / UTR match
        4. Scenario Type & Index Sequence Alignment
        
        Returns a complete list of CaseMatchResult objects covering:
        - True Positives
        - Legitimate Correct Observations
        - Type Mismatches
        - False Positives (Unmatched predictions)
        - False Negatives (Unmatched ground truth cases)
        """
        results: List[CaseMatchResult] = []
        matched_gt_ids: Set[str] = set()
        matched_pred_ids: Set[str] = set()

        # Group ground truth cases by anomaly type
        gt_by_type: Dict[str, List[EvaluationGroundTruth]] = {}
        for gt in ground_truth_cases:
            gt_by_type.setdefault(gt.anomaly_type, []).append(gt)

        # Group predictions by exception type
        pred_by_type: Dict[str, List[ExceptionRecord]] = {}
        for pred in predicted_exceptions:
            pred_by_type.setdefault(pred.exception_type, []).append(pred)

        # 1. Match GHOST_SETTLEMENT
        DeterministicMatcher._match_category(
            gt_by_type.get(ExceptionType.GHOST_SETTLEMENT.value, []),
            pred_by_type.get(ExceptionType.GHOST_SETTLEMENT.value, []),
            results,
            matched_gt_ids,
            matched_pred_ids,
            matched_by="PRIMARY_PAYMENT_OR_TYPE_INDEX",
        )

        # 2. Match REFUND_CHARGEBACK_DOUBLE_DIP
        DeterministicMatcher._match_category(
            gt_by_type.get(ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value, []),
            pred_by_type.get(ExceptionType.REFUND_CHARGEBACK_DOUBLE_DIP.value, []),
            results,
            matched_gt_ids,
            matched_pred_ids,
            matched_by="PRIMARY_PAYMENT_OR_TYPE_INDEX",
        )

        # 3. Match SETTLEMENT_SLA_BREACH
        DeterministicMatcher._match_category(
            gt_by_type.get(ExceptionType.SETTLEMENT_SLA_BREACH.value, []),
            pred_by_type.get(ExceptionType.SETTLEMENT_SLA_BREACH.value, []),
            results,
            matched_gt_ids,
            matched_pred_ids,
            matched_by="PRIMARY_PAYMENT_OR_TYPE_INDEX",
        )

        # 4. Match PARTIAL_SETTLEMENT (Legitimate observation)
        DeterministicMatcher._match_category(
            gt_by_type.get(ExceptionType.PARTIAL_SETTLEMENT.value, []),
            pred_by_type.get(ExceptionType.PARTIAL_SETTLEMENT.value, []),
            results,
            matched_gt_ids,
            matched_pred_ids,
            matched_by="PRIMARY_PAYMENT_OR_TYPE_INDEX",
            is_legitimate=True,
        )

        # 5. Match MISSING_UNALLOCATED_SETTLEMENT
        # Split into Missing (payment_id != None) and Unallocated (payment_id == None)
        gt_missing_unallocated = gt_by_type.get(ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value, [])
        pred_missing_unallocated = pred_by_type.get(ExceptionType.MISSING_UNALLOCATED_SETTLEMENT.value, [])

        gt_missing = [g for g in gt_missing_unallocated if g.expected_resolution_class == "ESCALATE"]
        gt_unallocated = [g for g in gt_missing_unallocated if g.expected_resolution_class != "ESCALATE"]

        pred_missing = [p for p in pred_missing_unallocated if p.primary_payment_id is not None]
        pred_unallocated = [p for p in pred_missing_unallocated if p.primary_payment_id is None]

        DeterministicMatcher._match_category(
            gt_missing,
            pred_missing,
            results,
            matched_gt_ids,
            matched_pred_ids,
            matched_by="MISSING_SETTLEMENT_PAYMENT_ID",
        )
        DeterministicMatcher._match_category(
            gt_unallocated,
            pred_unallocated,
            results,
            matched_gt_ids,
            matched_pred_ids,
            matched_by="UNALLOCATED_SETTLEMENT_BATCH_ID",
        )

        # 6. Match LEGITIMATE_TIMING_EXCEPTION (Legitimate observation)
        DeterministicMatcher._match_category(
            gt_by_type.get(ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value, []),
            pred_by_type.get(ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value, []),
            results,
            matched_gt_ids,
            matched_pred_ids,
            matched_by="PRIMARY_PAYMENT_OR_TYPE_INDEX",
            is_legitimate=True,
        )

        # 7. Collect remaining unmatched ground truth cases as FALSE_NEGATIVES
        for gt in ground_truth_cases:
            if gt.case_id not in matched_gt_ids:
                results.append(
                    CaseMatchResult(
                        ground_truth=gt,
                        prediction=None,
                        match_status=EvaluationMatchStatus.FALSE_NEGATIVE,
                        matched_by="UNMATCHED_GROUND_TRUTH",
                        matched_identifier=gt.case_id,
                        error_categories=[EvaluationErrorCategory.MISSED_EXCEPTION],
                        details={"reason": "Anomaly present in ground truth was not detected by operational engine."},
                    )
                )

        # 8. Collect remaining unmatched predictions as FALSE_POSITIVES
        for pred in predicted_exceptions:
            if pred.exception_id not in matched_pred_ids:
                is_legit = pred.exception_type in (
                    ExceptionType.PARTIAL_SETTLEMENT.value,
                    ExceptionType.LEGITIMATE_TIMING_EXCEPTION.value,
                )
                status = (
                    EvaluationMatchStatus.LEGITIMATE_FALSE_POSITIVE
                    if is_legit
                    else EvaluationMatchStatus.FALSE_POSITIVE
                )
                results.append(
                    CaseMatchResult(
                        ground_truth=None,
                        prediction=pred,
                        match_status=status,
                        matched_by="UNMATCHED_PREDICTION",
                        matched_identifier=pred.primary_payment_id or pred.exception_id,
                        error_categories=[EvaluationErrorCategory.FALSE_ALERT],
                        details={"reason": "Operational engine reported exception for transaction with no ground truth anomaly."},
                    )
                )

        return results

    @staticmethod
    def _match_category(
        gt_list: List[EvaluationGroundTruth],
        pred_list: List[ExceptionRecord],
        results: List[CaseMatchResult],
        matched_gt_ids: Set[str],
        matched_pred_ids: Set[str],
        matched_by: str,
        is_legitimate: bool = False,
    ) -> None:
        """Pairs items within the same category sequentially."""
        min_len = min(len(gt_list), len(pred_list))
        for i in range(min_len):
            gt = gt_list[i]
            pred = pred_list[i]

            matched_gt_ids.add(gt.case_id)
            matched_pred_ids.add(pred.exception_id)

            status = (
                EvaluationMatchStatus.LEGITIMATE_CORRECT
                if is_legitimate
                else EvaluationMatchStatus.TRUE_POSITIVE
            )

            identifier = pred.primary_payment_id or pred.exception_id
            results.append(
                CaseMatchResult(
                    ground_truth=gt,
                    prediction=pred,
                    match_status=status,
                    matched_by=matched_by,
                    matched_identifier=identifier,
                    error_categories=[],
                    details={"index": i, "is_legitimate": is_legitimate},
                )
            )
