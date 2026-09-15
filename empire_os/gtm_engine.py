#!/usr/bin/env python3
"""Empire OS GTM Engine v2.

Plan-only commercial control plane.

Principles:
- demand before volume
- fulfilment capacity before generation
- observed economics before invented economics
- niche/metro identity-aware buyer matching
- MRR and visibility remain first-class GTM motions
- no outreach, campaign launch, invoice creation, fulfilment trigger,
  or Supabase mutation occurs in this version
"""

from __future__ import annotations

import json
import math
import os
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from empire_os.niche_taxonomy import (
    NICHE_FAMILIES,
    metro_key,
    niche_family,
    normalise,
)

ENV_PATH = "/etc/empire_os.env"

RUNTIME_ROOT = Path(
    os.environ.get("EMPIRE_RUNTIME_ROOT", "/srv/empire_os/runtime")
)

REPORT_PATH = Path(
    os.environ.get(
        "GTM_PLAN_PATH",
        str(RUNTIME_ROOT / "gtm" / "gtm_plan.json"),
    )
)

BATCH_SIZE = 1000


# ---------------------------------------------------------------------------
# Normalisation / matching
# ---------------------------------------------------------------------------

# Canonical niche/metro matching lives in niche_taxonomy.py.
# Keep this engine focused on commercial planning and economics.

def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def saturate(value: float, scale: float) -> float:
    if value <= 0 or scale <= 0:
        return 0.0

    return clamp(1.0 - math.exp(-value / scale))


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BuyerSignal:
    buyer_id: str
    buyer_name: str
    niche: str
    niche_family: str
    metro: str
    is_active: bool
    status: str
    daily_cap: int
    calls_today: int
    remaining_capacity: int
    buyer_rate: float | None
    priority: float


@dataclass(frozen=True)
class Opportunity:
    niche: str
    niche_family: str
    metro: str

    prospect_count: int
    new_count: int
    bridged_count: int
    activated_count: int

    buyer_count: int
    buyer_capacity: int
    high_priority_buyer_count: int

    observed_buyer_rate: float | None

    supply_score: float
    buyer_demand_score: float
    economic_score: float
    fulfilment_score: float
    visibility_score: float
    activation_gap_score: float

    market_balance: str
    priority_score: float

    expected_revenue_cents: int
    expected_margin_cents: int

    rationale: list[str]


@dataclass(frozen=True)
class GTMJob:
    job_type: str
    priority: float
    target: dict[str, Any]
    status: str
    worker_adapter: str
    requires_approval: bool
    payload: dict[str, Any]


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------

def load_env() -> dict[str, str]:
    env: dict[str, str] = {}

    with open(ENV_PATH, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()

            if (
                line
                and not line.startswith("#")
                and "=" in line
            ):
                key, value = line.split("=", 1)
                env[key] = value

    return env


ENV = load_env()

SUPABASE_URL = ENV["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = ENV["SUPABASE_SERVICE_KEY"]

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": "Bearer " + SUPABASE_KEY,
    "Accept": "application/json",
}


def supabase_select(
    table: str,
    columns: str,
    *,
    limit: int = BATCH_SIZE,
    offset: int = 0,
    filters: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    params: dict[str, Any] = {
        "select": columns,
        "limit": limit,
        "offset": offset,
    }

    if filters:
        params.update(filters)

    query = urllib.parse.urlencode(params)

    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/{table}?{query}",
        headers=HEADERS,
    )

    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode())


