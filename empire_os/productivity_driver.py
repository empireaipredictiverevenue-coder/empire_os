"""Evidence-led productivity review inside the existing completion monitor.

No independent agent, timer, queue, provider invocation, assignment, or
consequential authority. This is a deterministic existing-owner action brief.
"""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping

SCHEMA = "empire.productivity-driver.v1"
MONITOR_SCHEMA = "empire.completion-task-monitor.v1"
MAX_REVIEW = 12

BASE_PRIORITY = {
    "NEEDS_WIRING_OR_TEST_FIX": 100,
    "BUILDER_PROVIDER_BLOCKED": 88,
    "CODE_COMPLETE_NOT_LIVE": 90,
    "RUNTIME_OBSERVED_PENDING_FORMAL_CLOSURE": 88,
    "INDEPENDENT_REVIEW_REQUIRED_BEFORE_RETRY": 85,
    "REVIEW_PRIOR_ATTEMPT": 83,
    "NEEDS_LIVE_PROOF": 78,
    "VERIFY_NOT_MATERIALIZED": 76,
    "VERIFY_QUEUED": 70,
    "VERIFYING": 65,
    "REAL_WORLD_EVIDENCE_REQUIRED": 64,
    "FOUNDER_GATE": 60,
    "FOUNDER_PRICE_POLICY_APPROVED_FORMAL_CLOSURE_PENDING": 58,
    "PLAN_HANDOFF_ONLY_BUILD_OR_VERIFY_PENDING": 40,
    "NEEDS_WIRING": 38,
    "REVIEW_REQUIRED": 30,
}

PROOF = {
    "NEEDS_WIRING_OR_TEST_FIX": "Exact failed verification, bounded repair and passing regression evidence",
    "BUILDER_PROVIDER_BLOCKED": "Independent provider-capacity/recovery evidence before retry",
    "CODE_COMPLETE_NOT_LIVE": "Governed production runtime proof, not just passing tests",
    "RUNTIME_OBSERVED_PENDING_FORMAL_CLOSURE": "Exact independent runtime closeout and checklist verification",
    "NEEDS_LIVE_PROOF": "Genuine production runtime proof and source provenance",
    "REAL_WORLD_EVIDENCE_REQUIRED": "Genuine buyer/customer outcome, not generated or test data",
    "FOUNDER_GATE": "Existing founder approval evidence and prerequisites; do not grant approval",
    "FOUNDER_PRICE_POLICY_APPROVED_FORMAL_CLOSURE_PENDING": "Price approval already recorded; independent closeout only",
    "PLAN_HANDOFF_ONLY_BUILD_OR_VERIFY_PENDING": "Actual implementation, tests, and owner verification; PLAN alone is insufficient",
}

# A workstream's relative commercial importance is an ordering heuristic,
# not independent evidence of a customer, sale or a verified market.
OWNER_BONUS = {"sales_revenue": 15, "operations_fulfilment": 5, "product": 5, "marketing_growth": 4}
COMMERCIAL_PROOF_STATES = frozenset({
    "REAL_WORLD_EVIDENCE_REQUIRED", "NEEDS_LIVE_PROOF",
    "CODE_COMPLETE_NOT_LIVE", "RUNTIME_OBSERVED_PENDING_FORMAL_CLOSURE",
    "NEEDS_WIRING_OR_TEST_FIX",
})


def _held(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA,
        "status": "HELD",
        "reason": reason,
        "mode": "OBSERVE",
        "review_candidates": [],
        "owner_review_counts": {},
        "execution_authority": "none",
        "work_dispatched": False,
        "commercial_outcome_verified": False,
    }


def build_productivity_review(monitor: Mapping[str, Any]) -> dict[str, Any]:
    """Rank only identified, monitored tasks. Never perform or imply execution."""
    if (not isinstance(monitor, Mapping)
            or monitor.get("schema_version") != MONITOR_SCHEMA
            or monitor.get("status") != "AVAILABLE"
            or monitor.get("mode") != "OBSERVE"
            or monitor.get("execution_authority") != "none"
            or monitor.get("external_execution_performed") is not False
            or monitor.get("automatic_checklist_mutation_allowed") is not False):
        return _held("untrusted_monitor_contract")

    rows = monitor.get("items")
    held = monitor.get("invalid_task_identity_hold_count", 0)
    if (not isinstance(rows, list)
            or type(monitor.get("tracked_pending_count")) is not int
            or len(rows) != monitor["tracked_pending_count"]
            or type(held) is not int or held < 0):
        return _held("monitor_count_invalid")

    verified: list[dict[str, Any]] = []
    keys: set[str] = set()
    for row in rows:
        if not isinstance(row, Mapping):
            return _held("monitor_row_invalid")
        key, owner, state = row.get("task_key"), row.get("department"), row.get("state")
        if (not isinstance(key, str) or not key.startswith("task_") or key in keys
                or not isinstance(owner, str) or not owner
                or not isinstance(state, str) or state not in BASE_PRIORITY
                or row.get("execution_authority") != "none"
                or row.get("commercial_outcome_verified") is not False
                or type(row.get("line")) is not int):
            return _held("monitor_identity_or_authority_invalid")
        keys.add(key)
        # Freshness is monitored by the upstream source. Do not claim elapsed
        # time since project inception from a first observational snapshot.
        stale = "NO_OBSERVED_STAGE_CHANGE_24H" in (row.get("signals") or ())
        score = (BASE_PRIORITY[state] + OWNER_BONUS.get(owner, 0)
                 + (20 if owner == "sales_revenue" and state in COMMERCIAL_PROOF_STATES else 0)
                 + (5 if stale else 0))
        gate = ("FOUNDER_APPROVAL_REQUIRED" if state == "FOUNDER_GATE"
                else "FORMAL_CLOSEOUT_REQUIRED" if state in {
                    "RUNTIME_OBSERVED_PENDING_FORMAL_CLOSURE",
                    "FOUNDER_PRICE_POLICY_APPROVED_FORMAL_CLOSURE_PENDING",
                } else "EVIDENCE_AND_EXISTING_OWNER_REVIEW")
        verified.append({
            "task_key": key,
            "checklist_line": row["line"],
            "owner": owner,
            "state": state,
            "priority_score_heuristic": score,
            "next_step": row.get("next_evidence_step"),
            "required_proof": PROOF.get(state, "Exact existing-owner implementation and verification evidence"),
            "gate": gate,
            "stalled_observation_24h": bool(stale),
            "approved_for_external_execution": False,
        })
    ordered = sorted(
        verified, key=lambda row: (-row["priority_score_heuristic"], row["checklist_line"], row["task_key"])
    )
    return {
        "schema_version": SCHEMA,
        "status": "READY_FOR_EXISTING_OWNER_REVIEW",
        "mode": "OBSERVE",
        "source": "existing_completion_task_monitor",
        "source_observed_at": monitor.get("generated_at"),
        "tracked_pending_count": len(verified),
        "identity_held_pending_count": held,
        "review_candidate_count": len(ordered),
        "review_candidates": ordered[:MAX_REVIEW],
        "owner_review_counts": dict(sorted(Counter(row["owner"] for row in verified).items())),
        "ranking_is_not_independent_commercial_evidence": True,
        "checked_done_is_not_live_verified": True,
        "work_dispatched": False,
        "founder_gates_preserved": True,
        "commercial_outcome_verified": False,
        "execution_authority": "none",
    }
