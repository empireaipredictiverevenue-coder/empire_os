"""Commercial-gap triage above the existing canonical Buyer Scout.

Prioritises *what first-party commercial evidence is absent*, not
unsubstantiated conversion probability, revenue, buyer price or demand.
Reuses the private partner pilot's nine existing activation gates.
No contact dispatch, scraping, CRM writes, data promotion, model training,
money movement or changes to the primary Scout service.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from datetime import datetime, timezone

from empire_os.buyer_specification_readiness import (
    REQUIRED_GATES, CRITICAL_FIRST,
)
from empire_os.buyer_scout_commercial_awareness import (
    SCHEMA as AWARENESS_SCHEMA, RELATIONSHIP_SCHEMA,
    _source_timestamp, _domain,
)

ALLOWED_TASKS = frozenset({
    "SUPPRESSION_REVIEW_ONLY", "RESOLVE_IDENTITY_ALIAS_CONFLICT",
    "RESOLVE_SCOUT_AND_FOUNDER_ROLE_CONFLICT",
    "REFRESH_EXISTING_THREAD_BEFORE_ANY_CONTACT",
    "REVIEW_EXISTING_THREAD_NO_DUPLICATE_INTRO",
    "RESOLVE_FOUNDING_COMMERCIAL_HOLD",
    "VERIFY_INTERMEDIARY_OWN_SPEND_VS_PUBLISHER_RECRUITMENT",
    "VERIFY_FIRST_PARTY_DIRECT_BUYBOX_AND_DEMAND",
    "RECONCILE_CANONICAL_BUSINESS_IDENTITY_WITH_CRM",
    "VERIFY_BUDGET_AND_PURCHASING_AUTHORITY",
    "VERIFY_BUYBOX_PRICE_TERMS_AND_PAYMENT_PATH",
    "REVIEW_BUYER_CAPACITY_AND_PILOT_RISK_WITH_OWNER",
    "COOLDOWN_RESEARCH_REUSE_EXISTING_FIRST_PARTY_EVIDENCE",
})
ALLOWED_ROLES = frozenset({
    "SUPPRESSED", "UNKNOWN", "EXISTING_RELATIONSHIP", "RESEARCH_ONLY",
    "INTERMEDIARY_OR_PUBLISHER", "UNVERIFIED_BUYER_ROLE",
    "DIRECT_BUYER_CLAIM_UNVERIFIED_IDENTITY",
    "DIRECT_BUYER_EVIDENCE_INCOMPLETE", "EVIDENCE_REVIEW_ONLY",
})

SCHEMA = "empire.buyer_scout_economic_gap_review.v1"
MAX_PILOTS = 12
MAX_RESEARCH = 150

def _review_pilots(registry: Mapping) -> list[dict]:
    pilots = registry.get("partner_pilot_readiness_queue")
    if not isinstance(pilots, list) or len(pilots) > MAX_PILOTS:
        raise ValueError("pilot_queue_missing_or_unbounded")
    seen = set()
    result = []
    for index, pilot in enumerate(pilots):
        if not isinstance(pilot, Mapping):
            raise ValueError("invalid_pilot_row")
        key = pilot.get("entity_key")
        if not isinstance(key, str) or not 1 <= len(key) <= 80 or key in seen:
            raise ValueError("pilot_identity_missing_or_duplicate")
        seen.add(key)
        gates = pilot.get("activation_gates")
        if (not isinstance(gates, Mapping) or set(gates) != REQUIRED_GATES
                or any(type(gates[g]) is not bool for g in REQUIRED_GATES)
                or pilot.get("gate_count_total") != len(REQUIRED_GATES)
                or pilot.get("gate_count_verified") != sum(gates.values())
                or pilot.get("outbound_authorized") is not False
                or pilot.get("live_traffic_authorized") is not False
                or pilot.get("lead_smart_route_and_terms_reused") is not False
                or pilot.get("tracking_or_route_mutation_performed") is not False):
            raise ValueError("invalid_partner_commercial_gates")
        if pilot.get("inbound_requirement_review_status") not in (
            "REPORTED_AWAITING_INDEPENDENT_VERIFICATION",
            "HISTORICAL_REPORTED_REQUIREMENTS_HOLD",
            "NO_NEW_VERIFIED_GMAIL_OBSERVATION",
        ):
            raise ValueError("unsupported_inbound_evidence_status")
        missing = [gate for gate in CRITICAL_FIRST if gates[gate] is not True]
        if not missing:
            task = "OWNER_REVIEW_COMPLETED_BUYER_EVIDENCE_NO_AUTO_ACTIVATION"
        elif pilot.get("activation_stage") == "DEFERRED_PENDING_ESTABLISHED_TRAFFIC":
            task = "VERIFY_IF_BUYER_WANTS_FUNDED_PILOT_WITH_NEW_TRAFFIC_CONSTRAINT"
        elif pilot.get("inbound_requirement_review_status") == "HISTORICAL_REPORTED_REQUIREMENTS_HOLD":
            task = "RECONCILE_HISTORICAL_BUYER_REQUIREMENTS_BEFORE_ASKING_TERMS"
        else:
            task = "ASK_EXISTING_CONVERSATION_OWNER_FOR_VERIFIED_BUYBOX_AND_PRICE_TERMS"
        # This read-only lane never sends an email. Even a two-way thread
        # and price statement may not prove demand or a funded buyer.
        result.append({
            "pilot_queue_index": index,
            "observed_two_way_conversation": pilot.get("two_way_gmail_thread_observed") is True,
            "pilot_mailbox_reported_fresh": pilot.get("mailbox_snapshot_fresh") is True,
            "economic_evidence_gates_verified": sum(gates.values()),
            "economic_evidence_gates_total": len(REQUIRED_GATES),
            "missing_economic_and_activation_evidence": missing,
            "first_missing_gate": missing[0] if missing else None,
            "commercial_next_research_task": task,
            "partner_status": "EXISTING_DISCUSSION_UNVERIFIED_BUYER"
                if pilot.get("two_way_gmail_thread_observed") is True else
                "UNVERIFIED_PARTNER_PILOT",
            "buyer_daily_capacity_verified": False,
            "buyer_first_party_budget_verified": False,
            "buyer_per_lead_or_call_price_verified": False,
            "buyer_payable_terms_gate_verified": gates["buyer_payable_event_and_terms_verified"],
            "buyer_payable_event_verified": gates["buyer_payable_event_and_terms_verified"],
            "money_available_for_pilot_verified": False,
            "activation_authorized": False,
        })
    return result


def build_buyer_economic_gap_review(
    awareness: Mapping, registry: Mapping, *, as_of: datetime,
) -> dict:
    if as_of.tzinfo is None or as_of.utcoffset() is None:
        raise ValueError("timezone_aware_review_required")
    now = as_of.astimezone(timezone.utc)
    _source_timestamp(registry, RELATIONSHIP_SCHEMA, now, registry=True)
    if (not isinstance(awareness, Mapping)
            or awareness.get("schema_version") != AWARENESS_SCHEMA
            or awareness.get("mode") != "OBSERVE"
            or awareness.get("execution_authority") != "none"
            or awareness.get("outbound_authorized") is not False
            or awareness.get("canonical_crm_writes") is not False
            or awareness.get("buyer_activation_authorized") is not False):
        raise ValueError("untrusted_awareness_review")
    snapshots = awareness.get("snapshots")
    if (not isinstance(snapshots, Mapping) or
            snapshots.get("relationship_registry") !=
            datetime.fromisoformat(registry["generated_at"].replace("Z", "+00:00")).astimezone(timezone.utc).isoformat()):
        raise ValueError("relationship_source_version_mismatch")
    domains = awareness.get("review_queue")
    if (not isinstance(domains, list) or len(domains) > MAX_RESEARCH
            or any(not isinstance(x, Mapping) for x in domains)):
        raise ValueError("invalid_economic_research_queue")
    pilots = _review_pilots(registry)
    # Reuse *already vetted* buyer research priorities, not fresh fuzzy
    # organisation matching or made-up payer economic quantities.
    tasks = []
    seen = set()
    for row in domains:
        domain = row.get("domain")
        if not isinstance(domain, str) or not _domain(domain) or domain != _domain(domain) or domain in seen:
            raise ValueError("duplicate_or_invalid_commercial_domain")
        seen.add(domain)
        task = row.get("next_evidence_task")
        if task not in ALLOWED_TASKS or row.get("buyer_role_for_review") not in ALLOWED_ROLES:
            raise ValueError("unsupported_awareness_task_or_role")
        priority = row.get("research_priority_not_conversion_probability")
        if type(priority) is not int or not 0 <= priority <= 100:
            raise ValueError("invalid_research_priority")
        tasks.append({
            "domain": domain, "commercial_role_review": row["buyer_role_for_review"],
            "research_task": task,
            "priority_not_conversion_probability": row["research_priority_not_conversion_probability"],
            "previously_engaged": row["prior_contact_or_thread_evidence"] is True,
            "suppression_hold": row["suppression_or_bounce_hold"] is True,
            "buyer_capacity_verified": False,
            "first_payer_verified": False,
            "automatic_outbound_authorized": False,
        })
    pilot_gates = Counter(g for p in pilots for g in p["missing_economic_and_activation_evidence"])
    # Actionable, human-facing priority: existing buyer conversations can
    # be advanced by obtaining explicit buybox and pricing; unknown direct
    # buyer claims require separate first-party proof; held domains never
    # auto-join the customer acquisition queue.
    portfolio_tasks = Counter(t["research_task"] for t in tasks)
    return {
        "schema_version": SCHEMA,
        "mode": "READ_ONLY_COMMERCIAL_RESEARCH",
        "as_of": now.isoformat(),
        "partner_pilots_reviewed": len(pilots),
        "global_gmail_snapshot_fresh": registry.get("gmail_snapshot_fresh") is True,
        "manual_follower_review_required_before_any_partner_message": True,
        "partner_pilots_with_two_way_history": sum(p["observed_two_way_conversation"] for p in pilots),
        "partner_pilots_without_verified_buybox": pilot_gates["buyer_buybox_received_and_verified"],
        "partner_pilots_without_verified_payable_terms": pilot_gates["buyer_payable_event_and_terms_verified"],
        "partner_pilots_without_verified_geography": pilot_gates["current_target_geography_verified"],
        "partner_pilots_without_founder_traffic_authorization": pilot_gates["founder_live_traffic_authorized"],
        "verified_paying_buyer_capacity": 0,
        "active_confirmed_paying_pilots": 0,
        "next_pilot_evidence_queue": pilots,
        "scout_domains_triaged": len(tasks),
        "scout_next_commercial_research_queue": sorted(
            tasks, key=lambda x: (-x["priority_not_conversion_probability"], x["domain"])),
        "scout_economic_research_task_counts": dict(sorted(portfolio_tasks.items())),
        "source_snapshots_joined_by_reference_only": True,
        "no_unverified_partner_company_merge": True,
        "business_name_is_not_buyer_identity": True,
        "published_program_terms_not_buyer_acceptance": True,
        "web_traffic_not_buyer_capacity": True,
        "forecasted_revenue_not_recognized_revenue": True,
        "model_training_authorized": False,
        "outbound_authorized": False,
        "buyer_activation_authorized": False,
        "canonical_empiredb_writes": False,
        "execution_authority": "none",
    }
