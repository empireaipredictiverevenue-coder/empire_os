"""ICP and buying-trigger intelligence for governed buyer acquisition.

The module prioritizes who Empire should research before Buyer Scout searches.
Scores are deterministic heuristics over observed/public evidence. They are not
verified budget, intent, qualification, commercial terms, or revenue.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping


ICP_PROFILES: tuple[dict[str, Any], ...] = (
    {
        "profile_key": "direct_demand_buyer",
        "name": "Direct Lead / Call / Appointment Buyer",
        "buyer_pools": ["direct_demand_buyers"],
        "industry_signals": [
            "lead buyer", "lead marketplace", "lead distribution",
            "pay per lead", "pay per call", "affiliate network",
            "performance marketing", "appointment setting",
        ],
        "decision_maker_roles": [
            "founder", "ceo", "chief revenue officer", "cro",
            "head of growth", "vp growth", "media buyer",
            "partnerships", "affiliate manager",
        ],
        "likely_problems": [
            "insufficient qualified volume",
            "uneven vertical or territory coverage",
            "high acquisition cost",
            "limited verified supply",
        ],
        "buying_triggers": [
            "buy leads", "pay per lead", "pay per call",
            "new vertical", "new market", "expansion",
            "affiliate partners", "lead volume",
        ],
        "product_codes": [
            "exchange_seat_starter", "exchange_seat_growth",
            "exchange_seat_pro", "exchange_seat_enterprise",
        ],
        "priority_score": 96,
    },
    {
        "profile_key": "multi_location_service_business",
        "name": "Multi-location Service Business",
        "buyer_pools": [
            "local_and_smb_buyers", "software_and_advisory_buyers",
        ],
        "industry_signals": [
            "multi-location", "locations", "service area", "clinic",
            "dental", "legal", "estate agent", "home services",
            "franchise", "branches",
        ],
        "decision_maker_roles": [
            "founder", "ceo", "cmo", "chief marketing officer",
            "head of growth", "marketing director",
            "revenue operations", "revops",
        ],
        "likely_problems": [
            "inconsistent local visibility",
            "weak attribution across locations",
            "missed geographic demand",
            "fragmented conversion measurement",
        ],
        "buying_triggers": [
            "new location", "opening", "expansion", "new market",
            "hiring", "acquisition", "franchise", "rebrand",
        ],
        "product_codes": [
            "local_search_grid", "tag_intelligence_monitor",
            "search_growth_command", "competitor_search_gap",
        ],
        "priority_score": 92,
    },
    {
        "profile_key": "high_ticket_home_service",
        "name": "High-ticket Home Service Operator",
        "buyer_pools": [
            "end_service_buyers", "local_and_smb_buyers",
        ],
        "industry_signals": [
            "roofing", "hvac", "solar", "restoration", "plumbing",
            "gutter", "general contractor", "insurance restoration",
        ],
        "decision_maker_roles": [
            "owner", "founder", "ceo", "general manager",
            "sales director", "marketing director", "head of growth",
        ],
        "likely_problems": [
            "lead volatility",
            "territory coverage gaps",
            "slow response to event-driven demand",
            "high paid acquisition cost",
        ],
        "buying_triggers": [
            "storm", "hail", "wind damage", "emergency",
            "free estimate", "financing", "new service area",
            "hiring", "expansion",
        ],
        "product_codes": [
            "managed_service", "local_search_grid",
            "search_growth_command", "tag_intelligence_monitor",
        ],
        "priority_score": 94,
    },
    {
        "profile_key": "agency_white_label_partner",
        "name": "Agency / White-label Partner",
        "buyer_pools": ["agency_and_reseller_buyers"],
        "industry_signals": [
            "marketing agency", "seo agency", "growth agency",
            "lead generation agency", "white label", "reseller",
        ],
        "decision_maker_roles": [
            "founder", "agency owner", "ceo", "managing director",
            "head of growth", "client services director",
        ],
        "likely_problems": [
            "delivery capacity constraints",
            "need for differentiated intelligence",
            "client reporting gaps",
            "need for scalable fulfilment",
        ],
        "buying_triggers": [
            "white label", "new clients", "client growth",
            "hiring", "partnership", "reseller", "scale",
        ],
        "product_codes": [
            "tag_intelligence_monitor", "local_search_grid",
            "search_growth_command", "serp_intelligence_api",
        ],
        "priority_score": 90,
    },
    {
        "profile_key": "private_capital_rollup",
        "name": "Private Capital / Roll-up Operator",
        "buyer_pools": ["enterprise_and_data_buyers"],
        "industry_signals": [
            "private equity", "investment firm", "portfolio",
            "roll-up", "rollup", "acquisition", "bolt-on",
            "operating partner",
        ],
        "decision_maker_roles": [
            "partner", "principal", "operating partner",
            "head of origination", "investment director",
            "vice president", "vp",
        ],
        "likely_problems": [
            "fragmented target discovery",
            "slow market mapping",
            "poor geographic expansion intelligence",
            "limited early acquisition signals",
        ],
        "buying_triggers": [
            "new fund", "platform acquisition", "bolt-on",
            "add-on acquisition", "portfolio expansion",
            "sector mandate", "acquisition strategy",
        ],
        "product_codes": [
            "private_capital_intelligence",
            "property_intelligence",
            "permit_intelligence",
            "managed_service",
        ],
        "priority_score": 95,
    },
    {
        "profile_key": "predictive_revenue_home_services_platform",
        "name": "Predictive Revenue — Multi-brand Home Services Platform",
        "buyer_pools": [
            "enterprise_and_data_buyers",
            "software_and_advisory_buyers",
        ],
        "industry_signals": [
            "home services platform", "multi-brand home services",
            "hvac plumbing electrical", "residential services platform",
            "portfolio brands", "national home services",
            "multi-location home services",
        ],
        "decision_maker_roles": [
            "chief executive officer", "ceo", "chief revenue officer",
            "cro", "chief marketing officer", "cmo",
            "chief technology officer", "cto", "chief information officer",
            "revenue operations", "analytics", "data",
        ],
        "likely_problems": [
            "fragmented cross-brand revenue visibility",
            "uneven market demand and capacity",
            "slow identification of growth opportunities",
            "inconsistent forecasting across operating companies",
        ],
        "buying_triggers": [
            "acquisition", "expansion", "data analytics",
            "technology investment", "new market", "new leadership",
            "portfolio growth",
        ],
        "product_codes": [
            "predictive_revenue_intelligence_os",
            "predictive_revenue_autonomous_os",
            "predictive_revenue_private_strategic",
        ],
        "priority_score": 100,
    },
    {
        "profile_key": "predictive_revenue_franchise_network",
        "name": "Predictive Revenue — Franchise / Multi-location Network",
        "buyer_pools": [
            "enterprise_and_data_buyers",
            "software_and_advisory_buyers",
        ],
        "industry_signals": [
            "franchise network", "multi-brand franchise",
            "franchise platform", "franchise locations",
            "multi-location services", "central marketing",
            "consumer insights",
        ],
        "decision_maker_roles": [
            "chief executive officer", "ceo",
            "chief marketing officer", "cmo",
            "chief growth officer", "growth",
            "strategic operations", "analytics",
            "consumer insights", "data",
        ],
        "likely_problems": [
            "fragmented franchise performance signals",
            "slow cross-brand demand detection",
            "weak leading indicators across locations",
            "inconsistent local market visibility",
        ],
        "buying_triggers": [
            "analytics", "ai", "marketing automation",
            "expansion", "new app", "new leadership",
            "customer data",
        ],
        "product_codes": [
            "predictive_revenue_autonomous_os",
            "predictive_revenue_intelligence_os",
            "predictive_revenue_private_strategic",
        ],
        "priority_score": 99,
    },
    {
        "profile_key": "predictive_revenue_portfolio_value_creation",
        "name": "Predictive Revenue — Portfolio Value Creation / Operating Team",
        "buyer_pools": ["enterprise_and_data_buyers"],
        "industry_signals": [
            "private equity operating team", "portfolio value creation",
            "portfolio operations", "operating partner",
            "portfolio analytics", "ai value creation",
            "digital transformation portfolio",
        ],
        "decision_maker_roles": [
            "operating partner", "portfolio operations",
            "value creation", "digital", "ai",
            "data", "technology", "chief executive officer",
        ],
        "likely_problems": [
            "inconsistent revenue measurement across portfolio companies",
            "slow opportunity detection",
            "weak forecast-versus-actual calibration",
            "fragmented operating data across portfolio companies",
        ],
        "buying_triggers": [
            "value creation", "ai", "portfolio transformation",
            "operational performance", "growth", "acquisition",
            "digital transformation",
        ],
        "product_codes": [
            "predictive_revenue_diagnostic",
            "predictive_revenue_private_strategic",
            "predictive_revenue_intelligence_os",
        ],
        "priority_score": 100,
    },
    {
        "profile_key": "legal_mass_tort_plaintiff_firm",
        "name": "Legal — Mass Tort Plaintiff Firm",
        "buyer_pools": [
            "enterprise_and_data_buyers",
            "software_and_advisory_buyers",
            "direct_demand_buyers",
        ],
        "industry_signals": [
            "mass tort law firm", "mass tort lawyer",
            "mass tort attorneys", "class action law firm",
            "class action lawyer", "multidistrict litigation",
            "mdL", "plaintiff law firm",
        ],
        "decision_maker_roles": [
            "managing partner", "founding partner", "partner",
            "chief marketing officer", "marketing director",
            "intake director", "chief operating officer",
            "business development",
        ],
        "likely_problems": [
            "volatile case acquisition cost",
            "uneven campaign and intake capacity",
            "slow market and litigation signal detection",
            "fragmented search and competitor intelligence",
        ],
        "buying_triggers": [
            "new litigation", "multidistrict litigation",
            "case intake", "mass tort", "class action",
            "campaign launch", "intake expansion",
        ],
        "product_codes": [
            "managed_service",
            "search_growth_command",
            "tag_intelligence_monitor",
            "competitor_search_gap",
        ],
        "priority_score": 100,
    },
    {
        "profile_key": "legal_plaintiff_growth_firm",
        "name": "Legal — Personal Injury / High-value Plaintiff Firm",
        "buyer_pools": [
            "enterprise_and_data_buyers",
            "software_and_advisory_buyers",
            "direct_demand_buyers",
        ],
        "industry_signals": [
            "personal injury law firm", "personal injury lawyer",
            "plaintiff law firm", "medical malpractice law firm",
            "medical malpractice lawyer", "workers compensation law firm",
            "workers comp lawyer",
            "catastrophic injury", "trial lawyers",
        ],
        "decision_maker_roles": [
            "managing partner", "founding partner", "partner",
            "chief marketing officer", "marketing director",
            "intake director", "chief operating officer",
            "business development",
        ],
        "likely_problems": [
            "high lead acquisition cost",
            "weak intake conversion visibility",
            "territory and practice-area demand gaps",
            "competitive search pressure",
        ],
        "buying_triggers": [
            "expansion", "new office", "hiring",
            "case intake", "marketing", "growth",
            "new practice area",
        ],
        "product_codes": [
            "managed_service",
            "search_growth_command",
            "tag_intelligence_monitor",
            "competitor_search_gap",
        ],
        "priority_score": 98,
    },
    {
        "profile_key": "insurance_distribution_growth",
        "name": "Insurance — Distribution / Agency Network",
        "buyer_pools": [
            "enterprise_and_data_buyers",
            "software_and_advisory_buyers",
            "direct_demand_buyers",
        ],
        "industry_signals": [
            "insurance agency network", "insurance brokerage",
            "independent insurance agency", "insurance distribution",
            "insurance marketplace", "insurance leads",
            "insurance call center", "auto insurance",
            "life insurance agent", "public insurance adjuster",
            "final expense insurance", "medicare advantage agent",
        ],
        "decision_maker_roles": [
            "chief executive officer", "ceo",
            "chief revenue officer", "cro",
            "chief marketing officer", "cmo",
            "chief growth officer", "head of growth",
            "distribution", "digital", "analytics",
        ],
        "likely_problems": [
            "uneven producer and territory demand",
            "high customer acquisition cost",
            "fragmented channel attribution",
            "slow identification of profitable markets",
        ],
        "buying_triggers": [
            "acquisition", "expansion", "new market",
            "digital transformation", "distribution growth",
            "new leadership", "lead generation",
        ],
        "product_codes": [
            "managed_service",
            "search_growth_command",
            "tag_intelligence_monitor",
            "competitor_search_gap",
        ],
        "priority_score": 98,
    },
    {
        "profile_key": "enterprise_growth_data_team",
        "name": "Enterprise Growth / Data Team",
        "buyer_pools": [
            "enterprise_and_data_buyers",
            "software_and_advisory_buyers",
        ],
        "industry_signals": [
            "enterprise", "revenue operations", "revops",
            "growth team", "sales operations", "market intelligence",
            "data team", "multi-location",
        ],
        "decision_maker_roles": [
            "chief revenue officer", "cro", "cmo",
            "vp sales", "vp marketing", "head of growth",
            "revenue operations", "revops", "data director",
        ],
        "likely_problems": [
            "fragmented market signals",
            "weak revenue attribution",
            "slow account prioritization",
            "limited competitor intelligence",
        ],
        "buying_triggers": [
            "new market", "expansion", "funding", "acquisition",
            "new leadership", "hiring", "go-to-market",
            "revenue operations",
        ],
        "product_codes": [
            "tag_intelligence_monitor", "managed_service",
            "serp_intelligence_api", "competitor_search_gap",
        ],
        "priority_score": 91,
    },
)

ECONOMIC_CAPACITY_PROXY_TERMS = (
    "multi-location", "multiple locations", "locations",
    "enterprise", "portfolio", "national", "international",
    "franchise", "branches", "fund", "acquisition",
)

LEARNING_OUTCOMES = (
    "reply_positive",
    "reply_negative",
    "meeting_booked",
    "qualified_opportunity",
    "terms_accepted",
    "payment_verified",
    "recognized_revenue",
    "realized_gross_profit",
    "lost_reason",
)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _profile_index() -> dict[str, dict[str, Any]]:
    return {
        str(profile["profile_key"]): dict(profile)
        for profile in ICP_PROFILES
    }


def build_icp_priority_targets(
    *,
    corridor_targets: Iterable[Mapping[str, Any]] = (),
    product_targets: Iterable[Mapping[str, Any]] = (),
) -> list[dict[str, Any]]:
    """Build bounded ICP-led search targets ahead of Buyer Scout."""
    territories = []
    niches = []
    for row in corridor_targets:
        territory = _text(row.get("territory")).replace("_", " ")
        niche = _text(row.get("niche_family")).replace("_", " ")
        if territory and territory not in territories:
            territories.append(territory)
        if niche and niche not in niches:
            niches.append(niche)

    active_products = {
        _text(row.get("product_code"))
        for row in product_targets
        if _text(row.get("product_code"))
    }

    targets: list[dict[str, Any]] = []
    for profile in ICP_PROFILES:
        product_overlap = sorted(
            set(profile["product_codes"]) & active_products
        )
        priority = int(profile["priority_score"]) + min(
            len(product_overlap) * 2, 6
        )
        terms = list(profile["industry_signals"])
        triggers = list(profile["buying_triggers"])
        place = territories[0] if territories else ""
        niche = niches[0] if niches else ""

        subject = terms[0]
        if profile["profile_key"] == "high_ticket_home_service" and niche:
            subject = niche

        suffix = f" {place}".rstrip()
        queries = [
            f'"{subject}" "{triggers[0]}"{suffix}',
            f'"{subject}" "{triggers[1]}"{suffix}',
        ]

        targets.append({
            "icp_profile_key": profile["profile_key"],
            "icp_name": profile["name"],
            "priority_score": priority,
            "buyer_pools": list(profile["buyer_pools"]),
            "decision_maker_roles": list(
                profile["decision_maker_roles"]
            ),
            "likely_problems": list(profile["likely_problems"]),
            "buying_triggers": triggers,
            "product_codes": list(profile["product_codes"]),
            "active_product_overlap": product_overlap,
            "research_queries": {
                pool: list(queries)
                for pool in profile["buyer_pools"]
            },
            "budget_verified": False,
            "binding_intent_verified": False,
            "qualification_created": False,
        })

    targets.sort(
        key=lambda row: (
            -int(row["priority_score"]),
            str(row["icp_profile_key"]),
        )
    )
    for index, row in enumerate(targets, start=1):
        row["rank"] = index
    return targets


def assess_icp_candidate(
    record: Mapping[str, Any],
    *,
    target_profile_keys: Iterable[str] = (),
) -> dict[str, Any]:
    """Assess fit using only observed/public candidate evidence."""
    profiles = _profile_index()
    selected = [
        profiles[key]
        for key in target_profile_keys
        if key in profiles
    ]
    if not selected:
        selected = list(profiles.values())

    people = [
        dict(person)
        for person in (record.get("first_party_people") or [])
        if isinstance(person, Mapping)
    ]
    corpus_parts = [
        record.get("business_name"),
        record.get("description"),
        record.get("notes"),
        record.get("buyer_type"),
        " ".join(record.get("direct_signal_hits") or []),
        " ".join(record.get("reseller_signal_hits") or []),
        " ".join(
            _text(person.get("title"))
            for person in people
        ),
    ]
    corpus = " ".join(
        _text(value).lower()
        for value in corpus_parts
        if _text(value)
    )
    buyer_pools = {
        _text(value)
        for value in (record.get("target_buyer_pools") or [])
        if _text(value)
    }
    products = {
        _text(value)
        for value in (record.get("target_product_codes") or [])
        if _text(value)
    }

    assessments: list[dict[str, Any]] = []
    for profile in selected:
        industry_hits = sorted({
            term for term in profile["industry_signals"]
            if term in corpus
        })
        trigger_hits = sorted({
            term for term in profile["buying_triggers"]
            if term in corpus
        })
        role_hits = sorted({
            role
            for role in profile["decision_maker_roles"]
            if role in corpus
        })
        pool_hits = sorted(
            set(profile["buyer_pools"]) & buyer_pools
        )
        product_hits = sorted(
            set(profile["product_codes"]) & products
        )

        score = min(
            100,
            len(industry_hits) * 14
            + len(trigger_hits) * 12
            + len(role_hits) * 8
            + len(pool_hits) * 18
            + len(product_hits) * 6,
        )
        assessments.append({
            "profile_key": profile["profile_key"],
            "profile_name": profile["name"],
            "model_fit_score": score,
            "industry_signal_hits": industry_hits,
            "buying_trigger_hits": trigger_hits,
            "decision_maker_role_hits": role_hits,
            "buyer_pool_hits": pool_hits,
            "product_fit_hits": product_hits,
        })

    assessments.sort(
        key=lambda row: (
            -int(row["model_fit_score"]),
            str(row["profile_key"]),
        )
    )
    best = assessments[0] if assessments else {}

    economic_hits = sorted({
        term
        for term in ECONOMIC_CAPACITY_PROXY_TERMS
        if term in corpus
    })
    observed_triggers = list(best.get("buying_trigger_hits") or [])
    decision_roles = list(
        best.get("decision_maker_role_hits") or []
    )

    return {
        "best_profile_key": best.get("profile_key"),
        "best_profile_name": best.get("profile_name"),
        "model_fit_score": int(best.get("model_fit_score") or 0),
        "score_classification": "MODEL_HEURISTIC",
        "fit_evidence": {
            "industry_signal_hits": list(
                best.get("industry_signal_hits") or []
            ),
            "buyer_pool_hits": list(
                best.get("buyer_pool_hits") or []
            ),
            "product_fit_hits": list(
                best.get("product_fit_hits") or []
            ),
        },
        "observed_buying_triggers": observed_triggers,
        "why_now_state": (
            "OBSERVED_TRIGGER" if observed_triggers else "UNKNOWN"
        ),
        "decision_maker_role_hits": decision_roles,
        "decision_maker_state": (
            "OBSERVED_ROLE_MATCH" if decision_roles else "UNKNOWN"
        ),
        "economic_capacity_state": (
            "OBSERVED_PROXY" if economic_hits else "UNKNOWN"
        ),
        "economic_capacity_evidence": economic_hits,
        "budget_verified": False,
        "binding_intent_verified": False,
        "qualification_created": False,
        "commercial_terms_verified": False,
        "outreach_authorized": False,
        "actual_revenue": False,
        "profile_assessments": assessments[:3],
    }


def icp_learning_contract() -> dict[str, Any]:
    return {
        "learning_source": "observed_commercial_outcomes_only",
        "accepted_outcomes": list(LEARNING_OUTCOMES),
        "forecast_is_revenue": False,
        "reply_is_revenue": False,
        "meeting_is_revenue": False,
        "payment_request_is_revenue": False,
        "payment_verified_is_recognized_revenue": False,
        "synthetic_training_outcomes_allowed": False,
        "execution_authority": "none",
    }
