"""Phase 4 Buyer Acquisition Team control plane.

This is the canonical demand-side orchestration contract for Commercial
Exchange. It coordinates existing buyer discovery/enrichment/review/evidence
components without granting outbound, terms, payment or revenue authority.

The team targets companies that directly buy B2B leads, calls, appointments,
data feeds or white-label demand, plus qualified end-buyers where appropriate.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from empire_os.phase4_exchange_mrr_products import (
    build_exchange_mrr_product_plan,
)
from empire_os.search_intelligence.products import get_search_product
from empire_os.icp_buyer_trigger_intelligence import (
    build_icp_priority_targets,
    icp_learning_contract,
)
from empire_os.predictive_revenue_enterprise_targets import (
    build_enterprise_target_review,
)
from empire_os.niche_taxonomy import niche_family


OUTPUT = Path("runtime/buyer_acquisition/latest.json")


DIRECT_BUYER_SIGNALS = {
    "buy leads": 35,
    "lead buyer": 35,
    "lead buyers": 35,
    "buy calls": 35,
    "call buyer": 35,
    "buy appointments": 35,
    "lead purchasing": 30,
    "purchase leads": 35,
    "third party leads": 25,
    "third-party leads": 25,
    "lead vendors": 25,
    "lead sources": 20,
    "daily budget": 20,
    "daily cap": 20,
    "buying criteria": 25,
    "buy box": 25,
    "pay per lead": 20,
    "pay per call": 20,
    "inbound calls": 15,
    "booked appointments": 15,
    "lead marketplace": 20,
    "lead exchange": 20,
    "customer acquisition": 10,
    "call center": 10,
    "contact center": 10,
    "aggregator": 15,
}

BUYER_SIDE_SIGNALS = {
    "we buy leads": 50,
    "buy leads": 35,
    "purchase leads": 40,
    "lead purchasing": 35,
    "buy calls": 40,
    "buy appointments": 40,
    "lead buyer": 35,
    "lead buyers": 35,
    "third party leads": 25,
    "third-party leads": 25,
    "lead vendors": 25,
    "lead sources": 20,
    "daily budget": 20,
    "daily cap": 20,
    "buy box": 25,
    "buying criteria": 25,
}

SUPPLIER_SIDE_SIGNALS = {
    "lead generation agency": 35,
    "lead generation services": 35,
    "sales lead generation": 25,
    "we generate leads": 35,
    "we deliver leads": 40,
    "we send leads": 40,
    "lead generation platform": 25,
    "generate qualified leads": 30,
    "performance marketing agency": 25,
}

RESELLER_SIGNALS = {
    "agency": 12,
    "marketing agency": 18,
    "growth agency": 18,
    "white label": 25,
    "reseller": 25,
    "broker": 15,
    "network": 10,
}

TARGET_BUYER_TYPES = (
    "direct_lead_buyer",
    "call_buyer",
    "appointment_buyer",
    "lead_aggregator",
    "performance_marketing_firm",
    "affiliate_network",
    "lead_marketplace",
    "white_label_agency",
    "data_or_intent_buyer",
    "qualified_end_buyer",
    "local_smb_buyer",
    "enterprise_data_buyer",
    "saas_buyer",
    "managed_growth_buyer",
    "commercial_diagnostics_buyer",
    "vertical_intelligence_buyer",
)

BUYER_POOLS = (
    {
        "pool": "local_and_smb_buyers",
        "examples": (
            "local contractors", "dentists", "clinics", "accountants",
            "estate agents", "garages", "cleaners", "landscapers",
            "gyms", "salons", "local legal firms", "independent retailers",
            "home services", "professional services",
        ),
        "purchases": (
            "local_leads",
            "exclusive_leads",
            "calls",
            "booked_appointments",
            "seo_and_search_intelligence",
            "commercial_diagnostics",
            "managed_growth",
            "lightweight_saas",
        ),
    },
    {
        "pool": "end_service_buyers",
        "examples": (
            "roofing", "hvac", "plumbing", "solar", "restoration",
            "legal", "insurance", "mortgage", "debt", "medicare",
            "landscaping", "cleaning", "gutter", "general contractor",
        ),
        "purchases": (
            "qualified_leads",
            "exclusive_leads",
            "calls",
            "booked_appointments",
        ),
    },
    {
        "pool": "direct_demand_buyers",
        "examples": (
            "lead buyers", "lead aggregators", "call buyers",
            "performance marketing firms", "affiliate networks",
            "lead marketplaces",
        ),
        "purchases": (
            "leads",
            "calls",
            "appointments",
            "overflow_inventory",
            "data_feeds",
        ),
    },
    {
        "pool": "agency_and_reseller_buyers",
        "examples": (
            "marketing agencies", "lead generation agencies",
            "growth agencies", "white-label resellers",
        ),
        "purchases": (
            "white_label",
            "managed_growth",
            "lead_supply",
            "content_and_campaign_services",
            "api_access",
        ),
    },
    {
        "pool": "enterprise_and_data_buyers",
        "examples": (
            "private equity", "property groups", "logistics",
            "warehouse operators", "financial services",
            "enterprise sales teams",
        ),
        "purchases": (
            "vertical_intelligence",
            "private_feeds",
            "market_intelligence",
            "intent_data",
            "api_access",
            "benchmark_products",
        ),
    },
    {
        "pool": "software_and_advisory_buyers",
        "examples": (
            "sales teams", "marketing teams", "operators",
            "agencies", "multi-location businesses",
        ),
        "purchases": (
            "saas_subscriptions",
            "commercial_diagnostics",
            "revenue_leak_audits",
            "managed_growth",
            "predictive_intelligence",
        ),
    },
)

TEAM_ROLES = (
    {
        "role": "icp_trigger_strategist",
        "purpose": (
            "Define evidence-backed ideal client profiles, decision-maker maps "
            "and observable buying triggers before Buyer Scout searches."
        ),
        "automatic": True,
        "external_action": False,
    },
    {
        "role": "demand_gap_analyst",
        "purpose": (
            "Prioritize corridors with overflow, zero active seats, weak "
            "capacity or material supply/demand imbalance."
        ),
        "automatic": True,
        "external_action": False,
    },
    {
        "role": "buyer_scout",
        "purpose": (
            "Discover businesses with evidence they buy leads, calls, "
            "appointments, intent/data feeds or white-label demand."
        ),
        "automatic": True,
        "external_action": False,
    },
    {
        "role": "decision_maker_resolver",
        "purpose": (
            "Resolve current economic/functional buyers from first-party and "
            "corroborated public evidence."
        ),
        "automatic": True,
        "external_action": False,
    },
    {
        "role": "contact_verifier",
        "purpose": (
            "Verify person-bound contact paths separately from identity."
        ),
        "automatic": True,
        "external_action": False,
    },
    {
        "role": "buyer_qualifier",
        "purpose": (
            "Determine purchased unit, verticals, territories, volume, "
            "delivery route, exclusivity and commercial evidence gaps."
        ),
        "automatic": True,
        "external_action": False,
    },
    {
        "role": "outreach_preparer",
        "purpose": (
            "Prepare concise evidence-led outbound proposals and channel plans."
        ),
        "automatic": True,
        "external_action": False,
    },
    {
        "role": "buyer_conversation_intake",
        "purpose": (
            "Classify replies and extract buyer-stated price, capacity, "
            "territory, delivery and acceptance criteria."
        ),
        "automatic": True,
        "external_action": False,
    },
    {
        "role": "commercial_evidence_verifier",
        "purpose": (
            "Advance only deterministic buyer-stated evidence allowed by "
            "existing verification authority."
        ),
        "automatic": True,
        "external_action": False,
    },
    {
        "role": "seat_readiness_agent",
        "purpose": (
            "Evaluate verified terms, capacity, territory and delivery "
            "evidence for corridor-seat readiness."
        ),
        "automatic": True,
        "external_action": False,
    },
    {
        "role": "buyer_success_capacity_agent",
        "purpose": (
            "Refresh capacity and route overflow when seats become full or "
            "available without ever stopping acquisition."
        ),
        "automatic": True,
        "external_action": False,
    },
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _corpus(record: Mapping[str, Any]) -> str:
    values = (
        record.get("business_name"),
        record.get("niche"),
        record.get("notes"),
        record.get("website"),
        record.get("description"),
        record.get("category"),
    )
    return " ".join(_text(value).lower() for value in values if _text(value))


def direct_buyer_profile(record: Mapping[str, Any]) -> dict[str, Any]:
    corpus = _corpus(record)
    direct_hits = {
        phrase: weight
        for phrase, weight in DIRECT_BUYER_SIGNALS.items()
        if phrase in corpus
    }
    buyer_side_hits = {
        phrase: weight
        for phrase, weight in BUYER_SIDE_SIGNALS.items()
        if phrase in corpus
    }
    supplier_side_hits = {
        phrase: weight
        for phrase, weight in SUPPLIER_SIDE_SIGNALS.items()
        if phrase in corpus
    }
    reseller_hits = {
        phrase: weight
        for phrase, weight in RESELLER_SIGNALS.items()
        if phrase in corpus
    }

    # Direct-demand precision matters more than recall. Generic lead-gen or
    # performance-marketing language is supplier-side evidence, not proof that
    # the company purchases third-party commercial inventory.
    buyer_score = (
        sum(buyer_side_hits.values())
        + sum(
            weight
            for phrase, weight in direct_hits.items()
            if phrase in buyer_side_hits
        )
        - min(sum(supplier_side_hits.values()), 60)
    )
    score = max(0, min(100, buyer_score))

    explicit_buyer = bool(buyer_side_hits) and (
        score >= 25 or not supplier_side_hits
    )

    if any(
        phrase in buyer_side_hits
        for phrase in (
            "we buy leads",
            "buy leads",
            "purchase leads",
            "lead purchasing",
            "lead buyer",
            "lead buyers",
        )
    ):
        buyer_type = "direct_lead_buyer"
    elif any(
        phrase in buyer_side_hits
        for phrase in ("buy calls", "call buyer")
    ):
        buyer_type = "call_buyer"
    elif "buy appointments" in buyer_side_hits:
        buyer_type = "appointment_buyer"
    elif any(
        phrase in reseller_hits for phrase in ("white label", "reseller")
    ):
        buyer_type = "white_label_agency"
    elif any(
        phrase in reseller_hits for phrase in ("agency", "marketing agency")
    ):
        buyer_type = "white_label_agency"
    else:
        buyer_type = "qualified_end_buyer"

    return {
        "buyer_type": buyer_type,
        "direct_buyer_score": score,
        "direct_signal_hits": sorted(direct_hits),
        "buyer_side_signal_hits": sorted(buyer_side_hits),
        "supplier_side_signal_hits": sorted(supplier_side_hits),
        "reseller_signal_hits": sorted(reseller_hits),
        "explicit_direct_buyer_evidence": explicit_buyer,
        "binding_commercial_evidence": False,
    }


def _corridor_parts(key: str) -> dict[str, str | None]:
    text = _text(key)
    match = re.fullmatch(
        r"corridor:v1:([^:]+):([^:]+):([^:]+):([^:]+)",
        text,
    )
    if not match:
        return {
            "niche_family": None,
            "territory": None,
            "demand_type": None,
            "delivery_type": None,
        }
    return {
        "niche_family": match.group(1),
        "territory": match.group(2),
        "demand_type": match.group(3),
        "delivery_type": match.group(4),
    }


def build_demand_gap_queue(
    exchange_snapshot: Mapping[str, Any],
) -> list[dict[str, Any]]:
    inventory = [
        dict(row)
        for row in (exchange_snapshot.get("inventory") or [])
        if isinstance(row, Mapping)
    ]
    seats = [
        dict(row)
        for row in (exchange_snapshot.get("buyer_seats") or [])
        if isinstance(row, Mapping)
    ]

    corridor_inventory: Counter[str] = Counter()
    corridor_overflow: Counter[str] = Counter()
    corridor_candidates: Counter[str] = Counter()
    active_capacity: Counter[str] = Counter()
    blocked_seats: Counter[str] = Counter()

    for row in inventory:
        corridor = _text(row.get("corridor_key"))
        if not corridor:
            continue
        corridor_inventory[corridor] += 1
        state = _text(row.get("state"))
        if state == "overflow_no_capacity":
            corridor_overflow[corridor] += 1
        if state == "allocation_candidate":
            corridor_candidates[corridor] += 1

    for row in seats:
        corridor = _text(row.get("corridor_key"))
        if not corridor:
            continue
        state = _text(row.get("seat_state"))
        if state == "active_capacity":
            try:
                capacity = max(int(row.get("remaining_capacity") or 0), 0)
            except (TypeError, ValueError):
                capacity = 0
            active_capacity[corridor] += capacity
        elif state == "blocked_missing_evidence":
            blocked_seats[corridor] += 1

    all_corridors = sorted(
        set(corridor_inventory)
        | set(active_capacity)
        | set(blocked_seats)
    )

    queue: list[dict[str, Any]] = []
    for corridor in all_corridors:
        supply = corridor_inventory[corridor]
        overflow = corridor_overflow[corridor]
        candidates = corridor_candidates[corridor]
        capacity = active_capacity[corridor]
        blocked = blocked_seats[corridor]

        priority = (
            overflow * 100
            + max(supply - capacity, 0) * 40
            + (50 if supply > 0 and capacity == 0 else 0)
            + min(blocked, 20)
        )

        if priority <= 0 and supply <= 0:
            continue

        parts = _corridor_parts(corridor)
        queue.append({
            "corridor_key": corridor,
            **parts,
            "qualified_inventory_count": supply,
            "overflow_count": overflow,
            "allocation_candidate_count": candidates,
            "active_remaining_capacity": capacity,
            "blocked_seat_count": blocked,
            "priority_score": priority,
            "buyer_hunt_required": bool(
                overflow > 0 or (supply > 0 and capacity == 0)
            ),
            "acquisition_should_continue": True,
        })

    queue.sort(
        key=lambda row: (
            -int(row["priority_score"]),
            str(row["corridor_key"]),
        )
    )
    for index, row in enumerate(queue, start=1):
        row["rank"] = index
    return queue


def buyer_research_queries(
    *,
    niche_family: str | None,
    territory: str | None,
) -> dict[str, list[str]]:
    niche = _text(niche_family).replace("_", " ") or "B2B"
    place = _text(territory).replace("_", " ") or ""
    suffix = f" {place}".rstrip()

    return {
        "direct_demand_buyers": [
            f'"we buy {niche} leads"{suffix}',
            f'"buy {niche} leads"{suffix}',
            f'"purchase {niche} leads"{suffix}',
            f'"{niche} lead buyer"{suffix}',
            f'"buy {niche} calls"{suffix}',
            f'"buy {niche} appointments"{suffix}',
            f'"{niche}" "third-party leads"{suffix}',
            f'"{niche}" "lead vendors"{suffix}',
            f'"{niche}" "daily budget" leads{suffix}',
            f'"{niche}" "daily cap" leads{suffix}',
            f'"{niche}" "buy box" leads{suffix}',
        ],
        "local_and_smb_buyers": [
            f'"{niche}" "near me"{suffix}',
            f'"{niche}" "local business"{suffix}',
            f'"{niche}" "small business"{suffix}',
            f'"{niche}" "family owned"{suffix}',
            f'"{niche}" "book online"{suffix}',
            f'"{niche}" "free quote"{suffix}',
        ],
        "end_service_buyers": [
            f'"{niche} company"{suffix}',
            f'"{niche} contractor"{suffix}',
            f'"{niche}" "service area"{suffix}',
            f'"{niche}" "free estimate"{suffix}',
            f'"{niche}" "schedule service"{suffix}',
        ],
        "agency_and_reseller_buyers": [
            f'"{niche}" "marketing agency"{suffix}',
            f'"{niche}" "growth agency"{suffix}',
            f'"{niche}" "white label"{suffix}',
            f'"{niche}" reseller{suffix}',
        ],
        "enterprise_and_data_buyers": [
            f'"{niche}" "market intelligence"{suffix}',
            f'"{niche}" "intent data"{suffix}',
            f'"{niche}" "data provider"{suffix}',
            f'"{niche}" enterprise{suffix}',
        ],
        "software_and_advisory_buyers": [
            f'"{niche}" "sales software"{suffix}',
            f'"{niche}" "revenue operations"{suffix}',
            f'"{niche}" "growth platform"{suffix}',
            f'"{niche}" "revenue audit"{suffix}',
        ],
    }


def _product_buyer_pools(
    product_family: str,
    product_code: str,
) -> list[str]:
    family = _text(product_family).lower()
    code = _text(product_code).lower()

    if family == "search_intelligence" or "search" in code or "serp" in code:
        return [
            "local_and_smb_buyers",
            "agency_and_reseller_buyers",
            "enterprise_and_data_buyers",
            "software_and_advisory_buyers",
        ]
    if family in {
        "private_capital",
        "property",
        "public_record_intelligence",
    }:
        return [
            "enterprise_and_data_buyers",
            "agency_and_reseller_buyers",
            "software_and_advisory_buyers",
        ]
    if family == "opportunity_intelligence":
        return [
            "local_and_smb_buyers",
            "end_service_buyers",
            "agency_and_reseller_buyers",
            "enterprise_and_data_buyers",
            "software_and_advisory_buyers",
        ]
    return [
        "software_and_advisory_buyers",
        "enterprise_and_data_buyers",
        "agency_and_reseller_buyers",
    ]


def _phase4_exchange_mrr_demand_rows() -> list[dict[str, Any]]:
    plan = build_exchange_mrr_product_plan()
    rows: list[dict[str, Any]] = []
    for raw in plan.get("products") or []:
        if not isinstance(raw, Mapping):
            continue
        row = dict(raw)
        code = _text(row.get("product_code"))
        if not code:
            continue
        rows.append({
            "product_code": code,
            "product_name": _text(row.get("name")) or code,
            "product_family": "commercial_exchange",
            "billing_model": "monthly_subscription",
            "commercial_state": "MARKET_VALIDATE_TERMS_REQUIRED",
            "binding_terms_ready": False,
            "catalog_verified": False,
            "target_buyer_pools": [
                "local_and_smb_buyers",
                "end_service_buyers",
                "direct_demand_buyers",
                "agency_and_reseller_buyers",
                "enterprise_and_data_buyers",
            ],
            "priority_score": 70,
            "price_claim_allowed": False,
            "actual_revenue": False,
            "recovered_mrr_product": True,
            "corridor_limit": row.get("corridor_limit"),
            "capacity_model": row.get("capacity_model"),
            "monetization": list(row.get("monetization") or []),
        })
    return rows


def _tag_intelligence_demand_row() -> dict[str, Any]:
    product = get_search_product("tag_intelligence_monitor")
    if product is None:
        raise RuntimeError("tag intelligence product contract missing")
    return {
        "product_code": product.key,
        "product_name": product.name,
        "product_family": product.category,
        "billing_model": product.commercial_model,
        "commercial_state": "MARKET_VALIDATE_TERMS_REQUIRED",
        "binding_terms_ready": False,
        "catalog_verified": False,
        "target_buyer_pools": [
            "local_and_smb_buyers",
            "agency_and_reseller_buyers",
            "enterprise_and_data_buyers",
            "software_and_advisory_buyers",
        ],
        "target_buyer_types": list(product.buyer_types),
        "priority_score": 80,
        "price_claim_allowed": False,
        "actual_revenue": False,
        "recovered_mrr_product": False,
        "new_mrr_product": True,
        "revenue_models": list(product.revenue_models),
    }


def build_product_demand_queue(
    catalog_snapshot: Mapping[str, Any] | None,
) -> list[dict[str, Any]]:
    snapshot = (
        dict(catalog_snapshot)
        if isinstance(catalog_snapshot, Mapping)
        else {}
    )
    products = [
        dict(row)
        for row in (snapshot.get("products") or [])
        if isinstance(row, Mapping)
        and row.get("active") is True
    ]

    queue: list[dict[str, Any]] = []
    for row in products:
        product_code = _text(row.get("product_code"))
        product_name = _text(row.get("product_name"))
        product_family = _text(row.get("product_family"))
        if not product_code:
            continue

        terms_ready = row.get("binding_terms_ready") is True
        catalog_verified = (
            _text(row.get("catalog_state")).upper() == "VERIFIED"
            and _text(row.get("version_state")).upper() == "VERIFIED"
        )
        if terms_ready and catalog_verified:
            state = "SELLABLE_TERMS_READY"
            priority = 100
        else:
            state = "MARKET_VALIDATE_TERMS_REQUIRED"
            priority = 35

        pools = _product_buyer_pools(product_family, product_code)
        queue.append({
            "product_code": product_code,
            "product_name": product_name or product_code,
            "product_family": product_family or None,
            "billing_model": row.get("billing_model"),
            "commercial_state": state,
            "binding_terms_ready": terms_ready,
            "catalog_verified": catalog_verified,
            "target_buyer_pools": pools,
            "priority_score": priority,
            "price_claim_allowed": terms_ready and catalog_verified,
            "actual_revenue": False,
        })

    known_codes = {
        str(row.get("product_code") or "")
        for row in queue
    }
    for row in _phase4_exchange_mrr_demand_rows():
        if row["product_code"] not in known_codes:
            queue.append(row)

    tag_row = _tag_intelligence_demand_row()
    if tag_row["product_code"] not in {
        str(row.get("product_code") or "")
        for row in queue
    }:
        queue.append(tag_row)

    queue.sort(
        key=lambda row: (
            -int(row["priority_score"]),
            str(row["product_code"]),
        )
    )
    for index, row in enumerate(queue, start=1):
        row["rank"] = index
    return queue


def product_research_queries(
    product: Mapping[str, Any],
) -> dict[str, list[str]]:
    name = _text(product.get("product_name")) or _text(
        product.get("product_code")
    )
    family = _text(product.get("product_family")).replace("_", " ")
    subject = family or name

    return {
        "local_and_smb_buyers": [
            f'"{subject}" "small business"',
            f'"{subject}" "local business"',
            f'"{subject}" agency',
        ],
        "agency_and_reseller_buyers": [
            f'"{subject}" "marketing agency"',
            f'"{subject}" "white label"',
            f'"{subject}" reseller',
        ],
        "enterprise_and_data_buyers": [
            f'"{subject}" enterprise',
            f'"{subject}" "data team"',
            f'"{subject}" "market intelligence"',
        ],
        "software_and_advisory_buyers": [
            f'"{subject}" software',
            f'"{subject}" "revenue operations"',
            f'"{subject}" "growth team"',
        ],
    }


def build_buyer_acquisition_plan(
    exchange_snapshot: Mapping[str, Any],
    *,
    catalog_snapshot: Mapping[str, Any] | None = None,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    queue = build_demand_gap_queue(exchange_snapshot)
    product_queue = build_product_demand_queue(catalog_snapshot)
    targets = []
    for row in queue[:25]:
        targets.append({
            **row,
            "research_queries": buyer_research_queries(
                niche_family=row.get("niche_family"),
                territory=row.get("territory"),
            ),
            "preferred_buyer_types": list(TARGET_BUYER_TYPES),
        })

    product_targets = [
        {
            **row,
            "research_queries": product_research_queries(row),
        }
        for row in product_queue[:25]
    ]
    icp_targets = build_icp_priority_targets(
        corridor_targets=targets,
        product_targets=product_targets,
    )
    enterprise_review = build_enterprise_target_review()

    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("generated_at must include timezone")

    supply = exchange_snapshot.get("supply_gate_diagnostics")
    supply = dict(supply) if isinstance(supply, Mapping) else {}
    seat_blockers = exchange_snapshot.get("seat_activation_blocker_counts")
    seat_blockers = (
        dict(seat_blockers)
        if isinstance(seat_blockers, Mapping)
        else {}
    )

    return {
        "schema_version": "empire.buyer_acquisition_team.v1",
        "phase": "4",
        "mode": "OBSERVE",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "team_roles": [dict(row) for row in TEAM_ROLES],
        "team_role_count": len(TEAM_ROLES),
        "target_buyer_types": list(TARGET_BUYER_TYPES),
        "buyer_pools": [
            {
                "pool": row["pool"],
                "examples": list(row["examples"]),
                "purchases": list(row["purchases"]),
            }
            for row in BUYER_POOLS
        ],
        "demand_gap_queue": queue,
        "demand_gap_count": len(queue),
        "priority_targets": targets,
        "product_demand_queue": product_queue,
        "product_demand_count": len(product_queue),
        "sellable_product_demand_count": sum(
            row["binding_terms_ready"] and row["catalog_verified"]
            for row in product_queue
        ),
        "market_validate_product_count": sum(
            not (
                row["binding_terms_ready"]
                and row["catalog_verified"]
            )
            for row in product_queue
        ),
        "product_priority_targets": product_targets,
        "icp_buyer_trigger_intelligence": {
            "enabled": True,
            "profile_count": len(icp_targets),
            "priority_targets": icp_targets,
            "target_company_count_per_campaign": 100,
            "bounded_incremental_discovery": True,
            "single_run_100_company_scrape": False,
            "research_stages": [
                {
                    "stage": "define_icp",
                    "automatic": True,
                    "external_action": False,
                },
                {
                    "stage": "find_matching_companies",
                    "automatic": True,
                    "external_action": False,
                    "evidence_required": True,
                    "deduplicate": True,
                },
                {
                    "stage": "resolve_decision_maker",
                    "automatic": True,
                    "external_action": False,
                    "public_evidence_only": True,
                },
                {
                    "stage": "find_evidence_backed_pain",
                    "automatic": True,
                    "external_action": False,
                    "invented_problem_claims_allowed": False,
                },
                {
                    "stage": "prepare_one_to_one_message",
                    "automatic": True,
                    "external_action": False,
                    "generic_sales_language_allowed": False,
                    "fake_personalization_allowed": False,
                },
                {
                    "stage": "prepare_batch_personalization",
                    "automatic": True,
                    "external_action": False,
                    "verified_observations_only": True,
                    "live_send": False,
                },
            ],
            "evidence_sources": [
                "first_party_website",
                "public_job_opening",
                "public_announcement",
                "public_content",
                "public_product_launch",
                "public_customer_review",
                "corroborated_public_source",
            ],
            "personalization_output_fields": [
                "company",
                "decision_maker",
                "role",
                "channel",
                "verified_observation",
                "observed_problem_evidence",
                "buying_trigger",
                "personalization_angle",
                "draft_message",
            ],
            "learning_contract": icp_learning_contract(),
            "budget_estimates_are_verified": False,
            "binding_intent_created": False,
            "qualification_created": False,
            "outreach_authorized": False,
            "execution_authority": "none",
        },
        "icp_priority_target_count": len(icp_targets),
        "icp_priority_targets": icp_targets,
        "predictive_revenue_enterprise_targets": enterprise_review,
        "predictive_revenue_enterprise_target_count": enterprise_review[
            "target_count"
        ],
        "supply_gate_diagnostics": supply,
        "seat_activation_blocker_counts": seat_blockers,
        "commercial_fact_capture": [
            "purchased_unit",
            "niches_or_products",
            "territories",
            "daily_capacity",
            "monthly_capacity",
            "exclusive_or_shared",
            "acceptance_criteria",
            "delivery_method",
            "price_or_rate",
            "return_or_replacement_terms",
            "compliance_requirements",
            "payment_terms",
            "settlement_rail",
        ],
        "automation": {
            "demand_gap_reprioritization": True,
            "icp_definition": True,
            "buying_trigger_detection": True,
            "icp_definition_and_trigger_planning": True,
            "buyer_research_planning": True,
            "decision_maker_resolution": True,
            "evidenced_problem_research": True,
            "evidence_grounded_personalization": True,
            "evidence_backed_pain_research": True,
            "personalized_outreach_preparation": True,
            "batch_personalization_preparation": True,
            "contact_enrichment": True,
            "review_proposal_generation": True,
            "reply_classification": True,
            "commercial_evidence_extraction": True,
            "deterministic_evidence_verification": True,
            "seat_readiness_refresh": True,
            "capacity_refresh": True,
            "live_outbound_send": False,
        },
        "legacy_buyer_hunter_is_canonical": False,
        "legacy_settlement_assumptions_allowed": False,
        "canonical_settlement_rail": "USDT_BSC",
        "buyer_capacity_never_gates_acquisition": True,
        "overflow_remains_empire_owned": True,
        "outbound_sent": False,
        "terms_accepted": False,
        "payment_mutation": False,
        "actual_revenue": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }


def _read_runtime_snapshot(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}, {
            "state": "MISSING",
            "path": str(path),
            "readable": False,
        }
    except PermissionError:
        return {}, {
            "state": "PERMISSION_DENIED",
            "path": str(path),
            "readable": False,
        }
    except OSError as exc:
        return {}, {
            "state": "READ_ERROR",
            "path": str(path),
            "readable": False,
            "error": f"{type(exc).__name__}:{str(exc)[:160]}",
        }

    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}, {
            "state": "INVALID_JSON",
            "path": str(path),
            "readable": True,
        }
    if not isinstance(value, dict):
        return {}, {
            "state": "INVALID_ROOT_TYPE",
            "path": str(path),
            "readable": True,
        }
    return value, {
        "state": "OK",
        "path": str(path),
        "readable": True,
    }


def refresh_buyer_acquisition_plan(
    repo_root: str | Path,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    exchange, exchange_health = _read_runtime_snapshot(
        root / "runtime/commercial_exchange/latest.json"
    )
    catalog, catalog_health = _read_runtime_snapshot(
        root / "runtime/commercial_catalog/latest.json"
    )

    payload = build_buyer_acquisition_plan(
        exchange,
        catalog_snapshot=catalog,
    )

    permit_inventory, permit_inventory_health = _read_runtime_snapshot(
        root / "runtime/recovery/legacy_permit_inventory_summary.json"
    )
    permit_targets: list[dict[str, Any]] = []
    niche_counts = (
        dict(permit_inventory.get("niche_counts") or {})
        if permit_inventory
        else {}
    )
    ranked_niches = sorted(
        (
            (str(raw_niche), int(raw_count or 0))
            for raw_niche, raw_count in niche_counts.items()
            if int(raw_count or 0) > 0
        ),
        key=lambda item: (-item[1], item[0]),
    )
    seen_families: set[str] = set()
    for raw_niche, count in ranked_niches:
        family = niche_family(raw_niche)
        if not family or family in seen_families:
            continue
        seen_families.add(family)
        permit_targets.append({
            "corridor_key": (
                "permit-recovery:v1:"
                + re.sub(r"[^a-z0-9]+", "_", family).strip("_")
                + ":nyc"
            ),
            "niche_family": family,
            "territory": "nyc",
            "qualified_inventory_count": count,
            "verified_supply_observation_count": count,
            "overflow_count": 0,
            "allocation_candidate_count": 0,
            "active_remaining_capacity": 0,
            "blocked_seat_count": 0,
            "priority_score": 10000 + min(count, 9999),
            "buyer_hunt_required": True,
            "acquisition_should_continue": True,
            "research_queries": buyer_research_queries(
                niche_family=family,
                territory="nyc",
            ),
            "preferred_buyer_types": list(TARGET_BUYER_TYPES),
            "product_code": "permit_intelligence",
            "source": "legacy_permit_verified_inventory",
            "canonical_inventory_claimed": False,
            "commercial_ready_claimed": False,
        })
        if len(permit_targets) >= 5:
            break

    if permit_targets:
        payload["priority_targets"] = [
            *permit_targets,
            *list(payload.get("priority_targets") or []),
        ]
        payload["demand_gap_count"] = len(payload["priority_targets"])

    payload["permit_inventory_demand"] = {
        "status": (
            "ACTIVE" if permit_inventory else "NOT_MATERIALIZED"
        ),
        "verified_current_inventory": int(
            permit_inventory.get("verified_current_inventory") or 0
        ),
        "verified_current_owner_identified": int(
            permit_inventory.get(
                "verified_current_owner_identified"
            ) or 0
        ),
        "verified_current_project_only": int(
            permit_inventory.get("verified_current_project_only") or 0
        ),
        "buyer_hunt_target_count": len(permit_targets),
        "buyer_hunt_targets": permit_targets,
        "product_code": "permit_intelligence",
        "canonical_inventory_claimed": False,
        "commercial_ready_claimed": False,
        "allocation_authority": "none",
        "outbound_authority": "none",
        "actual_revenue": False,
    }

    enterprise_activation, enterprise_activation_health = (
        _read_runtime_snapshot(
            root
            / "runtime/predictive_revenue/"
            "enterprise_activation_latest.json"
        )
    )
    if enterprise_activation:
        payload["predictive_revenue_enterprise_activation"] = {
            "status": enterprise_activation.get("status"),
            "target_count": enterprise_activation.get("target_count", 0),
            "canonical_prospect_count": enterprise_activation.get(
                "canonical_prospect_count", 0
            ),
            "qualified_count": enterprise_activation.get(
                "qualified_count", 0
            ),
            "review_ready_count": enterprise_activation.get(
                "review_ready_count", 0
            ),
            "person_contact_verified_count": enterprise_activation.get(
                "person_contact_verified_count", 0
            ),
            "company_route_available_count": enterprise_activation.get(
                "company_route_available_count", 0
            ),
            "failed_count": enterprise_activation.get("failed_count", 0),
            "live_outbound_send": False,
            "actual_revenue": False,
        }
    else:
        payload["predictive_revenue_enterprise_activation"] = {
            "status": "NOT_MATERIALIZED",
            "target_count": 0,
            "canonical_prospect_count": 0,
            "qualified_count": 0,
            "review_ready_count": 0,
            "person_contact_verified_count": 0,
            "company_route_available_count": 0,
            "failed_count": 0,
            "live_outbound_send": False,
            "actual_revenue": False,
        }

    enterprise_contacts, enterprise_contacts_health = (
        _read_runtime_snapshot(
            root
            / "runtime/predictive_revenue/"
            "enterprise_contact_intelligence_latest.json"
        )
    )
    payload["predictive_revenue_enterprise_contact_intelligence"] = {
        "status": (
            "ACTIVE"
            if enterprise_contacts
            else "NOT_MATERIALIZED"
        ),
        "proposed_review_count": enterprise_contacts.get(
            "proposed_review_count", 0
        ),
        "targeted_retry_queued_count": enterprise_contacts.get(
            "targeted_retry_queued_count", 0
        ),
        "skipped_count": enterprise_contacts.get("skipped_count", 0),
        "error_count": enterprise_contacts.get("error_count", 0),
        "live_outbound_send": False,
        "actual_revenue": False,
    }

    payload["runtime_input_health"] = {
        "commercial_exchange": exchange_health,
        "commercial_catalog": catalog_health,
        "predictive_revenue_enterprise_activation": (
            enterprise_activation_health
        ),
        "predictive_revenue_enterprise_contact_intelligence": (
            enterprise_contacts_health
        ),
        "permit_inventory": permit_inventory_health,
        "degraded": (
            exchange_health["state"] != "OK"
            or catalog_health["state"] != "OK"
            or permit_inventory_health["state"] != "OK"
        ),
    }
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
