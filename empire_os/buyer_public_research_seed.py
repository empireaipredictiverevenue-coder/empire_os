"""Continuous public-research seeds for Buyer Acquisition Scout.

Research seeds are discovery hints only. Every domain still passes through the
existing first-party site probe, reconciliation and review gates before it can
become a buyer candidate. This module grants no outbound or commercial authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from empire_os.search_fabric.search import search_domains_parallel


OUTPUT = Path("runtime/buyer_acquisition/public_research_seeds.json")
SearchFn = Callable[[list[str], int], Mapping[str, list[str]]]

_BAD_HOSTS = {
    "google.com", "bing.com", "duckduckgo.com", "facebook.com",
    "linkedin.com", "youtube.com", "reddit.com", "wikipedia.org",
    "mthink.com", "search.google",
}

_VOLUME_VERTICALS = (
    ("roofing contractor", "roofing"),
    ("hvac contractor", "hvac"),
    ("water damage restoration", "restoration"),
    ("plumber", "plumbing"),
    ("solar installer", "solar"),
    ("general contractor", "general_contractor"),
    ("personal injury lawyer", "personal_injury"),
    ("workers compensation lawyer", "workers_comp"),
    ("mass tort law firm", "mass_tort"),
)

_VOLUME_METROS = (
    "Dallas TX", "Houston TX", "San Antonio TX", "Austin TX",
    "Phoenix AZ", "Tampa FL", "Orlando FL", "Miami FL",
    "Atlanta GA", "Charlotte NC", "Nashville TN", "Denver CO",
    "Kansas City MO", "Oklahoma City OK", "Chicago IL",
    "Philadelphia PA", "New York NY", "Los Angeles CA",
)

# First-party domains observed publicly on 2026-10-02. They are only starting
# points for repeat first-party verification; no price, capacity, terms or
# contact claim is trusted from this list.
_BASELINE_SEEDS = (
    ("https://www.leadsmartinc.com/", "public:first_party:leadsmartinc.com"),
    ("https://partnerleadsnetwork.com/", "public:first_party:partnerleadsnetwork.com"),
    ("https://callflowmarket.com/verticals/home-services", "public:first_party:callflowmarket.com"),
    ("https://px.com/industries/home-services", "public:first_party:px.com"),
    ("https://bh-network.com/", "public:first_party:bh-network.com"),
    ("https://www.digitalmastermedia.com/", "public:first_party:digitalmastermedia.com"),
    ("https://positioncalls.com/", "public:first_party:positioncalls.com"),
)


def _host(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    parsed = urlparse(text if "://" in text else "https://" + text)
    host = parsed.netloc.split("@")[-1].split(":")[0]
    if host.startswith("www."):
        host = host[4:]
    return host


def _dynamic_queries(
    plan: Mapping[str, Any],
    *,
    max_queries: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in plan.get("priority_targets") or []:
        if not isinstance(raw, Mapping):
            continue
        if raw.get("buyer_hunt_required") is not True:
            continue
        niche = str(raw.get("niche_family") or "").strip()
        if not niche:
            continue
        corridor = str(raw.get("corridor_key") or "").strip() or None
        product = str(raw.get("product_code") or "").strip() or None
        priority = int(raw.get("priority_score") or 0)
        for query in (
            f'"{niche}" "publisher" "pay per call"',
            f'"{niche}" "lead buyer" "publishers"',
            f'"{niche}" "buy leads" "affiliate network"',
        ):
            rows.append({
                "query": query,
                "buyer_pool": "direct_demand_buyers",
                "corridor_key": corridor,
                "product_code": product,
                "priority_score": priority,
            })

    rows.sort(key=lambda row: (-row["priority_score"], row["query"]))
    dedup: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        query = row["query"]
        if query in seen:
            continue
        seen.add(query)
        dedup.append(row)
        if len(dedup) >= max(1, min(int(max_queries), 30)):
            break
    return dedup


def _volume_queries(
    *,
    observed_at: datetime,
    max_queries: int,
) -> list[dict[str, Any]]:
    combinations = [
        (vertical, niche, metro)
        for metro in _VOLUME_METROS
        for vertical, niche in _VOLUME_VERTICALS
    ]
    if not combinations:
        return []
    count = max(0, min(int(max_queries), len(combinations)))
    if count == 0:
        return []

    slot = int(observed_at.timestamp() // 1800)
    start = (slot * 37) % len(combinations)
    rows: list[dict[str, Any]] = []
    for offset in range(count):
        vertical, niche, metro = combinations[(start + offset) % len(combinations)]
        rows.append({
            "query": f'"{vertical}" "{metro}"',
            "buyer_pool": "local_and_smb_buyers",
            "corridor_key": None,
            "product_code": "managed_service",
            "priority_score": 80,
            "niche_family": niche,
            "metro": metro,
            "source": "rotating_volume_wave",
        })
    return rows


def build_public_research_seeds(
    plan: Mapping[str, Any],
    *,
    search_fn: SearchFn = search_domains_parallel,
    max_queries: int = 12,
    results_per_query: int = 5,
    observed_at: datetime | None = None,
    include_volume: bool = True,
) -> dict[str, Any]:
    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("observed_at must include timezone")

    by_domain: dict[str, dict[str, Any]] = {}

    def add_seed(
        website: str,
        *,
        source_ref: str,
        source_query: str | None = None,
        corridor_key: str | None = None,
        product_code: str | None = None,
        buyer_pool: str = "direct_demand_buyers",
    ) -> None:
        host = _host(website)
        if not host or host in _BAD_HOSTS:
            return
        row = by_domain.setdefault(host, {
            "domain": host,
            "website": website,
            "source_refs": [],
            "source_queries": [],
            "target_buyer_pools": [],
            "target_corridor_keys": [],
            "target_product_codes": [],
            "truth_class": "OBSERVED_PUBLIC_RESEARCH",
            "identity_verified": False,
            "commercial_terms_verified": False,
            "buyer_capacity_verified": False,
            "buyer_price_verified": False,
            "outreach_authorized": False,
            "execution_authority": "none",
        })
        buyer_pool = str(
            buyer_pool or "direct_demand_buyers"
        ).strip() or "direct_demand_buyers"
        if buyer_pool not in row["target_buyer_pools"]:
            row["target_buyer_pools"].append(buyer_pool)
        if source_ref and source_ref not in row["source_refs"]:
            row["source_refs"].append(source_ref)
        if source_query and source_query not in row["source_queries"]:
            row["source_queries"].append(source_query)
        if corridor_key and corridor_key not in row["target_corridor_keys"]:
            row["target_corridor_keys"].append(corridor_key)
        if product_code and product_code not in row["target_product_codes"]:
            row["target_product_codes"].append(product_code)

    for website, source_ref in _BASELINE_SEEDS:
        add_seed(website, source_ref=source_ref)

    safe_max = max(1, min(int(max_queries), 60))
    dynamic_budget = max(1, min(20, safe_max // 3))
    dynamic = _dynamic_queries(plan, max_queries=dynamic_budget)
    remaining = max(0, safe_max - len(dynamic))
    volume = (
        _volume_queries(
            observed_at=now,
            max_queries=remaining,
        )
        if include_volume
        else []
    )
    queries: list[dict[str, Any]] = []
    seen_queries: set[str] = set()
    for row in [*dynamic, *volume]:
        query = str(row.get("query") or "").strip()
        if not query or query in seen_queries:
            continue
        seen_queries.add(query)
        queries.append(row)
        if len(queries) >= safe_max:
            break
    query_texts = [row["query"] for row in queries]
    errors: list[str] = []
    try:
        domain_map = (
            search_fn(
                query_texts,
                num=max(1, min(int(results_per_query), 10)),
            )
            if query_texts
            else {}
        )
    except Exception as exc:
        domain_map = {}
        errors.append(
            f"search_fabric:{type(exc).__name__}:{str(exc)[:160]}"
        )

    for query_row in queries:
        query = query_row["query"]
        for domain in domain_map.get(query, []) or []:
            host = _host(domain)
            if not host or host in _BAD_HOSTS:
                continue
            add_seed(
                "https://" + host,
                source_ref="public:search_fabric:" + query,
                source_query=query,
                corridor_key=query_row.get("corridor_key"),
                product_code=query_row.get("product_code"),
                buyer_pool=str(
                    query_row.get("buyer_pool")
                    or "direct_demand_buyers"
                ),
            )

    seeds = sorted(by_domain.values(), key=lambda row: row["domain"])
    return {
        "schema_version": "empire.buyer_public_research_seeds.v1",
        "mode": "OBSERVE",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "query_count": len(queries),
        "seed_count": len(seeds),
        "error_count": len(errors),
        "errors": errors,
        "seeds": seeds,
        "database_write_performed": False,
        "outbound_sent": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }


def refresh_public_research_seeds(
    repo_root: str | Path,
    **kwargs: Any,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    try:
        plan = json.loads(
            (root / "runtime/buyer_acquisition/latest.json").read_text(
                encoding="utf-8"
            )
        )
    except (OSError, json.JSONDecodeError):
        plan = {}
    if not isinstance(plan, dict):
        plan = {}

    payload = build_public_research_seeds(plan, **kwargs)
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
