"""Commercial adaptive intelligence: source lineage, dependencies and safe priorities.

Pure diagnostic composition over EXISTING source owners' outputs. It may suggest
work only to existing owner lanes; it never schedules, dispatches, trains models,
contacts a buyer, updates records, or asserts real revenue from research.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from hashlib import sha256
import json
from typing import Any

SCHEMA = "empire.commercial.adaptive_intelligence_control.v1"
SALES_SCHEMA = "empire.commercial.sales_director_adaptive_recheck.v1"
OFFER_SCHEMA = "empire.commercial_growth.shadow_offer_reconstruction.v1"
DIST_SCHEMA = "empire.commercial.shadow_distribution_refresh_review.v1"
MAX_COUNT = 1_000_000

# Hard prerequisites express the causal dependency chain. A node must never
# be presented as a commercial activation grant, even if its reviews resolve.
POLICY = (
    ("CONTACT_SUPPRESSION", "sales_director_operator", "Confirm original contact suppression and context before reconsidering any thread", (), "compliance", 0),
    ("ORIGINAL_REPLY_AUTHENTICATION", "conversation_evidence_owner", "Verify original provider event, parent message, tenant and contact binding only for non-suppressed review cases", (), "evidence", 1),
    ("COMMERCIAL_SOURCE_PROVENANCE", "commercial_source_owners", "Refresh original aged commercial sources with real receipts, not overwritten dates", (), "evidence", 2),
    ("BUYER_CAPACITY_AND_TERMS", "commercial_evidence_verifier", "Verify directly purchasing buyer, accepted price, territory, capacity and delivery rights", (), "commercial", 3),
    ("CONTACT_AND_PROSPECT_IDENTITY", "decision_maker_resolver", "Reconcile exact first-party canonical prospect identity; never fuzzy-join", ("COMMERCIAL_SOURCE_PROVENANCE",), "identity", 4),
    ("CATALOG_DELIVERABILITY", "commercial_catalog_owner", "Review active product terms, scope and deliverability with original catalog owner", (), "product", 5),
    ("SEARCH_SOURCE_FRESHNESS", "agent_web_search_owner", "Refresh dated original Agent Web search retrieval receipts", (), "research", 6),
    ("COMPETITOR_SOURCE_FRESHNESS", "competitor_search_intelligence_owner", "Refresh dated original competitor intelligence evidence", (), "research", 7),
)
POLICY_LOOKUP = {name: (owner, message, prereqs, group, priority)
                 for name, owner, message, prereqs, group, priority in POLICY}
# A known proof requirement is not itself proof. Existing owners must attest.
REQUIRED_PROOF = {
    "CONTACT_SUPPRESSION": (
        "ORIGINAL_CONTACT_SCOPE", "CURRENT_OPTOUT_AND_SUPPRESSION_CHECK",
    ),
    "ORIGINAL_REPLY_AUTHENTICATION": (
        "ORIGINAL_PROVIDER_INBOUND_RECEIPT", "EXACT_ORIGINAL_MESSAGE_CHAIN",
        "TENANT_AND_CONTACT_AUTHORITY", "CURRENT_REPLY_CONTEXT",
    ),
    "COMMERCIAL_SOURCE_PROVENANCE": (
        "ORIGINAL_PRODUCER_GENERATED_AT", "FIRST_PARTY_SOURCE_RECEIPT",
    ),
    "BUYER_CAPACITY_AND_TERMS": (
        "AUTHENTICATED_REAL_COUNTERPARTY", "DIRECT_BUY_BOX_AND_TERRITORIES",
        "ACCEPTED_BUYER_CAPACITY_TERMS", "DELIVERABILITY_VERIFIED",
    ),
    "CONTACT_AND_PROSPECT_IDENTITY": (
        "FIRST_PARTY_EXACT_CANONICAL_PROSPECT_ID",
    ),
    "CATALOG_DELIVERABILITY": (
        "ACTIVE_PRODUCT_VERSION", "BINDING_PRODUCT_TERMS",
        "FULFILMENT_AND_SOURCE_RIGHTS",
    ),
    "SEARCH_SOURCE_FRESHNESS": ("CURRENT_ORIGINAL_AGENT_WEB_RETRIEVAL_RECEIPT",),
    "COMPETITOR_SOURCE_FRESHNESS": ("CURRENT_ORIGINAL_COMPETITOR_EVIDENCE_RECEIPT",),
}
ALLOWED_SOURCE_STATES = frozenset({
    "available", "stale", "unknown_freshness", "missing_or_invalid",
    "future_dated", "producer_unavailable",
})
MAX_TARGETS = 5000


def _count(value: Any) -> int | None:
    return value if type(value) is int and 0 <= value <= MAX_COUNT else None


def _clock(value: Any) -> datetime:
    if not isinstance(value, datetime) or value.utcoffset() is None:
        raise ValueError("timezone-aware decision clock required")
    return value.astimezone(timezone.utc)


def _digest(obj: Any) -> str:
    return sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"),
                             allow_nan=False, ensure_ascii=True).encode()).hexdigest()


def _contract(packet: Mapping, *, schema: str, required_false: tuple[str, ...]) -> None:
    if not isinstance(packet, Mapping) or packet.get("schema_version") != schema:
        raise ValueError("exact original-owner review schema required")
    if packet.get("mode") != "OBSERVE" or packet.get("execution_authority") != "none":
        raise ValueError("owner review must be observe-only with no authority")
    for key in required_false:
        if packet.get(key) is not False:
            raise ValueError("owner review must deny action: " + key)


def _previous(value: Mapping[str, Any] | None):
    if value is None:
        return None
    _contract(value, schema=SCHEMA,
              required_false=("outbound_authorized", "agent_tasks_created",
                              "database_writes", "payment_execution"))
    summary = value.get("decision_signature_data")
    if not isinstance(summary, Mapping) or value.get("decision_signature") != _digest(summary):
        raise ValueError("previous decision evidence checksum mismatch")
    if value.get("model_training") is not False or value.get("owner_authority_changed") is not False:
        raise ValueError("previous decision claimed unsupported autonomy")
    memory = value.get("gate_memory")
    if not isinstance(memory, list) or len(memory) != len(POLICY):
        raise ValueError("previous operational gate memory incomplete")
    by_key = {r.get("gate"): r for r in memory if isinstance(r, Mapping)}
    if set(by_key) != set(POLICY_LOOKUP):
        raise ValueError("previous operational gate memory has unknown keys")
    last_active = set(summary.get("gates", []))
    if not last_active.issubset(POLICY_LOOKUP):
        raise ValueError("previous unknown causal dependency node")
    for key, row in by_key.items():
        if (
            row.get("active") is not (key in last_active)
            or type(row.get("ever_active")) is not bool
            or not all(type(row.get(k)) is int and 0 <= row[k] <= 100_000
                       for k in ("consecutive_active_reviews",
                                 "lifetime_active_reviews", "resolutions",
                                 "recurrences"))
        ):
            raise ValueError("previous operational memory contradicts proof history")
        if row["consecutive_active_reviews"] > row["lifetime_active_reviews"]:
            raise ValueError("previous operational memory counters inconsistent")
    return summary


def review_adaptive_commercial_intelligence(
    *,
    sales: Mapping[str, Any],
    offers: Mapping[str, Any],
    distribution: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
    now: datetime,
) -> dict[str, Any]:
    """Compose evidence from different cohorts without joining their identities."""
    at = _clock(now)
    _contract(sales, schema=SALES_SCHEMA,
              required_false=("outbound_authorized", "agent_tasks_created",
                              "database_writes", "case_local_provider_authentication_attested"))
    _contract(offers, schema=OFFER_SCHEMA,
              required_false=("outbound_authorized", "agent_tasks_created",
                              "database_writes", "payment_execution"))
    _contract(distribution, schema=DIST_SCHEMA,
              required_false=("live_outbound_authorized", "agent_tasks_created",
                              "snapshot_writes", "payment_authorized"))

    if (
        sales.get("status") != "ADAPTIVE_REVIEW_HOLD_NO_COMMERCIAL_AUTHORITY"
        or offers.get("status") not in ("SOURCE_FRESHNESS_HOLD", "SHADOW_RECONSTRUCTION_ONLY")
        or distribution.get("status") not in (
            "SOURCE_FRESHNESS_HOLD", "SOURCE_AND_BUYER_EVIDENCE_HOLD",
            "BUYER_EVIDENCE_HOLD", "DISTRIBUTION_SHADOW_REVIEW_ONLY"
        )
        or offers.get("result_is_shadow_not_current_commercial_authority") is not True
        or distribution.get("no_current_revenue_or_buyer_evidence_inferred") is not True
        or type(offers.get("source_refresh_review_required")) is not bool
        or type(distribution.get("source_evidence_review_required")) is not bool
    ):
        raise ValueError("invalid non-commercial shadow truth and freshness contract")

    adaptive_state = sales.get("evidence_semantic_state")
    if not isinstance(adaptive_state, Mapping) or sales.get("evidence_semantic_hash") != _digest(adaptive_state):
        raise ValueError("sales adaptive semantic provenance invalid")
    sales_cases = _count(adaptive_state.get("case_count"))
    if sales_cases is None or sales_cases > MAX_TARGETS:
        raise ValueError("sales historic case count unsupported")
    distribution_states = distribution.get("source_states")
    if not isinstance(distribution_states, Mapping) or set(distribution_states) != {
        "conversion", "catalog", "radar", "buyer_acquisition", "buyer_scout",
        "buyer_capacity", "exchange", "search", "aeo", "competitor", "crawler",
    } or any(status not in ALLOWED_SOURCE_STATES for status in distribution_states.values()):
        raise ValueError("existing distribution 11-source contract drift")
    if distribution.get("source_count") != len(distribution_states):
        raise ValueError("source count inconsistent")
    capacity = distribution.get("buyer_capacity_source_counts_not_buyer_demand_proof")
    old = offers.get("historical_offer_book")
    new = offers.get("in_memory_reconstructed_offer_book")
    if not isinstance(capacity, Mapping) or not isinstance(old, Mapping) or not isinstance(new, Mapping):
        raise ValueError("source cohort summaries missing")
    historical = _count(old.get("target_count"))
    shadow = _count(new.get("target_count"))
    ready = _count(new.get("offer_ready_count"))
    missing_ids = _count(new.get("missing_canonical_prospect_id_count"))
    contacts = _count(new.get("verified_person_and_email_count"))
    verified_demand = _count(new.get("source_claims_verified_buyer_demand_count"))
    catalog_ready = _count(offers.get("reconstructed_ready_catalog_product_count"))
    buyers_seen = _count(capacity.get("buyers_seen"))
    buyer_activated = _count(capacity.get("fully_activated"))
    terms_verified = _count(capacity.get("terms_verified"))
    capacity_verified = _count(capacity.get("capacity_verified"))
    if any(x is None for x in (historical, shadow, ready, missing_ids,
                               contacts, verified_demand, catalog_ready)):
        raise ValueError("bounded original offer-book cohort counts required")
    if ready > shadow or missing_ids > shadow or contacts > shadow or verified_demand > shadow:
        raise ValueError("inconsistent offer book counters")
    if buyer_activated is not None and buyers_seen is not None and buyer_activated > buyers_seen:
        raise ValueError("buyer cohort inconsistent")
    # Do not treat a source claim of activated buyer as first-party purchase proof.
    buyer_purchase_attested = False

    sales_actions = adaptive_state.get("action_counts")
    if not isinstance(sales_actions, Mapping) or any(_count(v) is None for v in sales_actions.values()):
        raise ValueError("original Sales Director blocker counts required")
    suppression_cases = _count(sales_actions.get(
        "REVIEW_SUPPRESSION_AND_MISSING_CANONICAL_CONTEXT_NO_OUTREACH", 0))
    if suppression_cases is None or suppression_cases > sales_cases:
        raise ValueError("sales suppression cases exceed total")

    # Independent cohorts: these counts are NOT combined into a funnel or unique buyers.
    active = {
        "CONTACT_SUPPRESSION": suppression_cases > 0,
        "ORIGINAL_REPLY_AUTHENTICATION": sales_cases > 0,
        "COMMERCIAL_SOURCE_PROVENANCE": offers["source_refresh_review_required"],
        # Aggregate buyer-capacity counts cannot independently authenticate
        # a real purchasing counterparty, signed terms or accepted delivery.
        "BUYER_CAPACITY_AND_TERMS": not buyer_purchase_attested,
        "CONTACT_AND_PROSPECT_IDENTITY": missing_ids > 0,
        "CATALOG_DELIVERABILITY": (ready == 0 or catalog_ready == 0),
        "SEARCH_SOURCE_FRESHNESS": distribution_states["search"] != "available",
        "COMPETITOR_SOURCE_FRESHNESS": distribution_states["competitor"] != "available",
    }
    impact = {
        "CONTACT_SUPPRESSION": {"historical_conversation_case_count": suppression_cases},
        "ORIGINAL_REPLY_AUTHENTICATION": {
            "historical_conversation_case_count": sales_cases,
            "suppression_or_missing_context_subcohort_not_eligible": suppression_cases,
            "remaining_non_suppressed_review_cases_not_authenticated": sales_cases - suppression_cases,
        },
        "COMMERCIAL_SOURCE_PROVENANCE": {"historical_offer_review_target_count": shadow},
        "BUYER_CAPACITY_AND_TERMS": {"buyer_capacity_records_seen_not_activated": buyers_seen},
        "CONTACT_AND_PROSPECT_IDENTITY": {"shadow_offer_rows_missing_id": missing_ids},
        "CATALOG_DELIVERABILITY": {"catalog_ready_product_count_not_sellable_offers": catalog_ready},
        "SEARCH_SOURCE_FRESHNESS": {"existing_owner_source_unavailable": int(active["SEARCH_SOURCE_FRESHNESS"])},
        "COMPETITOR_SOURCE_FRESHNESS": {"existing_owner_source_unavailable": int(active["COMPETITOR_SOURCE_FRESHNESS"])},
    }
    graph = []
    for key, owner, message, prerequisites, group, priority in POLICY:
        if not active[key]:
            continue
        blocking = [p for p in prerequisites if active[p]]
        if key == "ORIGINAL_REPLY_AUTHENTICATION" and suppression_cases == sales_cases:
            blocking.append("CONTACT_SUPPRESSION")
        graph.append({
            "gate": key, "existing_owner_lane": owner,
            "review_instruction_not_dispatched": message,
            "priority_rank": priority,
            "category": group,
            "upstream_gates_blocking_work": blocking,
            "parallel_owner_review_possible": not blocking,
            "review_evidence_impact_not_forecast": impact[key],
            "original_proof_requirements_not_verified": list(REQUIRED_PROOF[key]),
            "source_change_does_not_grant_permission": True,
            "task_created": False,
        })
    signature = {
        "gates": [n["gate"] for n in graph],
        "original_sales_case_counts": dict(sorted(sales_actions.items())),
        "original_reply_semantic": sales["evidence_semantic_hash"],
        "offer_targets_from_reconstructed_source": shadow,
        "offer_ready": ready,
        "catalog_ready": catalog_ready,
        "missing_original_ids": missing_ids,
        "verified_person_and_email_source_claims": contacts,
        "original_source_claims_buyer_demand": verified_demand,
        "capacity_verified_source_claim": capacity_verified,
        "terms_verified_source_claim": terms_verified,
        "buyers_activated_source_claim": buyer_activated,
        "distribution_states": dict(sorted(distribution_states.items())),
        "upstream_offer_source_refresh": offers["source_refresh_review_required"],
    }
    signature_hash = _digest(signature)
    prior = _previous(previous)
    if prior is None:
        transition = "FIRST_COMMERCIAL_INTELLIGENCE_REVIEW"
        changed_gates = [n["gate"] for n in graph]
        regression = []
        resolved = []
    else:
        prior_gates = set(prior.get("gates", []))
        if not prior_gates.issubset(POLICY_LOOKUP):
            raise ValueError("previous unknown causal dependency node")
        current_gates = set(signature["gates"])
        regression = sorted(current_gates - prior_gates)
        resolved = sorted(prior_gates - current_gates)
        changed_gates = sorted(current_gates ^ prior_gates)
        transition = (
            "UNCHANGED_COMMERCIAL_HOLD" if signature_hash == previous["decision_signature"]
            else "PROVENANCE_OR_METRICS_CHANGED_REVIEW_REQUIRED"
        )
    material = transition != "UNCHANGED_COMMERCIAL_HOLD"
    actionable = []
    for node in graph:
        if material and node["parallel_owner_review_possible"]:
            actionable.append(node)

    # Observational "learning": track repeat holds, verified source-state
    # transitions and recurrence. No rewards, training or synthetic economics.
    old_memory = {
        r["gate"]: r for r in previous["gate_memory"]
    } if previous is not None else {}
    memory = []
    persistent = []
    recurring = []
    for key, *_ in POLICY:
        old_row = old_memory.get(key, {})
        is_active = active[key]
        was_active = old_row.get("active") is True
        ever_seen = old_row.get("ever_active") is True
        consecutive = (
            min(100_000, old_row.get("consecutive_active_reviews", 0) + 1)
            if is_active and was_active else 1 if is_active else 0
        )
        resolutions = min(
            100_000, old_row.get("resolutions", 0) +
            int(previous is not None and was_active and not is_active),
        )
        repeats = min(
            100_000, old_row.get("recurrences", 0) +
            int(previous is not None and is_active and not was_active and ever_seen),
        )
        row = {
            "gate": key,
            "active": is_active,
            "ever_active": bool(is_active or ever_seen),
            "consecutive_active_reviews": consecutive,
            "lifetime_active_reviews": min(
                100_000, old_row.get("lifetime_active_reviews", 0) + int(is_active)
            ),
            "resolutions": resolutions,
            "recurrences": repeats,
        }
        memory.append(row)
        if consecutive >= 3:
            persistent.append(key)
        if previous is not None and is_active and not was_active and ever_seen:
            recurring.append(key)

    explanation = (
        "Nothing materially changed; keep existing owner reviews without duplicate alerts."
        if not material else
        "Source evidence or blockers changed; review upstream prerequisites first. "
        "No authenticated buyer, order, revenue or send authority is inferred."
    )
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "status": "COMMERCIAL_DEPENDENCY_EVIDENCE_HOLD",
        "generated_at": at.isoformat(),
        "transition": transition,
        "plain_language_reason": explanation,
        "decision_signature_data": signature,
        "decision_signature": signature_hash,
        "active_dependency_gates": graph,
        "gates_newly_blocking": regression,
        "gates_no_longer_reported": resolved,
        "changed_gate_names": changed_gates,
        "gate_memory": memory,
        "recurrent_evidence_gates": recurring,
        "persistent_holds_three_or_more_observations": persistent,
        "operational_learning_only": True,
        "economic_feedback_training_permitted": False,
        "recommended_parallel_reviews_not_dispatched": actionable,
        "operator_attention_due": material,
        "deduplicated_if_unchanged": not material,
        "existing_agent_owner_review_only": True,
        "no_cross_cohort_buyer_identity_join": True,
        "historical_offer_targets_not_new_customers": historical,
        "shadow_offer_targets_not_new_customers": shadow,
        "historical_conversations_not_verified_replies": sales_cases,
        "buyer_capacity_records_seen_not_purchasers": buyers_seen,
        "independently_authenticated_buyers": None,
        "verified_purchase_or_payment_events": None,
        "accepted_verified_revenue_cents": None,
        "economic_model_update": "BLOCKED_UNTIL_ORIGINAL_SETTLEMENT_AND_FULFILMENT_PROOF",
        "outbound_authorized": False,
        "crm_mutations": False,
        "payment_execution": False,
        "agent_tasks_created": False,
        "database_writes": False,
        "model_training": False,
        "owner_authority_changed": False,
        "execution_authority": "none",
    }
