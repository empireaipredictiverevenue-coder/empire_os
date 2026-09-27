"""Observed market search-presence intelligence for EmpireOS.

Runs a bounded set of public market queries through Search Fabric and measures
which canonical market-company domains are actually observed in result sets.
The metric is search presence, not market share, demand, buyer intent, or
commercial intent.
"""
from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from empire_os.competitor_audience_sweep import (
    load_resolved_market_entities,
)
from empire_os.intelligence_materializer_transport import (
    COMPETITOR_SEARCH_PRESENCE_SOURCE_KEY,
    PostgresIntelligenceMaterializer,
    persist_competitor_search_presence_signal,
)
from empire_os.search_fabric.search import search as search_web


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/competitive_intelligence/"
    "competitor_search_presence_latest.json"
)

DEFAULT_QUERIES = (
    "Denver roofing",
    "Denver roofers",
    "roofing contractors Denver CO",
    "Denver roofing contractor",
    "roof repair Denver",
    "roof replacement Denver",
    "Denver hail damage roofing",
    "storm damage roofing Denver",
    "commercial roofing Denver",
    "residential roofing Denver",
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _domain(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    return (urlparse(text).hostname or "").lower().removeprefix("www.")


def _search_query(query: str, num: int = 20) -> dict[str, Any]:
    """Use Search Fabric's bounded provider rotation and quality gate.

    Auto mode prefers Brave when configured, then bounded public providers and
    recovery adapters. This is intentionally broader than the earlier Bing-only
    path because a single provider returning zero relevant results is not proof
    of zero public search presence.
    """
    result = search_web(query, num=num)
    if isinstance(result, Mapping):
        return dict(result)
    return {
        "organic": [],
        "searchParameters": {
            "q": query,
            "num": num,
            "engine": "none",
        },
        "credits_left": 999999,
        "error": "no_relevant_results",
    }


def _canonical_company_queries(
    company_name: str,
    company_domain: str,
) -> tuple[str, ...]:
    """Bounded verification queries for a known canonical company.

    These queries verify observed search/index presence for an already-resolved
    company. They do not discover companies and do not establish market share.
    """
    name = _clean(company_name)
    domain = _domain(company_domain)
    if domain and name:
        return (f'site:{domain} "{name}"',)
    if domain:
        return (f"site:{domain}",)
    if name:
        return (f'"{name}" Denver roofing',)
    return ()


def _canonical_presence_probe(
    *,
    company: Mapping[str, Any],
    search_fn=_search_query,
) -> list[dict[str, Any]]:
    entity_id = _clean(company.get("entity_id") or company.get("id"))
    company_name = _clean(
        company.get("company_name") or company.get("canonical_name")
    )
    company_domain = _domain(
        company.get("company_domain") or company.get("canonical_website")
    )
    if not entity_id or not company_domain:
        return []

    observations = []
    for query in _canonical_company_queries(company_name, company_domain):
        result = search_fn(query, 10)
        organic = result.get("organic") if isinstance(result, Mapping) else []
        organic = organic if isinstance(organic, list) else []
        engine = _clean(
            (result.get("searchParameters") or {}).get("engine")
        ) if isinstance(result, Mapping) else ""

        matched = None
        for idx, row in enumerate(organic, 1):
            if not isinstance(row, Mapping):
                continue
            link = _clean(row.get("link"))
            observed_domain = _domain(link)
            if (
                observed_domain == company_domain
                or observed_domain.endswith("." + company_domain)
            ):
                matched = {
                    "query": query,
                    "engine": engine or "unknown",
                    "position": int(row.get("position") or idx),
                    "entity_id": entity_id,
                    "company_name": company_name,
                    "domain": company_domain,
                    "url": link,
                    "title": _clean(row.get("title")),
                    "snippet": _clean(row.get("snippet")),
                    "observed_at": datetime.now(timezone.utc).isoformat(),
                    "provenance": {
                        "source": "empire_search_fabric",
                        "discovery_mode": "canonical_company_verification",
                        "quality_gate": (
                            (result.get("searchParameters") or {}).get(
                                "quality_gate"
                            )
                        ) if isinstance(result, Mapping) else None,
                    },
                }
                break

        if matched is not None:
            observations.append(matched)
            break

    return observations


def _match_company_for_domain(
    domain: str,
    domain_to_company: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any] | None:
    """Resolve exact or owned subdomain SERP hits to canonical companies."""
    normalized = _domain(domain)
    if not normalized:
        return None
    direct = domain_to_company.get(normalized)
    if direct is not None:
        return direct
    for canonical, company in domain_to_company.items():
        if normalized.endswith("." + canonical):
            return company
    return None


def build_search_presence_snapshot(
    *,
    companies: list[Mapping[str, Any]],
    queries: tuple[str, ...] = DEFAULT_QUERIES,
    search_fn=_search_query,
    max_workers: int = 4,
    verify_canonical_companies: bool = True,
) -> dict[str, Any]:
    domain_to_company: dict[str, dict[str, Any]] = {}
    for company in companies:
        domain = _domain(
            company.get("company_domain")
            or company.get("canonical_website")
        )
        entity_id = _clean(company.get("entity_id") or company.get("id"))
        if not domain or not entity_id:
            continue
        domain_to_company[domain] = {
            "entity_id": entity_id,
            "company_name": _clean(
                company.get("company_name")
                or company.get("canonical_name")
            ),
            "company_domain": domain,
        }

    observations: list[dict[str, Any]] = []
    query_results: list[dict[str, Any]] = []

    def _run(query: str) -> dict[str, Any]:
        result = search_fn(query, 20)
        engine = _clean(
            (result.get("searchParameters") or {}).get("engine")
        )
        organic = result.get("organic")
        organic = organic if isinstance(organic, list) else []

        seen_domains: set[str] = set()
        query_observations = []
        for idx, row in enumerate(organic, 1):
            if not isinstance(row, Mapping):
                continue
            link = _clean(row.get("link"))
            domain = _domain(link)
            if not domain or domain in seen_domains:
                continue
            seen_domains.add(domain)
            company = _match_company_for_domain(
                domain,
                domain_to_company,
            )
            if company is None:
                continue

            try:
                position = int(row.get("position") or idx)
            except (TypeError, ValueError):
                position = idx

            query_observations.append({
                "query": query,
                "engine": engine or "unknown",
                "position": position,
                "entity_id": company["entity_id"],
                "company_name": company["company_name"],
                "domain": domain,
                "url": link,
                "title": _clean(row.get("title")),
                "snippet": _clean(row.get("snippet")),
                "observed_at": datetime.now(timezone.utc).isoformat(),
                "provenance": {
                    "source": "empire_search_fabric",
                    "quality_gate": (
                        (result.get("searchParameters") or {}).get(
                            "quality_gate"
                        )
                    ),
                },
            })

        return {
            "query": query,
            "engine": engine or "none",
            "result_count": len(organic),
            "matched_company_count": len(query_observations),
            "observations": query_observations,
        }

    workers = min(max(1, int(max_workers)), max(1, len(queries)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_run, query): query
            for query in queries
        }
        for future in as_completed(futures):
            query_results.append(future.result())

    query_results.sort(key=lambda row: row["query"].casefold())
    for row in query_results:
        observations.extend(row["observations"])

    generic_observations = list(observations)
    canonical_verification_observations: list[dict[str, Any]] = []
    if verify_canonical_companies and domain_to_company:
        verification_workers = min(
            max(1, int(max_workers)),
            len(domain_to_company),
        )
        with ThreadPoolExecutor(
            max_workers=verification_workers
        ) as executor:
            futures = [
                executor.submit(
                    _canonical_presence_probe,
                    company=company,
                    search_fn=search_fn,
                )
                for company in domain_to_company.values()
            ]
            for future in as_completed(futures):
                canonical_verification_observations.extend(
                    future.result()
                )

        seen = {
            (
                row["entity_id"],
                row["query"],
                row["url"],
            )
            for row in observations
        }
        for row in canonical_verification_observations:
            key = (
                row["entity_id"],
                row["query"],
                row["url"],
            )
            if key not in seen:
                observations.append(row)
                seen.add(key)

    company_state: dict[str, dict[str, Any]] = {}
    for company in domain_to_company.values():
        company_state[company["entity_id"]] = {
            **company,
            "generic_queries_observed": set(),
            "generic_positions": [],
            "generic_observations": [],
            "canonical_verification_observations": [],
        }

    for row in generic_observations:
        state = company_state[row["entity_id"]]
        state["generic_queries_observed"].add(row["query"])
        state["generic_positions"].append(row["position"])
        state["generic_observations"].append(row)

    for row in canonical_verification_observations:
        state = company_state.get(row["entity_id"])
        if state is not None:
            state["canonical_verification_observations"].append(row)

    company_presence = []
    for state in company_state.values():
        generic_positions = state["generic_positions"]
        generic_weight = sum(
            1.0 / max(1, int(position))
            for position in generic_positions
        )
        all_observations = (
            state["generic_observations"]
            + state["canonical_verification_observations"]
        )
        company_presence.append({
            "entity_id": state["entity_id"],
            "company_name": state["company_name"],
            "company_domain": state["company_domain"],
            "query_presence_count": len(
                state["generic_queries_observed"]
            ),
            "generic_query_presence_count": len(
                state["generic_queries_observed"]
            ),
            "canonical_search_verified": bool(
                state["canonical_verification_observations"]
            ),
            "observation_count": len(all_observations),
            "generic_observation_count": len(
                state["generic_observations"]
            ),
            "canonical_verification_observation_count": len(
                state["canonical_verification_observations"]
            ),
            "best_position": (
                min(generic_positions)
                if generic_positions
                else None
            ),
            "reciprocal_position_weight": round(
                generic_weight,
                6,
            ),
            "observations": all_observations,
            "generic_observations": state["generic_observations"],
            "canonical_verification_observations": (
                state["canonical_verification_observations"]
            ),
            "search_presence_observed": bool(all_observations),
            "market_share_inferred": False,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
        })

    company_presence.sort(
        key=lambda row: (
            -int(row["canonical_search_verified"]),
            -row["reciprocal_position_weight"],
            -row["generic_query_presence_count"],
            row["company_name"].casefold(),
        )
    )

    total_weight = sum(
        row["reciprocal_position_weight"]
        for row in company_presence
    )
    for row in company_presence:
        row["observed_search_presence_share"] = (
            round(
                row["reciprocal_position_weight"] / total_weight,
                6,
            )
            if total_weight > 0
            else None
        )

    engines = sorted({
        row["engine"]
        for row in query_results
        if row["engine"] and row["engine"] != "none"
    })

    return {
        "schema_version": "empire.competitor_search_presence.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "query_count": len(queries),
        "query_with_results_count": sum(
            1 for row in query_results if row["result_count"] > 0
        ),
        "query_with_market_company_count": sum(
            1 for row in query_results
            if row["matched_company_count"] > 0
        ),
        "engine_count": len(engines),
        "engines": engines,
        "canonical_company_count": len(company_presence),
        "company_with_search_presence_count": sum(
            1 for row in company_presence
            if row["search_presence_observed"]
        ),
        "company_with_generic_market_presence_count": sum(
            1 for row in company_presence
            if row["generic_observation_count"] > 0
        ),
        "canonical_search_verified_company_count": sum(
            1 for row in company_presence
            if row["canonical_search_verified"]
        ),
        "observation_count": len(observations),
        "generic_query_observation_count": sum(
            len(row["observations"])
            for row in query_results
        ),
        "canonical_verification_observation_count": len(
            canonical_verification_observations
        ),
        "canonical_verification_enabled": bool(
            verify_canonical_companies
        ),
        "query_results": query_results,
        "companies": company_presence,
        "search_presence_available": bool(observations),
        "share_of_voice_available": total_weight > 0,
        "share_metric": (
            "reciprocal_position_weighted_observed_search_presence"
            if total_weight > 0
            else None
        ),
        "market_share": None,
        "market_share_inferred": False,
        "demand_inferred": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def search_presence_intelligence_signal(
    company: Mapping[str, Any],
    *,
    source_id: str,
) -> dict[str, Any]:
    entity_id = _clean(company.get("entity_id"))
    observations = [
        dict(row)
        for row in company.get("observations", []) or []
        if isinstance(row, Mapping)
    ]
    if not entity_id:
        raise ValueError("entity_id_required")
    if not observations:
        raise ValueError("search_presence_observations_required")

    observed_at = max(
        _clean(row.get("observed_at"))
        for row in observations
        if _clean(row.get("observed_at"))
    )

    return {
        "schema_version": "intelligence_signal_candidate.v1",
        "entity_id": entity_id,
        "signal_type": "competitor_search_presence",
        "signal_domain": "search_intelligence",
        "observed_at": observed_at,
        "source_id": _clean(source_id),
        "strength": min(
            1.0,
            float(company.get("query_presence_count") or 0) / 3.0,
        ),
        "confidence": 0.85,
        "payload": {
            "company_name": _clean(company.get("company_name")),
            "company_domain": _clean(company.get("company_domain")),
            "query_presence_count": int(
                company.get("query_presence_count") or 0
            ),
            "observation_count": len(observations),
            "best_position": company.get("best_position"),
            "reciprocal_position_weight": company.get(
                "reciprocal_position_weight"
            ),
            "observed_search_presence_share": company.get(
                "observed_search_presence_share"
            ),
            "observations": observations,
            "research_candidate": True,
            "market_share_inferred": False,
            "demand_inferred": False,
            "buyer_intent": False,
            "commercial_intent": False,
            "prospect_created": False,
            "outreach_enabled": False,
        },
        "persistence_performed": False,
        "market_share_inferred": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def write_search_presence_snapshot(
    repo_root: Path,
    payload: Mapping[str, Any],
) -> Path:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return path


def refresh_search_presence_snapshot(
    repo_root: Path,
    writer: PostgresIntelligenceMaterializer,
    *,
    persist: bool = False,
) -> dict[str, Any]:
    market = _load_json(
        repo_root
        / "runtime/competitive_intelligence/"
        / "competitor_market_scale_latest.json"
    )
    companies = load_resolved_market_entities(
        writer,
        niche=_clean(market.get("niche")),
        metro=_clean(market.get("metro")),
    )
    payload = build_search_presence_snapshot(companies=companies)

    persistence = []
    if persist:
        with writer._connect(writer.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET LOCAL ROLE empire_intelligence_materializer"
                )
                source_id = writer._source_id(
                    cursor,
                    COMPETITOR_SEARCH_PRESENCE_SOURCE_KEY,
                )

        for company in payload["companies"]:
            if int(company.get("observation_count") or 0) < 1:
                continue
            signal = search_presence_intelligence_signal(
                company,
                source_id=source_id,
            )
            persistence.append(
                persist_competitor_search_presence_signal(
                    writer,
                    signal,
                )
            )

    payload["persist_requested"] = bool(persist)
    payload["persisted_signal_count"] = sum(
        1 for row in persistence if row.get("inserted") is True
    )
    payload["existing_signal_count"] = sum(
        1 for row in persistence if row.get("existing") is True
    )
    payload["persistence"] = persistence

    write_search_presence_snapshot(repo_root, payload)
    return payload


def build_search_presence_runtime(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    try:
        payload = _load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "available": False,
            "schema_version": "empire.competitor_search_presence.v1",
            "mode": "OBSERVE",
            "query_count": 0,
            "canonical_company_count": 0,
            "company_with_search_presence_count": 0,
            "observation_count": 0,
            "search_presence_available": False,
            "market_share": None,
            "market_share_inferred": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Measure observed competitor search presence"
    )
    parser.add_argument(
        "--repo-root",
        default=os.getenv("EMPIRE_REPO_ROOT", "/srv/empire_os"),
    )
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--persist", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if not args.refresh:
        print(json.dumps(
            build_search_presence_runtime(repo_root),
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0

    writer = PostgresIntelligenceMaterializer.from_env()
    payload = refresh_search_presence_snapshot(
        repo_root,
        writer,
        persist=args.persist,
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
