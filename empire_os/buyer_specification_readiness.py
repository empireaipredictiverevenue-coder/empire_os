"""Buyer specification readiness: existing partner pilot gates vs Exchange.

PRIVATE and read-only. All buyer commercial proof must already be verified by
the current partner/CRM owner. First-party proposed corridors are NOT buyboxes,
signed terms, verified capacity or authorised live traffic. Never infer those
from source lists, keyword overlaps, or an old Gmail conversation.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from empire_os.lead_exchange_live_inventory import build_lead_exchange_live_inventory

SCHEMA = "empire.leadgen_buyer_specification_readiness.v1"
REGISTRY = "empire.commercial_relationship_registry.v1"
REQUIRED_GATES = frozenset({
    "buyer_buybox_received_and_verified",
    "current_target_geography_verified",
    "buyer_source_approved",
    "buyer_landing_approved",
    "partner_specific_tracking_verified",
    "partner_specific_routing_verified",
    "buyer_payable_event_and_terms_verified",
    "contract_and_compliance_approved",
    "founder_live_traffic_authorized",
})
CRITICAL_FIRST = (
    "buyer_buybox_received_and_verified",
    "current_target_geography_verified",
    "buyer_payable_event_and_terms_verified",
    "buyer_source_approved",
    "partner_specific_routing_verified",
    "partner_specific_tracking_verified",
    "contract_and_compliance_approved",
    "buyer_landing_approved",
    "founder_live_traffic_authorized",
)


def _hold(reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA, "state": "HOLD",
        "reason": reason, "mode": "READ_ONLY_PRIVATE",
        "verified_buyer_specifications": 0,
        "verified_buyer_capacity": 0, "allocatable_inventory": 0,
        "commercial_activation_authorized": False,
        "live_traffic_authorized": False, "outbound_authorized": False,
        "canonical_empiredb_writes": False, "execution_authority": "none",
    }


def build_buyer_specification_readiness(
    *, relationships: Mapping[str, Any], exchange: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("now_must_include_timezone")
    stock = build_lead_exchange_live_inventory(exchange, now=current)
    if stock["state"] != "FRESH_CANONICAL_SNAPSHOT":
        return _hold("canonical_exchange_not_fresh")
    if (not isinstance(relationships, Mapping)
            or relationships.get("schema_version") != REGISTRY
            or str(relationships.get("execution_authority")).upper() != "NONE"
            or relationships.get("outbound_authorized") is not False
            or relationships.get("outbound_sent") is not False):
        return _hold("untrusted_partner_relationship_registry")
    pilots = relationships.get("partner_pilot_readiness_queue")
    if not isinstance(pilots, list) or len(pilots) > 12:
        return _hold("partner_pilot_population_unbounded")
    reqs = relationships.get("partner_inbound_requirements")
    if (not isinstance(reqs, Mapping)
            or reqs.get("schema_version") != "empire.partner_inbound_requirements_review.v1"
            or reqs.get("commercial_activation_authorized") is not False
            or reqs.get("outbound_authorized") is not False):
        return _hold("partner_inbound_requirements_unverified")

    output = []
    seen = set()
    for item in pilots:
        if not isinstance(item, Mapping):
            return _hold("invalid_partner_pilot")
        key = item.get("entity_key")
        if not isinstance(key, str) or not 1 <= len(key) <= 80 or key in seen:
            return _hold("duplicate_or_invalid_partner")
        seen.add(key)
        gates = item.get("activation_gates")
        if (not isinstance(gates, Mapping) or set(gates) != REQUIRED_GATES
                or any(type(gates[g]) is not bool for g in REQUIRED_GATES)):
            return _hold("invalid_partner_gate_contract")
        n_verified = sum(gates.values())
        if (item.get("gate_count_total") != len(REQUIRED_GATES)
                or item.get("gate_count_verified") != n_verified
                or item.get("live_traffic_authorized") is not False
                or item.get("outbound_authorized") is not False
                or item.get("lead_smart_route_and_terms_reused") is not False
                or item.get("tracking_or_route_mutation_performed") is not False):
            return _hold("partner_gate_or_authority_conflict")
        inbox = item.get("inbound_requirement_review_status")
        if inbox not in (
            "REPORTED_AWAITING_INDEPENDENT_VERIFICATION",
            "HISTORICAL_REPORTED_REQUIREMENTS_HOLD",
            "NO_NEW_VERIFIED_GMAIL_OBSERVATION",
        ):
            return _hold("unknown_inbound_review_status")
        missing = [key for key in CRITICAL_FIRST if not gates[key]]
        # Selected inventory is counted independently of partner proposals;
        # do not do a bogus location/capacity match against string tags.
        output.append({
            "entity_key": key,
            "company": str(item.get("company") or "")[:100],
            "relationship_stage": str(item.get("relationship_stage") or "")[:80],
            "activation_stage": str(item.get("activation_stage") or "")[:80],
            "buyer_requirement_state": inbox,
            "reported_fields_unverified": item.get("inbound_requirement_field_count", 0),
            "two_way_thread_observed_not_contract": item.get("two_way_gmail_thread_observed") is True,
            "mailbox_snapshot_fresh": item.get("mailbox_snapshot_fresh") is True,
            "proposed_corridor_not_approved": str(
                item.get("proposed_corridor_not_buyer_approved") or ""
            )[:130],
            "gate_verified_count": n_verified,
            "gate_total": len(REQUIRED_GATES),
            "missing_evidence": missing,
            "next_verification": missing[0] if missing else "INDEPENDENT_BUYER_ACTIVATION_REVIEW",
            "buyer_buybox_verified": gates["buyer_buybox_received_and_verified"],
            "commercial_terms_verified": gates["buyer_payable_event_and_terms_verified"],
            "route_verified": gates["partner_specific_routing_verified"],
            "source_approval_verified": gates["buyer_source_approved"],
            "delivery_ready_match": False,
            "first_payer_capacity_authorized": False,
            "outbound_authorized": False,
        })
    output.sort(key=lambda p: (
        -int(p["two_way_thread_observed_not_contract"]),
        -int(p["gate_verified_count"]),
        p["entity_key"],
    ))
    return {
        "schema_version": SCHEMA,
        "state": "FOUNDER_PARTNER_GAP_BOARD_READY",
        "mode": "READ_ONLY_PRIVATE",
        "observed_at": current.isoformat(),
        "registry_generated_at": relationships.get("generated_at"),
        "registry_mailbox_snapshot_fresh": relationships.get("gmail_snapshot_fresh") is True,
        "partner_pilots_reviewed": len(output),
        "current_inbound_requirements_needing_verification": reqs.get("current_review_count"),
        "historical_requirements_held": reqs.get("historical_hold_count"),
        "verified_buyer_specifications": sum(p["buyer_buybox_verified"] for p in output),
        "verified_buyer_capacity": 0,
        "canonical_exchange_selected_records": stock["selected_inventory_records"],
        "canonical_exchange_evidence_holds": stock["evidence_hold_records"],
        "canonical_exchange_capacity_waitlist": stock["buyer_capacity_waitlist_records"],
        "allocatable_inventory": 0,
        "matching_scope": "NO_BUYER_SPEC_GEO_CAPACITY_MATCH",
        "partner_readiness": output,
        "commercial_activation_authorized": False,
        "live_traffic_authorized": False,
        "outbound_authorized": False,
        "canonical_empiredb_writes": False,
        "execution_authority": "none",
    }
