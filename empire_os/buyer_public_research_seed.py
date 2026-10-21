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
    # 2026-10-10 publisher-first benchmark discoveries. Source hints only,
    # never published rates, active buyer capacity or approval evidence.
    ("https://www.elocal.com/affiliate-contact/", "public:publisher_review:elocal.com"),
    ("https://www.polyares.com/pay-per-call-affiliate-program", "public:publisher_review:polyares.com"),
    ("https://homevantaleadgroup.com/for-affiliates", "public:publisher_review:homevantaleadgroup.com"),
    ("https://joinglobalwiz.com/affiliates", "public:publisher_review:joinglobalwiz.com"),
)


# Verified first-party public programme pages observed 15 October 2026.
# PUBLIC DISCOVERY CANDIDATES ONLY: not Empire AI buyer contracts, payouts,
# traffic permission, partner approval or category/postcode acceptance.
# Market labels describe *programme jurisdiction*, not founder location.
_MULTIMARKET_REVIEW_SEEDS = (
    ("https://modernize.com/affiliates", "USA", ("solar", "roofing", "hvac")),
    ("https://www.angi.com/landing/affiliatepartners", "USA", ("home_services",)),
    ("https://homeservicesleadgroup.com/affiliates", "USA", ("solar", "roofing", "hvac")),
    ("https://leads2trade.co.uk/about/affiliates/", "UK", ("solar", "home_services")),
    ("https://yoursolarquotes.com.au/solar-affiliate-program/", "AU", ("solar",)),
    ("https://www.australiansolarquotes.com.au/about-us/referral-partners/", "AU", ("solar",)),
    ("https://www.liveleads.ca/", "CA", ("home_services", "insurance", "legal")),
    ("https://centfix.ca/affiliates", "CA", ("home_services",)),
    ("https://xolar.ca/referral-program/", "CA", ("solar",)),
    # 2026-10-21 first-party publisher pages; identity, terms and buyer
    # capacity stay unverified pending the existing Scout evidence gates.
    ("https://www.ringpartner.com/affiliate-program/", "USA", ("home_services", "legal", "insurance")),
    ("https://leadsbycall.com/faq.html", "USA", ("home_services",)),
    ("https://leadspedio.com/", "USA", ("home_services", "legal", "insurance")),
    ("https://www.ringondemand.com/partners", "USA", ("legal", "insurance")),
    # Explicit first-party call/click/lead publisher marketplaces: these
    # programme pages are research evidence, never buyer or payout authority.
    ("https://visiqua.com/calls/", "USA", ("home_services", "insurance")),
    # 2026-10-21 existing first-party publisher/supplier programmes:
    # calls across multiple verticals, consented lead resale, UK insurance
    # cost-per-lead/whitelabel and AU/US/UK cross-market offers.
    # These entries are RESEARCH ONLY, with zero attribution or send authority.
    ("https://www.lucent.media/publishers", "USA", ("home_services", "legal", "insurance", "solar")),
    ("https://getmapleleads.com/suppliers", "USA", ("home_services", "insurance", "solar")),
    ("https://www.mymoneycomparison.com/become-an-affiliate/", "UK", ("insurance",)),
    ("https://traffic2lead.com/publishers/", "AU", ("solar", "insurance", "education")),
    # Publisher-only research for US home services, dental, legal, insurance
    # and UK debt/claims programmes. Broad catalogue listings are NOT
    # verified offers, publisher approvals or payable capacity.
    ("https://www.bfount.com/affiliate.php", "USA", ("home_services", "legal", "insurance", "solar")),
    ("https://www.callx.com/publishers", "USA", ("home_services", "legal", "insurance")),
)
MARKETS = frozenset({"UK", "USA", "AU", "CA"})
_MARKET_PUBLISHER_QUERIES = (
    # Existing four tested US home-service queries preserved unchanged below.
    ('"solar" "pay per lead" "publisher" "United States"', "USA"),
    ('"HVAC" "publisher" "lead buyer" "United States"', "USA"),
    ('"solar panels" "affiliate" "lead" "United Kingdom"', "UK"),
    ('"home improvements" "affiliate programme" "publisher" "UK"', "UK"),
    ('"solar" "affiliate program" "Australia"', "AU"),
    ('"roofing" "pay per lead" "Australia"', "AU"),
    ('"solar" "lead partner" "Canada"', "CA"),
    ('"home services" "affiliate" "publisher" "Canada"', "CA"),
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


# Tested publisher-specific searches returned more contactable demand channels
# than broad lead-buyer keyword matching. Rotate two queries on the existing
# 30-minute scout; no extra provider, timer, retry loop or external send.
_PUBLISHER_DISCOVERY_QUERIES = (
    '"roofing" "pay per call" "publisher" "SEO"',
    '"home services" "publisher" "organic" "apply"',
    '"roofing" "publisher" "qualification" "tracking"',
    '"home services" "calls" "publisher application" "SEO"',
    *(query for query, market in _MARKET_PUBLISHER_QUERIES),
)


def _publisher_queries(*, observed_at: datetime, max_queries: int) -> list[dict[str, Any]]:
    count = min(max(0, int(max_queries)), 2)
    slot = int(observed_at.timestamp() // 1800)
    # Exactly two searches per existing scout run. Cycle across country
    # pairs; widening markets does NOT increase provider calls or timers.
    start = (slot % (len(_PUBLISHER_DISCOVERY_QUERIES) // 2)) * 2
    def market_at(index: int) -> str:
        if index < 4:
            return "USA"
        return _MARKET_PUBLISHER_QUERIES[index - 4][1]
    return [{
        "query": _PUBLISHER_DISCOVERY_QUERIES[start + i],
        "buyer_pool": "direct_demand_buyers",
        "corridor_key": None,
        "product_code": None,
        "priority_score": 90,
        "source": "tested_publisher_first_search",
        "target_market": market_at(start + i),
    } for i in range(count)]


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
    known_registry_domains: set[str] | None = None,
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
        target_market: str | None = None,
        target_verticals: tuple[str, ...] = (),
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
            "target_markets": [],
            "target_verticals": [],
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
        if target_market in MARKETS and target_market not in row["target_markets"]:
            row["target_markets"].append(target_market)
        for vertical in target_verticals:
            if (isinstance(vertical, str) and vertical in {
                "solar", "roofing", "hvac", "home_services", "legal", "insurance"
            } and vertical not in row["target_verticals"]):
                row["target_verticals"].append(vertical)

    for website, source_ref in _BASELINE_SEEDS:
        add_seed(website, source_ref=source_ref)
    for website, market, verticals in _MULTIMARKET_REVIEW_SEEDS:
        host = _host(website)
        add_seed(
            website,
            source_ref=f"public:multimarket_review:{market}:{host}",
            target_market=market,
            target_verticals=verticals,
        )

    safe_max = max(1, min(int(max_queries), 60))
    publisher = _publisher_queries(observed_at=now, max_queries=safe_max)
    remaining_after_publisher = max(0, safe_max - len(publisher))
    dynamic_budget = max(1, min(20, remaining_after_publisher // 3))
    dynamic = (_dynamic_queries(plan, max_queries=dynamic_budget)
               if remaining_after_publisher else [])
    remaining = max(0, remaining_after_publisher - len(dynamic))
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
    for row in [*publisher, *dynamic, *volume]:
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
                target_market=query_row.get("target_market"),
                buyer_pool=str(
                    query_row.get("buyer_pool")
                    or "direct_demand_buyers"
                ),
            )

    seeds = sorted(by_domain.values(), key=lambda row: row["domain"])
    observed_from_queries = {
        row["domain"] for row in seeds if row["source_queries"]
    }
    query_result_status = (
        "NO_SEARCH_QUERIES" if not query_texts
        else "SEARCH_BACKEND_EXCEPTION" if errors
        else "FRESH_DOMAIN_RESULTS_OBSERVED" if observed_from_queries
        else "NO_FRESH_DOMAIN_RESULTS_PROVIDER_HEALTH_UNVERIFIED"
    )
    return {
        "schema_version": "empire.buyer_public_research_seeds.v1",
        "mode": "OBSERVE",
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "query_count": len(queries),
        "query_strategy_counts": {
            "publisher_first": sum(row.get("source") == "tested_publisher_first_search" for row in queries),
            "dynamic_buyer_target": sum(row.get("buyer_pool") == "direct_demand_buyers" and row.get("source") != "tested_publisher_first_search" for row in queries),
            "local_volume": sum(row.get("source") == "rotating_volume_wave" for row in queries),
        },
        "publisher_first_queries_are_discovery_hints_only": True,
        "multimarket_first_party_seed_count": len(_MULTIMARKET_REVIEW_SEEDS),
        "searches_per_existing_cycle_unchanged": True,
        "markets_targeted": list(sorted(MARKETS)),
        "fresh_search_domain_count": len(observed_from_queries),
        "fresh_search_result_status": query_result_status,
        "search_provider_health_independently_verified": False,
        "source_method_comparison": compare_seed_methods(
            seeds, queries, known_registry_domains,
        ),
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

    kwargs.setdefault('known_registry_domains', load_known_registry_domains(root))
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


def compare_seed_methods(
    seeds: list[dict[str, Any]],
    queries: list[dict[str, Any]],
    known_domains: set[str] | None,
) -> dict[str, Any]:
    """Operational search yield comparison, never commercial-outcome learning.

    New domain != verified company, active buyer, approval or revenue.
    """
    known = None if known_domains is None else {
        _host(d) for d in known_domains if _host(d)
    }
    query_method = {
        x["query"]: (
            "publisher_first" if x.get("source") == "tested_publisher_first_search"
            else "local_volume" if x.get("source") == "rotating_volume_wave"
            else "dynamic_buyer"
        ) for x in queries
    }
    pools: dict[str, set[str]] = {
        method: set() for method in query_method.values()
    }
    for row in seeds:
        for query in row.get("source_queries") or []:
            kind = query_method.get(query)
            if kind is not None:
                pools.setdefault(kind, set()).add(row["domain"])
    reviewed = {
        row["domain"] for row in seeds
        if any(
            tag.startswith("public:publisher_review:")
            for tag in row.get("source_refs") or []
        )
    }
    return {
        "status": ("REGISTRY_COMPARISON" if known is not None
                   else "REGISTRY_BASELINE_UNAVAILABLE"),
        "known_registry_domain_count": len(known) if known is not None else None,
        "publisher_programme_page_research_seed_count": len(reviewed),
        "publisher_programme_page_novel_domains": (
            sorted(reviewed-known) if known is not None else None
        ),
        "query_methods": {
            method: {
                "discovered_domains": len(domains),
                "not_in_registry": (
                    len(domains-known) if known is not None else None
                ),
                "metric_scope": "novelty_not_buyer_qualification",
                "verified_buyer_approvals": 0,
                "recognized_revenue": None,
            }
            for method, domains in sorted(pools.items())
        },
        "outbound_authorized": False,
        "execution_authority": "none",
    }


def load_known_registry_domains(root: Path) -> set[str] | None:
    """Missing baseline must not be treated as all-new buyers."""
    file = root / "runtime/buyer_network_intelligence/commercial_relationship_registry_latest.json"
    try:
        if not file.is_file() or file.is_symlink() or file.stat().st_size > 2_500_000:
            return None
        data = json.loads(file.read_text(encoding="utf-8"))
        rows = data.get("relationships")
        if not isinstance(rows, list):
            return None
        return {domain for row in rows if isinstance(row, dict)
                for domain in row.get("identity_domains", []) if isinstance(domain, str)}
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def publisher_review_page_path(domain: str) -> str | None:
    """Bounded same-host official entry point for first-party site verification."""
    host = _host(domain)
    pages = [
        *( (url, source) for url, source in _BASELINE_SEEDS),
        *( (url, f"public:multimarket_review:{market}:{_host(url)}")
            for url, market, _verticals in _MULTIMARKET_REVIEW_SEEDS),
    ]
    for page_url, source in pages:
        if not (
            source == "public:publisher_review:" + host
            or any(source == f"public:multimarket_review:{market}:{host}"
                   for market in MARKETS)
        ):
            continue
        parsed = urlparse(page_url)
        path = parsed.path.rstrip("/")
        if parsed.scheme != "https" or _host(page_url) != host:
            return None
        segments = path.strip("/").split("/")
        if path.startswith("/") and all(
            segment.replace("-", "").isalnum() for segment in segments
        ):
            return path
    return None


def publisher_review_page_paths(domain: str) -> tuple[str, ...]:
    """A bounded, independently reviewed first-party PPC/PPL page pair."""
    # Explicitly reviewed legacy .php affiliate endpoint. Do not relax the
    # general domain/path parser or follow third-party publisher redirects.
    if _host(domain) == "bfount.com":
        return ("/affiliate.php",)
    primary = publisher_review_page_path(domain)
    if primary is None:
        return ()
    # Exact Polyares first-party PPL programme page, not a general URL crawl.
    if _host(domain) == "polyares.com":
        return (primary, "/pay-per-lead-affiliate-program")
    if _host(domain) == "visiqua.com":
        return (primary, "/clicks", "/leads")
    return (primary,)