def fetch_all(
    table: str,
    columns: str,
    *,
    batch_size: int = BATCH_SIZE,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    offset = 0

    while True:
        batch = supabase_select(
            table,
            columns,
            limit=batch_size,
            offset=offset,
        )

        if not batch:
            break

        rows.extend(batch)

        if len(batch) < batch_size:
            break

        offset += batch_size

    return rows


def fetch_prospect_signals() -> list[dict[str, Any]]:
    return fetch_all(
        "prospects",
        "niche,metro,status",
    )


def fetch_buyer_signals() -> list[BuyerSignal]:
    rows = fetch_all(
        "buyers",
        (
            "id,buyer_name,niche,metro,is_active,status,"
            "daily_cap,calls_today,base_payout,per_lead_rate,priority"
        ),
    )

    buyers: list[BuyerSignal] = []

    for row in rows:
        niche = normalise(row.get("niche"))
        metro = metro_key(row.get("metro"))

        is_active = bool(row.get("is_active"))
        status = normalise(row.get("status"))

        daily_cap = int(row.get("daily_cap") or 0)
        calls_today = int(row.get("calls_today") or 0)

        remaining_capacity = max(
            daily_cap - calls_today,
            0,
        )

        raw_rate = row.get("per_lead_rate")

        if raw_rate in (None, ""):
            raw_rate = row.get("base_payout")

        buyer_rate: float | None

        try:
            buyer_rate = (
                float(raw_rate)
                if raw_rate not in (None, "")
                and float(raw_rate) > 0
                else None
            )
        except (TypeError, ValueError):
            buyer_rate = None

        try:
            priority = float(row.get("priority") or 0)
        except (TypeError, ValueError):
            priority = 0.0

        buyers.append(
            BuyerSignal(
                buyer_id=str(row.get("id") or ""),
                buyer_name=str(row.get("buyer_name") or ""),
                niche=niche,
                niche_family=niche_family(niche),
                metro=metro,
                is_active=(
                    is_active
                    and status not in {"inactive", "disabled"}
                ),
                status=status,
                daily_cap=daily_cap,
                calls_today=calls_today,
                remaining_capacity=remaining_capacity,
                buyer_rate=buyer_rate,
                priority=priority,
            )
        )

    return buyers


def load_identity_review_count() -> int:
    path = RUNTIME_ROOT / "identity" / "identity_dry_run.json"

    try:
        with path.open(encoding="utf-8") as fh:
            report = json.load(fh)
        return int(report.get("review_clusters") or 0)
    except (OSError, ValueError, TypeError):
        return 0


def fetch_identity_counts() -> dict[str, int]:
    counts: dict[str, int] = {}

    for table in (
        "business_entities",
        "prospect_entity_links",
        "business_entity_conflicts",
    ):
        query = urllib.parse.urlencode(
            {
                "select": "id",
                "limit": 1,
            }
        )

        req = urllib.request.Request(
            f"{SUPABASE_URL}/rest/v1/{table}?{query}",
            headers={
                **HEADERS,
                "Prefer": "count=exact",
            },
        )

        with urllib.request.urlopen(req, timeout=30) as response:
            content_range = response.headers.get(
                "Content-Range",
                "",
            )

            counts[table] = (
                int(
                    content_range.rsplit("/", 1)[1]
                )
                if "/"
                in content_range
                and content_range.rsplit("/", 1)[1].isdigit()
                else 0
            )

    return counts


# ---------------------------------------------------------------------------
# Buyer matching
# ---------------------------------------------------------------------------

def buyer_matches(
    buyer: BuyerSignal,
    niche: str,
    metro: str,
) -> bool:
    if not buyer.is_active:
        return False

    target_family = niche_family(niche)
    target_metro = metro_key(metro)

    niche_match = (
        buyer.niche_family == target_family
        or not buyer.niche
    )

    metro_match = (
        not buyer.metro
        or buyer.metro == target_metro
    )

    return niche_match and metro_match


def matched_buyers_for_market(
    buyers: list[BuyerSignal],
    niche: str,
    metro: str,
) -> list[BuyerSignal]:
    return [
        buyer
        for buyer in buyers
        if buyer_matches(
            buyer,
            niche,
            metro,
        )
    ]


# ---------------------------------------------------------------------------
# Opportunity scoring
# ---------------------------------------------------------------------------

def observed_rate(
    buyers: list[BuyerSignal],
) -> float | None:
    rates = [
        buyer.buyer_rate
        for buyer in buyers
        if buyer.buyer_rate is not None
        and buyer.buyer_rate > 0
    ]

    if not rates:
        return None

    return max(rates)


def build_opportunities(
    prospects: list[dict[str, Any]],
    buyers: list[BuyerSignal],
) -> list[Opportunity]:
    grouped: defaultdict[
        tuple[str, str],
        Counter,
    ] = defaultdict(Counter)

    source_niches: defaultdict[
        tuple[str, str],
        Counter,
    ] = defaultdict(Counter)

    for row in prospects:
        niche = normalise(row.get("niche"))
        metro = metro_key(row.get("metro"))

        if not niche or not metro:
            continue

        family = niche_family(niche)
        status = normalise(row.get("status")) or "unknown"

        grouped[(family, metro)][status] += 1
        source_niches[(family, metro)][niche] += 1

    # Global rate used only for relative normalisation.
    all_rates = [
        buyer.buyer_rate
        for buyer in buyers
        if buyer.is_active
        and buyer.buyer_rate is not None
        and buyer.buyer_rate > 0
    ]

    max_rate = max(all_rates, default=0.0)

    opportunities: list[Opportunity] = []

    for (family, metro), counts in grouped.items():

        total = sum(counts.values())

        new_count = counts.get("new", 0)
        bridged_count = counts.get("bridged", 0)
        activated_count = counts.get("activated", 0)

        matched_buyers = matched_buyers_for_market(
            buyers,
            family,
            metro,
        )

        variant_counts = source_niches[(family, metro)]
        dominant_variant = (
            variant_counts.most_common(1)[0][0]
            if variant_counts
            else family
        )

        buyer_count = len(matched_buyers)

        buyer_capacity = sum(
            buyer.remaining_capacity
            for buyer in matched_buyers
        )

        high_priority_buyer_count = sum(
            1
            for buyer in matched_buyers
            if buyer.priority >= 80
        )

        market_rate = observed_rate(matched_buyers)

        # Supply is useful, but deliberately saturates.
        supply_score = clamp(
            0.50 * saturate(total, 250)
            + 0.25 * saturate(new_count, 150)
            + 0.15 * saturate(bridged_count, 100)
            + 0.10 * saturate(activated_count, 50)
        )

        # Demand combines buyer count, unused capacity and buyer priority.
        capacity_signal = saturate(
            buyer_capacity,
            500,
        )

        buyer_count_signal = saturate(
            buyer_count,
            10,
        )

        priority_signal = (
            sum(
                clamp(buyer.priority / 100.0)
                for buyer in matched_buyers
            )
            / max(buyer_count, 1)
        )

        buyer_demand_score = clamp(
            0.35 * buyer_count_signal
            + 0.45 * capacity_signal
            + 0.20 * priority_signal
        )

        # Economics is based only on observed buyer rates.
        # Unknown economics stays neutral rather than becoming fake revenue.
        if market_rate is not None and max_rate > 0:
            economic_score = clamp(
                market_rate / max_rate
            )
        else:
            economic_score = 0.50

        # Fulfilment score measures how much observed buyer capacity
        # exists relative to the immediately available prospect pool.
        addressable_supply = max(
            new_count + bridged_count + activated_count,
            1,
        )

        capacity_ratio = (
            buyer_capacity / addressable_supply
        )

        fulfilment_score = clamp(
            0.20
            + 0.80 * min(
                capacity_ratio,
                1.0,
            )
        )

        # Large inactive/under-activated pools create a visibility
        # and activation opportunity, without pretending SEO demand
        # has already been measured.
        activation_gap = max(
            total - activated_count,
            0,
        )

        activation_gap_score = clamp(
            saturate(
                activation_gap,
                250,
            )
        )

        visibility_score = clamp(
            0.60 * saturate(total, 300)
            + 0.40 * activation_gap_score
        )

        supply_capacity_ratio = (
            total / max(buyer_capacity, 1)
        )

        if buyer_capacity == 0 and total > 0:
            market_balance = "demand-constrained"
        elif supply_capacity_ratio > 3:
            market_balance = "supply-heavy"
        elif supply_capacity_ratio < 0.50:
            market_balance = "demand-heavy"
        else:
            market_balance = "balanced"

        # Commercial priority:
        # demand + economics + fulfilment carry more weight than raw volume.
        priority_score = clamp(
            0.30 * buyer_demand_score
            + 0.20 * economic_score
            + 0.20 * fulfilment_score
            + 0.15 * supply_score
            + 0.10 * activation_gap_score
            + 0.05 * visibility_score
        )

        rationale: list[str] = []

        if buyer_count:
            rationale.append(
                f"{buyer_count} active buyer(s) match this niche/metro"
            )

        if buyer_capacity > 0:
            rationale.append(
                f"{buyer_capacity} units of unused buyer capacity"
            )
        else:
            rationale.append(
                "no unused matched buyer capacity"
            )

        if market_rate is not None:
            rationale.append(
                f"observed buyer rate up to {market_rate:.2f}"
            )
        else:
            rationale.append(
                "buyer economics not observed for this market"
            )

        if new_count >= 100:
            rationale.append(
                "large fresh prospect pool"
            )

        if activated_count == 0 and total >= 50:
            rationale.append(
                "large unactivated pool"
            )

        if market_balance == "supply-heavy":
            rationale.append(
                "supply exceeds currently observed buyer capacity"
            )

        if market_balance == "demand-heavy":
            rationale.append(
                "buyer capacity materially exceeds observed supply"
            )

        if market_balance == "balanced":
            rationale.append(
                "observed supply and buyer capacity are reasonably balanced"
            )

        expected_revenue_cents = 0
        expected_margin_cents = 0

        # Deliberately do not fabricate revenue/margin.
        # These become non-zero only after the commercial product/buyer
        # economics layer provides a verified sell price and cost model.

        opportunities.append(
            Opportunity(
                niche=family,
                niche_family=family,
                metro=metro,
                prospect_count=total,
                new_count=new_count,
                bridged_count=bridged_count,
                activated_count=activated_count,
                buyer_count=buyer_count,
                buyer_capacity=buyer_capacity,
                high_priority_buyer_count=high_priority_buyer_count,
                observed_buyer_rate=market_rate,
                supply_score=round(supply_score, 4),
                buyer_demand_score=round(buyer_demand_score, 4),
                economic_score=round(economic_score, 4),
                fulfilment_score=round(fulfilment_score, 4),
                visibility_score=round(visibility_score, 4),
                activation_gap_score=round(
                    activation_gap_score,
                    4,
                ),
                market_balance=market_balance,
                priority_score=round(
                    priority_score,
                    4,
                ),
                expected_revenue_cents=expected_revenue_cents,
                expected_margin_cents=expected_margin_cents,
                rationale=rationale,
            )
        )

    opportunities.sort(
        key=lambda item: item.priority_score,
        reverse=True,
    )

    return opportunities


# ---------------------------------------------------------------------------
# Job planning
# ---------------------------------------------------------------------------

def build_gtm_jobs(
    opportunities: list[Opportunity],
) -> list[GTMJob]:
    jobs: list[GTMJob] = []

    for opportunity in opportunities[:50]:
        target = {
            "niche": opportunity.niche,
            "niche_family": opportunity.niche_family,
            "metro": opportunity.metro,
        }

        base_payload = {
            "niche": opportunity.niche,
            "niche_family": opportunity.niche_family,
            "metro": opportunity.metro,
            "prospect_count": opportunity.prospect_count,
            "new_count": opportunity.new_count,
            "bridged_count": opportunity.bridged_count,
            "activated_count": opportunity.activated_count,
            "buyer_count": opportunity.buyer_count,
            "buyer_capacity": opportunity.buyer_capacity,
            "market_balance": opportunity.market_balance,
            "scores": {
                "supply": opportunity.supply_score,
                "buyer_demand": opportunity.buyer_demand_score,
                "economic": opportunity.economic_score,
                "fulfilment": opportunity.fulfilment_score,
                "visibility": opportunity.visibility_score,
                "activation_gap": opportunity.activation_gap_score,
            },
            "observed_buyer_rate": opportunity.observed_buyer_rate,
        }

        # Supply generation only gets high priority when fulfilment
        # capacity exists.
        if opportunity.buyer_capacity > 0:
            jobs.append(
                GTMJob(
                    job_type="lead_generation",
                    priority=round(
                        opportunity.priority_score,
                        4,
                    ),
                    target=target,
                    status="planned",
                    worker_adapter="market_sweep_adapter",
                    requires_approval=True,
                    payload={
                        **base_payload,
                        "execution_mode": "bounded",
                        "source_policy": "approved_sources_only",
                        "capacity_gate": True,
                    },
                )
            )

        # Demand generation gets prioritised when supply is already
        # materially ahead of buyer capacity.
        if (
            opportunity.market_balance == "supply-heavy"
            or opportunity.buyer_count == 0
        ):
            jobs.append(
                GTMJob(
                    job_type="buyer_acquisition",
                    priority=round(
                        opportunity.priority_score * 0.98,
                        4,
                    ),
                    target=target,
                    status="planned",
                    worker_adapter="buyer_gtm_adapter",
                    requires_approval=True,
                    payload={
                        **base_payload,
                        "reason": (
                            "insufficient observed buyer demand/capacity"
                        ),
                    },
                )
            )

        jobs.append(
            GTMJob(
                job_type="qualification",
                priority=round(
                    opportunity.priority_score * 0.94,
                    4,
                ),
                target=target,
                status="planned",
                worker_adapter="omega_qualification_adapter",
                requires_approval=False,
                payload={
                    **base_payload,
                    "strategy": (
                        "identity_aware_qualification"
                    ),
                },
            )
        )

        # Visibility is first-class, but the trigger is a market with
        # meaningful supply / activation opportunity rather than volume alone.
        if opportunity.visibility_score >= 0.55:
            for job_type, adapter, multiplier in (
                ("visibility_seo", "seo_adapter", 0.78),
                ("visibility_aeo", "aeo_adapter", 0.76),
                ("visibility_geo", "geo_adapter", 0.74),
            ):
                jobs.append(
                    GTMJob(
                        job_type=job_type,
                        priority=round(
                            opportunity.priority_score
                            * multiplier,
                            4,
                        ),
                        target=target,
                        status="planned",
                        worker_adapter=adapter,
                        requires_approval=True,
                        payload={
                            **base_payload,
                            "channel": job_type.removeprefix(
                                "visibility_"
                            ),
                        },
                    )
                )

        # MRR / product motion is strongest where there is repeatable
        # buyer demand and meaningful capacity.
        if (
            opportunity.buyer_count >= 2
            and opportunity.buyer_capacity >= 50
        ):
            jobs.append(
                GTMJob(
                    job_type="product_offer",
                    priority=round(
                        opportunity.priority_score * 0.90,
                        4,
                    ),
                    target=target,
                    status="planned",
                    worker_adapter="mrr_product_adapter",
                    requires_approval=True,
                    payload={
                        **base_payload,
                        "product_family": "lead_supply",
                        "recurring": True,
                        "product_strategy": (
                            "lane_or_managed_supply"
                        ),
                    },
                )
            )

        jobs.append(
            GTMJob(
                job_type="fulfilment_capacity_check",
                priority=round(
                    opportunity.priority_score * 0.89,
                    4,
                ),
                target=target,
                status="planned",
                worker_adapter="fulfilment_capacity_adapter",
                requires_approval=False,
                payload={
                    **base_payload,
                    "gate": "capacity_before_generation",
                },
            )
        )

        jobs.append(
            GTMJob(
                job_type="experiment",
                priority=round(
                    opportunity.priority_score * 0.70,
                    4,
                ),
                target=target,
                status="planned",
                worker_adapter="experiment_adapter",
                requires_approval=True,
                payload={
                    **base_payload,
                    "experiment": (
                        "channel_offer_angle"
                    ),
                    "variants": 3,
                    "minimum_sample_policy": (
                        "bounded_before_scale"
                    ),
                },
            )
        )

    jobs.sort(
        key=lambda item: item.priority,
        reverse=True,
    )

    return jobs


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------

def build_plan() -> dict[str, Any]:
    prospects = fetch_prospect_signals()
    buyers = fetch_buyer_signals()
    identities = fetch_identity_counts()

    opportunities = build_opportunities(
        prospects,
        buyers,
    )

    jobs = build_gtm_jobs(
        opportunities,
    )

    status_counts = Counter(
        normalise(row.get("status")) or "unknown"
        for row in prospects
    )

    niche_counts = Counter(
        niche_family(row.get("niche"))
        for row in prospects
        if normalise(row.get("niche"))
    )

    active_buyers = [
        buyer
        for buyer in buyers
        if buyer.is_active
    ]

    inactive_buyers = len(buyers) - len(active_buyers)

    remaining_capacity = sum(
        buyer.remaining_capacity
        for buyer in active_buyers
    )

    daily_cap = sum(
        buyer.daily_cap
        for buyer in active_buyers
    )

    calls_today = sum(
        buyer.calls_today
        for buyer in active_buyers
    )

    return {
        "schema_version": "gtm_engine.v2",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "plan_only",

        "commercial_objective": (
            "expected_long_term_contribution_margin"
        ),

        "source": {
            "supabase": SUPABASE_URL,
            "prospects": len(prospects),
            "buyers": len(buyers),
            "active_buyers": len(active_buyers),
            "inactive_buyers": inactive_buyers,
            "buyer_daily_capacity": daily_cap,
            "buyer_calls_today": calls_today,
            "buyer_remaining_capacity": remaining_capacity,
            "identity": identities,
        },

        "market": {
            "opportunity_count": len(opportunities),
            "top_opportunities": [
                asdict(item)
                for item in opportunities[:50]
            ],
            "top_niches": niche_counts.most_common(25),
            "balance_counts": dict(
                Counter(
                    opportunity.market_balance
                    for opportunity in opportunities
                )
            ),
        },

        "funnel": {
            "statuses": dict(status_counts),
        },

        "jobs": {
            "total": len(jobs),
            "by_type": dict(
                Counter(job.job_type for job in jobs)
            ),
            "items": [
                asdict(job)
                for job in jobs
            ],
        },

        "execution": {
            "writes_to_supabase": 0,
            "prospects_modified": 0,
            "outreach_sent": 0,
            "campaigns_launched": 0,
            "invoices_created": 0,
            "fulfilments_triggered": 0,
        },
    }


def main() -> None:
    plan = build_plan()

    REPORT_PATH.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_PATH.write_text(
        json.dumps(
            plan,
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )

    balance_counts = plan["market"]["balance_counts"]

    print("GTM ENGINE: PLAN ONLY / v2")
    print(f"PROSPECTS: {plan['source']['prospects']}")
    print(f"BUYERS: {plan['source']['buyers']}")
    print(f"ACTIVE BUYERS: {plan['source']['active_buyers']}")
    print(f"INACTIVE BUYERS: {plan['source']['inactive_buyers']}")
    print(
        "BUYER REMAINING CAPACITY: "
        f"{plan['source']['buyer_remaining_capacity']}"
    )
    print(
        "CANONICAL ENTITIES: "
        f"{plan['source']['identity']['business_entities']}"
    )
    print(
        "IDENTITY LINKS: "
        f"{plan['source']['identity']['prospect_entity_links']}"
    )
    print(
        "PROMOTED IDENTITY CONFLICTS: "
        f"{plan['source']['identity']['business_entity_conflicts']}"
    )
    print(
        "HELD REVIEW CLUSTERS: "
        f"{load_identity_review_count()}"
    )
    print(
        "OPPORTUNITIES: "
        f"{plan['market']['opportunity_count']}"
    )
    print(
        "BALANCE: "
        + ", ".join(
            f"{key}={value}"
            for key, value in balance_counts.items()
        )
    )
    print(
        "JOBS PLANNED: "
        f"{plan['jobs']['total']}"
    )
    print(
        "LEAD GENERATION JOBS: "
        f"{plan['jobs']['by_type'].get('lead_generation', 0)}"
    )
    print(
        "BUYER GTM JOBS: "
        f"{plan['jobs']['by_type'].get('buyer_acquisition', 0)}"
    )
    print(
        "MRR PRODUCT JOBS: "
        f"{plan['jobs']['by_type'].get('product_offer', 0)}"
    )
    print(
        "SEO/AEO/GEO JOBS: "
        f"{sum(plan['jobs']['by_type'].get(x, 0) for x in ('visibility_seo', 'visibility_aeo', 'visibility_geo'))}"
    )
    print(
        "FULFILMENT CHECKS: "
        f"{plan['jobs']['by_type'].get('fulfilment_capacity_check', 0)}"
    )
    print("SUPABASE WRITES: 0")
    print(f"REPORT: {REPORT_PATH}")


if __name__ == "__main__":
    main()
