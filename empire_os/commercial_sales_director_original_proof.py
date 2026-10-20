"""Non-executing Sales Director handoff to EXISTING Conversation OS proof review.

Only original owner reports are read. Aggregate proof/control health is NOT
attributable to any individual thread, contact, buyer or tenant. No outreach,
CRM mutation, buyer promotion or new agent job is ever performed.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

SCHEMA = "empire.commercial.sales_director_original_proof_handoff.v1"
CASEBOOK_SCHEMA = "empire.commercial.conversation_conversion_casebook.v1"
CONVERSATION_PROOF_SCHEMA = "empire.conversation_control_operational_truth.v1"
MAX_CASES = 5000

CASE_STATES = frozenset({
    "SUPPRESSION_OR_CONTEXT_HOLD",
    "AMBIGUOUS_EXACT_THREAD_IDENTITY",
    "MISSING_EXACT_RECOVERY_RECEIPT",
    "FRESH_PROVENANCE_REQUIRED",
    "HISTORICAL_CONTEXT_READY_FOR_HUMAN_REVIEW",
})
SAFE_SOURCE_BLOCKERS = frozenset({
    "SCHEMA_COLUMNS_MISSING",
    "JOIN_CARDINALITY_UNVERIFIED",
    "PROVIDER_THREAD_ORIGINALITY_UNVERIFIED",
    "REPLY_CONTACT_IDENTITY_NOT_AUTHENTICATED",
    "TENANT_AUTHORITY_BINDING_NOT_PROVEN",
    "INBOUND_REPLY_SOURCE_AUTHENTICATION_NOT_PROVEN",
    "COMMERCIAL_INTENT_CLASSIFICATION_NOT_ATTESTED",
    "NO_CANONICAL_INBOUND_MESSAGES_VERIFIED",
    "CANONICAL_CONTROL_SCHEMA_UNVERIFIED",
    "LIVE_COLLECTOR_OR_LINKAGE_NOT_READY",
    "FOUNDER_MAILBOX_READ_UNAVAILABLE",
    "FOUNDER_MAILBOX_OBSERVER_NOT_CURRENTLY_VERIFIED",
    "IDENTITY_DISCOVERY_EVIDENCE_STALE_OR_MISSING",
})


def _count(value: Any) -> int | None:
    return value if type(value) is int and 0 <= value <= 1_000_000 else None


def _rows(value: Any, *, label: str) -> list[int]:
    if not isinstance(value, list) or len(value) > MAX_CASES:
        raise ValueError(label + " requires bounded 1-based list")
    if any(type(i) is not int or not 1 <= i <= 5000 for i in value):
        raise ValueError(label + " contains invalid 1-based row")
    return value


def review_sales_director_original_proof(
    *,
    casebook: Mapping[str, Any],
    conversation_proof: Mapping[str, Any],
    now: datetime,
) -> dict[str, Any]:
    """Enrich historic exact-ID cases with ORIGINAL provider-source health.

    Case-to-provider event binding CANNOT be asserted from aggregate health.
    """
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("timezone-aware review clock required")
    now = now.astimezone(timezone.utc)
    if (
        casebook.get("schema_version") != CASEBOOK_SCHEMA
        or casebook.get("mode") != "OBSERVE"
        or casebook.get("execution_authority") != "none"
        or casebook.get("outbound_authorized") is not False
        or casebook.get("agent_tasks_created") is not False
        or casebook.get("database_writes") is not False
    ):
        raise ValueError("exact non-executing conversation casebook required")
    if (
        conversation_proof.get("schema_version") != CONVERSATION_PROOF_SCHEMA
        or conversation_proof.get("mode") != "OBSERVE"
        or conversation_proof.get("status") != "HOLD_REAL_REPLY_EVIDENCE_REQUIRED"
        or conversation_proof.get("execution_authority") != "NONE"
        or conversation_proof.get("automatic_promotion_authorized") is not False
        or conversation_proof.get("authenticated_reply_identity_verified") is not False
        or conversation_proof.get("tenant_binding_independently_verified") is not False
        or conversation_proof.get("buyer_intent_verified") is not False
        or conversation_proof.get("outbound_enabled") is not False
        or conversation_proof.get("database_writes") is not False
    ):
        raise ValueError("existing Conversation OS original proof gate not trusted")
    case_rows = casebook.get("manual_operator_cases")
    if not isinstance(case_rows, list) or len(case_rows) > MAX_CASES:
        raise ValueError("bounded original casebook rows required")
    if _count(casebook.get("distinct_offer_thread_refs")) != len(case_rows):
        raise ValueError("casebook thread count mismatch")
    if type(casebook.get("source_evidence_refresh_required")) is not bool:
        raise ValueError("casebook source freshness decision missing")

    global_blockers = conversation_proof.get("source_blockers")
    if not isinstance(global_blockers, list):
        raise ValueError("Conversation OS source blocker inventory required")
    # Never echo arbitrary strings supplied by an external evidence packet.
    source_blockers = sorted({
        b for b in global_blockers if isinstance(b, str)
        and b in SAFE_SOURCE_BLOCKERS
    })
    control_count = _count(conversation_proof.get("total_control_count"))
    verified_controls = _count(conversation_proof.get("verified_control_count"))
    if control_count is None or verified_controls is None or verified_controls > control_count:
        raise ValueError("bounded Conversation OS controls required")
    auth_count = _count(conversation_proof.get("authenticated_inbound_reply_count_verified"))
    # Global counts, even if nonzero in a future source, NEVER establish
    # any exact case's inbound authenticity. Enforce owner schema version review.
    canonical_messages = _count(conversation_proof.get("canonical_message_count"))
    observed_candidates = _count(conversation_proof.get("observed_inbound_reply_candidate_count"))
    linked_replies = _count(conversation_proof.get("verified_reply_join_count"))
    old_case_count = casebook.get("source_evidence_refresh_required") is True

    cases = []
    seen = set()
    for row in case_rows:
        if not isinstance(row, Mapping):
            raise ValueError("casebook case must be record")
        case_number = row.get("operator_case_number")
        state = row.get("state")
        if (
            type(case_number) is not int
            or case_number <= 0 or case_number in seen
            or state not in CASE_STATES
            or row.get("owner_lane") != "sales_director_operator"
            or row.get("live_outbound_authorized") is not False
            or row.get("inbound_reply_verified") is not False
            or row.get("agent_task_created") is not False
        ):
            raise ValueError("untrusted casebook case or authority")
        seen.add(case_number)
        original_rows = _rows(row.get("recovery_source_row_numbers"), label="original recovery")
        shadow_rows = _rows(row.get("offer_book_target_row_numbers"), label="shadow offer")
        if not shadow_rows:
            raise ValueError("case missing original offer review reference")

        if state == "SUPPRESSION_OR_CONTEXT_HOLD":
            action = "REVIEW_SUPPRESSION_AND_MISSING_CANONICAL_CONTEXT_NO_OUTREACH"
            lane = "sales_director_operator"
        elif state == "AMBIGUOUS_EXACT_THREAD_IDENTITY":
            action = "RECONCILE_AMBIGUOUS_OR_DUPLICATE_ORIGINAL_THREAD_LINK"
            lane = "conversation_identity_owner"
        elif state == "MISSING_EXACT_RECOVERY_RECEIPT":
            action = "RECONCILE_UNMATCHED_ORIGINAL_INTENT_RECEIPT"
            lane = "conversation_identity_owner"
        elif old_case_count:
            action = "REFRESH_ORIGINAL_COMMERCIAL_SOURCE_EVIDENCE_FIRST"
            lane = "commercial_source_owners"
        else:
            action = "VERIFY_ORIGINAL_PROVIDER_INBOUND_AND_TENANT_CONTACT_BINDING"
            lane = "conversation_evidence_owner"

        cases.append({
            "operator_case_number": case_number,
            "shadow_offer_row_numbers_ephemeral": list(shadow_rows),
            "original_recovery_row_numbers": list(original_rows),
            "casebook_state": state,
            "existing_owner_review_lane": lane,
            "review_action_not_dispatched": action,
            "original_inbound_proof_linked_to_this_case": False,
            "provider_message_authentication_verified_for_this_case": False,
            "canonical_tenant_contact_bound_to_this_case": False,
            "latest_inbox_opt_out_suppression_checked_for_this_case": False,
            "commercial_buyer_intent_verified_for_this_case": False,
            "live_followup_permission": False,
            "agent_job_created": False,
        })
    if seen != set(range(1, len(case_rows) + 1)):
        raise ValueError("noncontiguous operator case numbers")

    cases.sort(key=lambda r: r["operator_case_number"])
    counts = dict(sorted(Counter(r["review_action_not_dispatched"] for r in cases).items()))
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "ORIGINAL_AUTHENTICATED_REPLY_EVIDENCE_HOLD",
        "review_generated_at": now.isoformat(),
        "existing_conversation_os_evidence_status": "HOLD_REAL_REPLY_EVIDENCE_REQUIRED",
        "original_provider_health_is_aggregate_not_per_case": True,
        "original_inbound_provider_events_independently_authenticated": False,
        "source_blockers_allowlisted": source_blockers,
        "original_evidence_proof_summary": {
            "total_control_count": control_count,
            "verified_control_count": verified_controls,
            "canonical_message_count": canonical_messages,
            "observed_inbound_reply_candidates": observed_candidates,
            "authenticated_inbound_reply_count_verified": auth_count,
            "verified_reply_join_count": linked_replies,
            "founder_mailbox_observer_status": (
                conversation_proof.get("founder_mailbox_observer_status")
                if conversation_proof.get("founder_mailbox_observer_status") in {
                    "NO_COMPLETE_INBOUND_MESSAGE", "OBSERVER_ERROR",
                    "VERIFIED_RUNTIME", "NOT_VERIFIED",
                } else "NOT_VERIFIED"
            ),
        },
        "casebook_source_refresh_required": old_case_count,
        "case_count": len(cases),
        "review_actions_not_dispatched": counts,
        "sales_director_case_reviews": cases,
        "case_count_does_not_imply_real_inbound_replies_or_buyers": True,
        "original_inbox_accessed": False,
        "provider_api_called": False,
        "crm_mutations": False,
        "outbound_sent": False,
        "outbound_authorized": False,
        "payment_execution": False,
        "database_writes": False,
        "agent_tasks_created": False,
        "execution_authority": "none",
    }
