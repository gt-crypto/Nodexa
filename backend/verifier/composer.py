"""Deterministic conservative policy composition for Adversarial Verifier.

Enforces the critical invariant:
    FINAL_POLICY_RESTRICTIVENESS >= ORIGINAL_POLICY_RESTRICTIVENESS

The verifier may only make a policy decision MORE conservative, never less.
This module is fully independent of any LLM.
"""
from typing import Tuple


# ────────────────────────────────────────────────────────────────────────────
# Policy Restrictiveness Ranking (Higher number = More restrictive)
# ────────────────────────────────────────────────────────────────────────────

POLICY_RESTRICTIVENESS = {
    # Least restrictive — allows autonomous remediation
    "ALLOW": 0,
    "ALLOW_WITH_CONDITIONS": 0,
    # Moderate — requires human gate
    "REQUIRE_APPROVAL": 1,
    "REQUIRE_ESCALATION": 1,
    "HUMAN_REVIEW": 1,
    "INSUFFICIENT_EVIDENCE": 1,
    # Most restrictive — action blocked
    "BLOCK": 2,
}


def get_restrictiveness_rank(policy: str) -> int:
    """Returns the restrictiveness rank for a policy decision.

    Unknown policies are treated as maximally restrictive (BLOCK)
    to maintain safety.
    """
    return POLICY_RESTRICTIVENESS.get(policy.upper(), 2)


def compose_conservative_policy(
    original_policy: str,
    verdict: str,
    recommended_action: str,
) -> Tuple[str, int, int]:
    """Composes the final conservative policy from original decision and verifier verdict.

    Returns:
        (final_policy, original_rank, final_rank)

    Critical invariant:
        final_rank >= original_rank  (ALWAYS)
    """
    original_rank = get_restrictiveness_rank(original_policy)

    if verdict == "AGREE":
        # Verifier agrees — original policy stands unchanged
        return original_policy, original_rank, original_rank

    elif verdict == "ABSTAIN":
        # Verifier cannot reach a supported opinion — conservative default:
        # If original allows, tighten to HUMAN_REVIEW; otherwise keep
        if original_rank < 1:
            return "HUMAN_REVIEW", original_rank, 1
        return original_policy, original_rank, original_rank

    elif verdict == "TIGHTEN":
        # Verifier recommends a more conservative outcome
        recommended_rank = get_restrictiveness_rank(recommended_action)
        # Ensure we only move MORE restrictive
        final_rank = max(original_rank, recommended_rank)
        if final_rank > original_rank:
            final_policy = recommended_action if recommended_rank == final_rank else _rank_to_policy(final_rank)
        else:
            # If recommended is equally or less restrictive, at least tighten by one step
            final_rank = min(original_rank + 1, 2)
            final_policy = _rank_to_policy(final_rank)
        return final_policy, original_rank, final_rank

    elif verdict == "DISPUTE":
        # Verifier independently disagrees — must not loosen, always tighten
        recommended_rank = get_restrictiveness_rank(recommended_action)
        final_rank = max(original_rank, recommended_rank, 1)  # At minimum HUMAN_REVIEW
        if final_rank > original_rank:
            final_policy = recommended_action if recommended_rank == final_rank else _rank_to_policy(final_rank)
        else:
            final_policy = original_policy
        return final_policy, original_rank, final_rank

    else:
        # Unknown verdict — treat as maximally conservative
        return "BLOCK", original_rank, 2


def _rank_to_policy(rank: int) -> str:
    """Converts a restrictiveness rank back to a policy string."""
    if rank <= 0:
        return "ALLOW"
    elif rank == 1:
        return "HUMAN_REVIEW"
    else:
        return "BLOCK"
