"""Bounded Buyer Scout for Phase 4 demand acquisition.

Consumes the Buyer Acquisition Team plan and executes a small number of
self-hosted Search Fabric queries. Results are internal research observations
only. They do not become buyers, seats, verified contacts or outbound targets
without the existing downstream evidence gates.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse

from empire_os.buyer_acquisition_team import direct_buyer_profile


OUTPUT = Path("runtime/buyer_acquisition/scout_latest.json")

SearchFn = Callable[..., Mapping[str, Any]]


BAD_HOSTS = {
    "google.com",
    "bing.com",
    "duckduckgo.com",
    "facebook.com",
    "linkedin.com",
    "youtube.com",
    "reddit.com",
    "wikipedia.org",
    "yelp.com",
}


def _host(value: Any) -> str:
    try:
        host = urlparse(str(value or "").strip()).netloc.lower()
    except Exception:
        return ""
    if host.startswith("www."):
        host = host[4:]
    return host


def _flatten_queries(
    plan: Mapping[str, Any],
    *,
    max_queries: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for target in plan.get("priority_targets") or []:
        if not isinstance(target, Mapping):
            continue
        query_groups = target.get("research_queries")
        if not isinstance(query_groups, Mapping):
            continue
        for pool, queries in query_groups.items():
            if not isinstance(queries, list):
                continue
            for query in queries:
                if str(query or "").strip():
                    rows.append({
                        "source": "corridor_demand",
                        "pool": str(pool),
                        "query": str(query).strip(),
                        "corridor_key": target.get("corridor_key"),
                        "product_code": None,
                        "priority_score": int(
                            target.get("priority_score") or 0
                        ),
                    })

    for target in plan.get("product_priority_targets") or []:
        if not isinstance(target, Mapping):
            continue
        query_groups = target.get("research_queries")
        if not isinstance(query_groups, Mapping):
            continue
        for pool, queries in query_groups.items():
            if not isinstance(queries, list):
                continue
            for query in queries:
                if str(query or "").strip():
                    rows.append({
                        "source": "product_demand",
                        "pool": str(pool),
                        "query": str(query).strip(),
                        "corridor_key": None,
                        "product_code": target.get("product_code"),
                        "priority_score": int(
                            target.get("priority_score") or 0
                        ),
                    })

    rows.sort(
        key=lambda row: (
            -int(row["priority_score"]),
            str(row["source"]),
            str(row["pool"]),
            str(row["query"]),
        )
    )

    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        query = str(row["query"])
        if query in seen:
            continue
        seen.add(query)
        selected.append(row)
        if len(selected) >= max(1, int(max_queries)):
            break
    return selected


def run_buyer_scout(
    plan: Mapping[str, Any],
    *,
    search_fn: SearchFn,
    max_queries: int = 12,
    results_per_query: int = 5,
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    queries = _flatten_queries(plan, max_queries=max_queries)
    observations: list[dict[str, Any]] = []
    errors: list[str] = []
    seen_domains: set[str] = set()

    for query_row in queries:
        query = str(query_row["query"])
        try:
            response = search_fn(
                query,
                num=max(1, min(int(results_per_query), 10)),
            )
        except Exception as exc:
            errors.append(
                f"{query}:{type(exc).__name__}:{str(exc)[:160]}"
            )
            continue

        engine = None
        parameters = response.get("searchParameters")
        if isinstance(parameters, Mapping):
            engine = parameters.get("engine")

        for result in response.get("organic") or []:
            if not isinstance(result, Mapping):
                continue
            link = str(result.get("link") or "").strip()
            host = _host(link)
            if not host or host in BAD_HOSTS or host in seen_domains:
                continue
            seen_domains.add(host)

            title = str(result.get("title") or "").strip()
            snippet = str(result.get("snippet") or "").strip()
            profile = direct_buyer_profile({
                "business_name": title,
                "website": link,
                "description": snippet,
                "category": query_row["pool"],
            })

            observations.append({
                "domain": host,
                "website": link,
                "business_name_observed": title or None,
                "snippet": snippet or None,
                "query": query,
                "query_source": query_row["source"],
                "target_pool": query_row["pool"],
                "corridor_key": query_row.get("corridor_key"),
                "product_code": query_row.get("product_code"),
                "search_engine": engine,
                "buyer_profile": profile,
                "candidate_state": "RESEARCH_OBSERVATION",
                "identity_verified": False,
                "contact_verified": False,
                "commercial_terms_verified": False,
                "buyer_seat_ready": False,
                "outbound_ready": False,
            })

    now = observed_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        raise ValueError("observed_at must include timezone")

    return {
        "schema_version": "empire.buyer_scout.v1",
        "mode": "INTERNAL_RESEARCH",
        "observed_at": now.astimezone(timezone.utc).isoformat(),
        "query_count": len(queries),
        "observation_count": len(observations),
        "error_count": len(errors),
        "queries": queries,
        "observations": observations,
        "errors": errors,
        "automatic_external_execution": False,
        "outbound_sent": False,
        "commercial_authority": "none",
        "execution_authority": "none",
    }


def refresh_buyer_scout(
    repo_root: str | Path,
    *,
    search_fn: SearchFn,
    max_queries: int = 12,
    results_per_query: int = 5,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    plan_path = root / "runtime/buyer_acquisition/latest.json"
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        plan = {}
    if not isinstance(plan, dict):
        plan = {}

    payload = run_buyer_scout(
        plan,
        search_fn=search_fn,
        max_queries=max_queries,
        results_per_query=results_per_query,
    )
    path = root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
