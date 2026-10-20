"""Deterministic adaptive decision memory for EXISTING Sales Director proof review.

Every evaluation is pure and non-executing. A trusted existing scheduler/owner
may invoke on source changes and persist the small privacy-safe checkpoint.
No model inference, generic retries, new agents, CRM writes or outbound sends.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any

from empire_os.commercial_sales_director_original_proof import SAFE_SOURCE_BLOCKERS

SCHEMA = "empire.commercial.sales_director_adaptive_recheck.v1"
PROOF_SCHEMA = "empire.commercial.sales_director_original_proof_handoff.v1"
SOURCE_KINDS = frozenset({
    "conversation_recovery", "conversation_control_collector",
    "conversation_control_linkage", "conversation_control_health",
    "founder_mailbox_observer", "identity_discovery", "identity_gap",
    "commercial_catalog", "revenue_distribution", "promotion_research",
})
OWNERS = frozenset({
    "sales_director_operator", "commercial_source_owners",
    "conversation_evidence_owner", "conversation_identity_owner",
})
KNOWN_ACTIONS = frozenset({
    "REFRESH_ORIGINAL_COMMERCIAL_SOURCE_EVIDENCE_FIRST",
    "REVIEW_SUPPRESSION_AND_MISSING_CANONICAL_CONTEXT_NO_OUTREACH",
    "RECONCILE_AMBIGUOUS_OR_DUPLICATE_ORIGINAL_THREAD_LINK",
    "RECONCILE_UNMATCHED_ORIGINAL_INTENT_RECEIPT",
    "VERIFY_ORIGINAL_PROVIDER_INBOUND_AND_TENANT_CONTACT_BINDING",
})
SHA = re.compile(r"^[0-9a-f]{64}$")
MAX_CASES = 5000
# Existing owners only; these instructions are never automatically dispatched.
ACTION_OWNER = {
    "REVIEW_SUPPRESSION_AND_MISSING_CANONICAL_CONTEXT_NO_OUTREACH": "sales_director_operator",
    "RECONCILE_AMBIGUOUS_OR_DUPLICATE_ORIGINAL_THREAD_LINK": "conversation_identity_owner",
    "RECONCILE_UNMATCHED_ORIGINAL_INTENT_RECEIPT": "conversation_identity_owner",
    "REFRESH_ORIGINAL_COMMERCIAL_SOURCE_EVIDENCE_FIRST": "commercial_source_owners",
    "VERIFY_ORIGINAL_PROVIDER_INBOUND_AND_TENANT_CONTACT_BINDING": "conversation_evidence_owner",
}


def _digest(value: Any) -> str:
    return sha256(json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("ascii")).hexdigest()


def _count(value: Any) -> int | None:
    return value if type(value) is int and 0 <= value <= 1_000_000 else None


def _source_receipts(value: Mapping[str, Any] | None) -> dict[str, str]:
    receipts = value or {}
    if not isinstance(receipts, Mapping) or not set(receipts).issubset(SOURCE_KINDS):
        raise ValueError("only existing owner source receipt names allowed")
    result = {}
    for name, digest in receipts.items():
        if not isinstance(digest, str) or not SHA.fullmatch(digest):
            raise ValueError("owner source digest must be SHA256 hex")
        result[name] = digest
    return dict(sorted(result.items()))


def adaptive_original_proof_review(
    *,
    current: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
    source_receipts: Mapping[str, str] | None,
    now: datetime,
) -> dict[str, Any]:
    """Reassess evidence, suppress repetitive requests and surface safe changes.

    Aggregate controls and source hashes never authenticate an individual reply.
    Case row numbers are ephemeral, so no row-based long-term identity tracking.
    """
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware decision clock required")
    now = now.astimezone(timezone.utc)
    if (
        not isinstance(current, Mapping)
        or current.get("schema_version") != PROOF_SCHEMA
        or current.get("status") != "ORIGINAL_AUTHENTICATED_REPLY_EVIDENCE_HOLD"
        or current.get("mode") != "OBSERVE"
        or current.get("execution_authority") != "none"
        or current.get("outbound_authorized") is not False
        or current.get("crm_mutations") is not False
        or current.get("agent_tasks_created") is not False
        or current.get("database_writes") is not False
        or current.get("original_inbound_provider_events_independently_authenticated") is not False
    ):
        raise ValueError("trusted non-executing original proof report required")
    total = _count(current.get("case_count"))
    summary = current.get("original_evidence_proof_summary")
    actions = current.get("review_actions_not_dispatched")
    cases = current.get("sales_director_case_reviews")
    if (
        total is None or total > MAX_CASES
        or not isinstance(summary, Mapping)
        or not isinstance(actions, Mapping)
        or not isinstance(cases, list) or len(cases) != total
        or not set(actions).issubset(KNOWN_ACTIONS)
        or any(_count(v) is None for v in actions.values())
        or sum(actions.values()) != total
    ):
        raise ValueError("exact bounded original proof cases and actions required")
    for row in cases:
        if (
            not isinstance(row, Mapping)
            or row.get("live_followup_permission") is not False
            or row.get("provider_message_authentication_verified_for_this_case") is not False
            or row.get("commercial_buyer_intent_verified_for_this_case") is not False
            or row.get("agent_job_created") is not False
        ):
            raise ValueError("untrusted case-specific reply and send proof")
    counts = {}
    for name in (
        "total_control_count", "verified_control_count",
        "canonical_message_count", "observed_inbound_reply_candidates",
        "authenticated_inbound_reply_count_verified", "verified_reply_join_count",
    ):
        raw = summary.get(name)
        if raw is not None and _count(raw) is None:
            raise ValueError("invalid original proof count")
        counts[name] = raw
    if counts["total_control_count"] is None or counts["verified_control_count"] is None:
        raise ValueError("original proof control count missing")
    if counts["verified_control_count"] > counts["total_control_count"]:
        raise ValueError("verified controls exceed original control count")
    health = summary.get("founder_mailbox_observer_status")
    if health not in (
        "NO_COMPLETE_INBOUND_MESSAGE", "OBSERVER_ERROR", "VERIFIED_RUNTIME", "NOT_VERIFIED"
    ):
        raise ValueError("original mailbox observer status not allowlisted")
    blockers = current.get("source_blockers_allowlisted")
    if (
        not isinstance(blockers, list) or len(blockers) > 50
        or any(not isinstance(b, str) or b not in SAFE_SOURCE_BLOCKERS for b in blockers)
    ):
        raise ValueError("source blocker format untrusted")
    if type(current.get("casebook_source_refresh_required")) is not bool:
        raise ValueError("casebook refresh gate required")

    source_hashes = _source_receipts(source_receipts)
    # Exclude generated_at, ephemeral row coordinates and all contact details.
    semantic = {
        "case_count": total,
        "action_counts": dict(sorted(actions.items())),
        "owner_proof_counts": counts,
        "source_blockers": sorted(set(blockers)),
        "mailbox_observer": health,
        "casebook_source_refresh_required": current["casebook_source_refresh_required"],
        "status": current["status"],
    }
    semantic_hash = _digest(semantic)

    prior_receipts: dict[str, str] = {}
    prior_semantic: dict[str, Any] | None = None
    if previous is not None:
        if (
            not isinstance(previous, Mapping)
            or previous.get("schema_version") != SCHEMA
            or previous.get("mode") != "OBSERVE"
            or previous.get("execution_authority") != "none"
            or previous.get("outbound_authorized") is not False
            or previous.get("database_writes") is not False
            or previous.get("agent_tasks_created") is not False
            or type(previous.get("operator_attention_due")) is not bool
        ):
            raise ValueError("invalid non-executing previous adaptation checkpoint")
        prior_semantic = previous.get("evidence_semantic_state")
        if not isinstance(prior_semantic, Mapping):
            raise ValueError("previous semantic evidence missing")
        if previous.get("evidence_semantic_hash") != _digest(prior_semantic):
            raise ValueError("previous semantic evidence checksum mismatch")
        prior_receipts = _source_receipts(previous.get("owner_source_receipts"))

    if previous is None:
        transition = "INITIAL_EVIDENCE_REVIEW"
    elif semantic_hash != previous["evidence_semantic_hash"]:
        transition = "MATERIAL_EVIDENCE_STATE_CHANGED"
    elif source_hashes != prior_receipts:
        transition = "OWNER_SOURCE_CHANGED_NO_PROOF_UPGRADE"
    else:
        transition = "UNCHANGED_HOLD_NO_DUPLICATE_WORK"

    changed_sources = sorted(
        name for name in set(source_hashes) | set(prior_receipts)
        if source_hashes.get(name) != prior_receipts.get(name)
    ) if previous is not None else sorted(source_hashes)
    actionable_review = transition in {
        "INITIAL_EVIDENCE_REVIEW", "MATERIAL_EVIDENCE_STATE_CHANGED"
    }
    # Do not auto-reopen suppressed threads even when source proof changes.
    owner_queue = [
        {
            "existing_owner_lane": ACTION_OWNER[name],
            "reason_code": name,
            "historical_case_count": count,
            "review_only": True,
            "task_dispatched": False,
        }
        for name, count in sorted(
            actions.items(), key=lambda x: (
                0 if "SUPPRESSION" in x[0] else
                1 if "AMBIGUOUS" in x[0] or "UNMATCHED" in x[0] else
                2 if "PROVIDER" in x[0] else 3,
                x[0],
            )
        ) if count > 0 and actionable_review
    ]
    if transition == "UNCHANGED_HOLD_NO_DUPLICATE_WORK":
        explanation = "No material evidence change. Keep existing owner holds; do not recreate cases or notify the founder again."
    elif transition == "OWNER_SOURCE_CHANGED_NO_PROOF_UPGRADE":
        explanation = "Existing owner inputs changed, but evidence has not advanced. Re-evaluate quietly; do not duplicate prior review work."
    elif transition == "MATERIAL_EVIDENCE_STATE_CHANGED":
        explanation = "Evidence or case state changed. Reassess existing owner review lanes; any individual reply still requires original provider and tenant proof."
    else:
        explanation = "First evidence review. Record the existing owners' blockers once and await original evidence changes."

    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "ADAPTIVE_REVIEW_HOLD_NO_COMMERCIAL_AUTHORITY",
        "evaluated_at": now.isoformat(),
        "transition": transition,
        "plain_language_reason": explanation,
        "evidence_semantic_state": semantic,
        "evidence_semantic_hash": semantic_hash,
        "owner_source_receipts": source_hashes,
        "changed_owner_source_names": changed_sources,
        "operator_attention_due": actionable_review,
        "duplicate_owner_attention_suppressed": not actionable_review,
        "existing_owner_review_suggestions": owner_queue,
        "source_change_requires_reverification_not_auto_approval": True,
        "recheck_trigger": "ON_ORIGINAL_OWNER_EVIDENCE_CHANGE_OR_EXISTING_OWNER_SCHEDULE",
        "manual_new_agent_dispatch_required": False,
        "case_local_provider_authentication_attested": False,
        "case_local_buyer_intent_attested": False,
        "founder_repeated_blocker_notifications": False,
        "outbound_authorized": False,
        "crm_mutations": False,
        "payment_execution": False,
        "agent_tasks_created": False,
        "database_writes": False,
        "execution_authority": "none",
    }
