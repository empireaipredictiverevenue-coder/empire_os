"""Privacy-minimal commercial conversation casebook for the EXISTING Sales Director.

Links the canonical offer-book's ORIGINAL conversation_refs to original
conversation-recovery root_intent_id by exact byte-for-byte ID only.

Operator location uses one-based row positions in the already-owned artifacts,
not contact data, fuzzy identities, hashes posing as identities or new CRM jobs.
No messages are sent, and recoverable NEVER means permitted to follow up.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

SCHEMA = "empire.commercial.conversation_conversion_casebook.v1"
OFFER_SCHEMA = "empire.predictive-revenue.commercial-offer-book.v2"
RECOVERY_SCHEMA = "empire.conversation_recovery.v1"
SHADOW_HEALTH_SCHEMA = "empire.commercial_growth.shadow_offer_reconstruction.v1"
MAX_RECORDS = 5000
MAX_AGE_HOURS = 72
REASONS = frozenset({"due_now", "missing_canonical_context", "suppressed_after_delivery"})


def _timestamp(value: Any, *, now: datetime) -> str:
    if not isinstance(value, str) or not value or len(value) > 90:
        return "UNKNOWN"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.utcoffset() is None:
            return "INVALID"
        age = (now - dt.astimezone(timezone.utc)).total_seconds() / 3600
    except (ValueError, OverflowError):
        return "INVALID"
    return "FUTURE" if age < -0.1 else "STALE" if age > MAX_AGE_HOURS else "FRESH"


def _identifier(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    clean = raw.strip()
    if not clean or len(clean) > 256:
        return None
    return clean


def review_conversion_casebook(
    *,
    offer_book: Mapping[str, Any],
    conversation_recovery: Mapping[str, Any],
    source_health: Mapping[str, Any],
    now: datetime,
) -> dict[str, Any]:
    if not isinstance(now, datetime) or now.utcoffset() is None:
        raise ValueError("trusted timezone-aware review clock required")
    now = now.astimezone(timezone.utc)
    if offer_book.get("schema_version") != OFFER_SCHEMA or offer_book.get("execution_authority") != "none":
        raise ValueError("non-executing canonical offer book required")
    if (
        conversation_recovery.get("schema_version") != RECOVERY_SCHEMA
        or conversation_recovery.get("execution_authority") != "none"
        or conversation_recovery.get("send_executed") is not False
    ):
        raise ValueError("non-executing canonical recovery report required")
    if (
        source_health.get("schema_version") != SHADOW_HEALTH_SCHEMA
        or source_health.get("mode") != "OBSERVE"
        or source_health.get("recomputed_using_existing_owner_logic") is not True
        or source_health.get("execution_authority") != "none"
        or type(source_health.get("source_refresh_review_required")) is not bool
    ):
        raise ValueError("canonical shadow provenance review required")
    offers = offer_book.get("targets")
    recovered = conversation_recovery.get("items")
    if (
        not isinstance(offers, list) or len(offers) > MAX_RECORDS
        or not isinstance(recovered, list) or len(recovered) > MAX_RECORDS
        or any(not isinstance(r, Mapping) for r in offers + recovered)
    ):
        raise ValueError("bounded offer and recovery record arrays required")
    clocks = {
        "original_conversation_recovery": _timestamp(
            conversation_recovery.get("observed_at"), now=now
        ),
        "shadow_calculation_not_proof": _timestamp(
            source_health.get("calculated_at"), now=now
        ),
    }
    upstream_stale = source_health["source_refresh_review_required"]
    source_hold = (
        upstream_stale
        or clocks["original_conversation_recovery"] != "FRESH"
        or clocks["shadow_calculation_not_proof"] != "FRESH"
    )

    # Presence in more than one review target is ambiguous, even if original
    # recovery has a single matching delivery. Do NOT silently select one.
    refs_to_offer_rows: dict[str, set[int]] = defaultdict(set)
    duplicate_refs_within_offer = 0
    invalid_offer_refs = 0
    offers_with_refs = set()
    for idx, row in enumerate(offers, start=1):
        raw_refs = row.get("conversation_refs") or []
        if not isinstance(raw_refs, (list, tuple)) or len(raw_refs) > 50:
            raise ValueError("bounded conversation_refs required")
        seen_local = set()
        for raw in raw_refs:
            ref = _identifier(raw)
            if ref is None:
                invalid_offer_refs += 1
                continue
            if ref in seen_local:
                duplicate_refs_within_offer += 1
                continue
            seen_local.add(ref)
            refs_to_offer_rows[ref].add(idx)
        if seen_local:
            offers_with_refs.add(idx)

    recovery_by_ref: dict[str, list[tuple[int, Mapping[str, Any]]]] = defaultdict(list)
    malformed_recovery_ids = 0
    for idx, row in enumerate(recovered, start=1):
        rid = _identifier(row.get("root_intent_id"))
        if rid is None:
            malformed_recovery_ids += 1
            continue
        recovery_by_ref[rid].append((idx, row))

    cases = []
    for ref, offer_rows in refs_to_offer_rows.items():
        matches = recovery_by_ref.get(ref, [])
        reason = "REVIEW_ORIGINAL_THREAD_AND_PROVIDER_INBOX"
        result_state = "HISTORICAL_CONTEXT_READY_FOR_HUMAN_REVIEW"
        if not matches:
            result_state = "MISSING_EXACT_RECOVERY_RECEIPT"
            reason = "RECONCILE_OWNER_SOURCE_BEFORE_SALES_REVIEW"
        elif len(matches) > 1 or len(offer_rows) > 1:
            result_state = "AMBIGUOUS_EXACT_THREAD_IDENTITY"
            reason = "RESOLVE_DUPLICATE_OWNER_SOURCE_LINKS"
        elif (
            matches[0][1].get("recoverable") is not True
            or matches[0][1].get("recovery_reason") == "suppressed_after_delivery"
            or matches[0][1].get("suppressed") is True
        ):
            result_state = "SUPPRESSION_OR_CONTEXT_HOLD"
            reason = "REVIEW_MISSING_CONTEXT_OR_SUPPRESSION_WITH_OWNER"
        elif source_hold:
            result_state = "FRESH_PROVENANCE_REQUIRED"
            reason = "RECHECK_SOURCE_AND_LIVE_PROVIDER_INBOX_BEFORE_NEXT_STEP"

        owner_rows = [offers[n - 1] for n in sorted(offer_rows)]
        codes = sorted({
            code for row in owner_rows for code in (row.get("source_product_codes") or [])
            if isinstance(code, str) and 0 < len(code) <= 100
        })[:15]
        cases.append({
            "offer_book_target_row_numbers": sorted(offer_rows),
            "recovery_source_row_numbers": [pos for pos, _ in matches],
            "owner_lane": "sales_director_operator",
            "state": result_state,
            "manual_review_action": reason,
            "product_codes_research_only": codes,
            "prospect_canonical_id_missing_in_any_offer": any(
                not _identifier(row.get("canonical_prospect_id")) for row in owner_rows
            ),
            "buyer_demand_verified": False,  # source claims not re-authenticated
            "inbound_reply_verified": False,
            "current_opt_out_and_suppression_checked": False,
            "original_provider_inbox_checked": False,
            "customer_contact_binding_verified": False,
            "live_outbound_authorized": False,
            "agent_task_created": False,
        })

    order = {
        "SUPPRESSION_OR_CONTEXT_HOLD": 0,
        "AMBIGUOUS_EXACT_THREAD_IDENTITY": 1,
        "MISSING_EXACT_RECOVERY_RECEIPT": 2,
        "FRESH_PROVENANCE_REQUIRED": 3,
        "HISTORICAL_CONTEXT_READY_FOR_HUMAN_REVIEW": 4,
    }
    cases.sort(key=lambda x: (
        order[x["state"]],
        x["recovery_source_row_numbers"][0] if x["recovery_source_row_numbers"] else 999999,
        x["offer_book_target_row_numbers"],
    ))
    for i, row in enumerate(cases, start=1):
        row["operator_case_number"] = i
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "SOURCE_REVIEW_HOLD" if source_hold else "SALES_OPERATOR_MANUAL_REVIEW_ONLY",
        "review_generated_at": now.isoformat(),
        "offer_book_source_row_path": None,
        "offer_book_is_shadow_in_memory": True,
        "shadow_offer_target_row_numbers_are_valid_only_for_this_calculation": True,
        "recovery_source_row_path": "runtime/conversation_recovery/latest.json",
        "case_row_numbers_are_one_based": True,
        "upstream_clock_states": clocks,
        "source_evidence_refresh_required": source_hold,
        "offer_target_count": len(offers),
        "offer_targets_with_original_conversation_refs": len(offers_with_refs),
        "distinct_offer_thread_refs": len(refs_to_offer_rows),
        "exact_recovery_matches": sum(bool(recovery_by_ref.get(ref)) for ref in refs_to_offer_rows),
        "unmatched_offer_thread_refs": sum(not recovery_by_ref.get(ref) for ref in refs_to_offer_rows),
        "recovery_records_seen": len(recovered),
        "unlinked_recovery_thread_records": sum(
            len(rows) for ref, rows in recovery_by_ref.items() if ref not in refs_to_offer_rows
        ),
        "duplicate_refs_within_offer": duplicate_refs_within_offer,
        "invalid_offer_refs": invalid_offer_refs,
        "invalid_recovery_ids": malformed_recovery_ids,
        "state_counts": dict(sorted(Counter(c["state"] for c in cases).items())),
        "manual_operator_cases": cases,
        "counts_are_not_unique_verified_customers_or_replies": True,
        "outbound_sent": False,
        "outbound_authorized": False,
        "crm_mutations": False,
        "buyer_activation": False,
        "database_writes": False,
        "payment_execution": False,
        "agent_tasks_created": False,
        "execution_authority": "none",
    }
