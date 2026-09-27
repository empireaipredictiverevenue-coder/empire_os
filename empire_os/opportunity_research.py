"""Bounded OBSERVE-only research for Predictive Cloud Opportunity Radar.

This executor uses Empire Search Fabric to collect public search observations for
radar candidates. Search results are evidence candidates only. They do not prove
demand, buyer intent, willingness to pay, market share, economics or revenue.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from empire_os.search_fabric.search import search as search_web


RADAR = Path("runtime/opportunity_radar/latest.json")
OUTPUT = Path("runtime/opportunity_radar/research_latest.json")

SearchFn = Callable[..., Mapping[str, Any]]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _tokens(value: Any) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", _clean(value).lower()))


def build_opportunity_research_queries(
    candidate: Mapping[str, Any],
) -> tuple[str, ...]:
    """Build small, deterministic public-research queries."""
    kind = _clean(candidate.get("opportunity_class"))
    niche = _clean(candidate.get("niche"))
    metro = _clean(candidate.get("metro"))
    title = _clean(candidate.get("title"))
    trigger = _clean(candidate.get("trigger"))

    queries: list[str] = []

    if kind == "market_research":
        base = " ".join(value for value in (niche, metro) if value)
        if base:
            queries.extend((
                f'"{base}" demand',
                f'"{base}" competitors pricing',
                f'"{base}" market growth',
            ))
    elif kind == "community_pain":
        pain = title or trigger
        if pain:
            queries.extend((
                f'"{pain}" businesses',
                f'"{pain}" software service',
                f'"{pain}" problem',
            ))
    elif kind == "competitive_research_gap":
        base = " ".join(value for value in (niche, metro) if value)
        if base:
            queries.extend((
                f'"{base}" companies',
                f'"{base}" competitors',
                f'"{base}" services',
            ))
    else:
        base = title or " ".join(
            value for value in (niche, metro, trigger) if value
        )
        if base:
            queries.append(f'"{base}"')

    return tuple(dict.fromkeys(query for query in queries if query.strip()))[:3]


def _result_relevant(
    raw: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> bool:
    haystack = " ".join((
        _clean(raw.get("title")),
        _clean(raw.get("snippet")),
        _clean(raw.get("link") or raw.get("url")),
    )).lower()
    if not haystack:
        return False

    candidate_terms = set(_tokens(candidate.get("niche")))
    candidate_terms.update(_tokens(candidate.get("metro")))
    candidate_terms.update(_tokens(candidate.get("title")))

    # Ignore very generic tokens when evaluating relevance.
    generic = {
        "the", "and", "for", "with", "best", "market", "research",
        "competitor", "evidence", "coverage", "gap",
    }
    candidate_terms = {
        token for token in candidate_terms
        if len(token) >= 3 and token not in generic
    }
    if not candidate_terms:
        return True

    words = set(_tokens(haystack))
    return bool(candidate_terms & words)


def research_candidate(
    candidate: Mapping[str, Any],
    *,
    search_fn: SearchFn = search_web,
    max_results_per_query: int = 3,
) -> dict[str, Any]:
    queries = build_opportunity_research_queries(candidate)
    observations: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    rejected_irrelevant = 0

    for query in queries:
        try:
            result = search_fn(
                query,
                num=max(1, min(int(max_results_per_query), 5)),
            )
        except Exception as exc:
            observations.append({
                "query": query,
                "observation_type": "search_error",
                "error": str(exc)[:500],
                "verified_fact": False,
            })
            continue

        if not isinstance(result, Mapping):
            continue

        params = result.get("searchParameters")
        engine = (
            _clean(params.get("engine"))
            if isinstance(params, Mapping)
            else ""
        )

        for raw in result.get("organic", []) or []:
            if not isinstance(raw, Mapping):
                continue
            url = _clean(raw.get("link") or raw.get("url"))
            if not url or url in seen_urls:
                continue
            if not _result_relevant(raw, candidate):
                rejected_irrelevant += 1
                continue
            seen_urls.add(url)
            observations.append({
                "query": query,
                "engine": engine or None,
                "position": raw.get("position"),
                "title": _clean(raw.get("title")),
                "snippet": _clean(raw.get("snippet")),
                "url": url,
                "relevance_score": raw.get("relevance_score"),
                "observation_type": "public_search_result",
                "verified_fact": False,
            })

    evidence_urls = tuple(
        row["url"]
        for row in observations
        if row.get("url")
    )

    return {
        "schema_version": "empire.opportunity_research.v1",
        "mode": "OBSERVE",
        "opportunity_key": _clean(candidate.get("opportunity_key")),
        "opportunity_class": _clean(
            candidate.get("opportunity_class")
        ),
        "title": _clean(candidate.get("title")),
        "planned_query_count": len(queries),
        "queries": list(queries),
        "observation_count": sum(
            row.get("observation_type") == "public_search_result"
            for row in observations
        ),
        "error_count": sum(
            row.get("observation_type") == "search_error"
            for row in observations
        ),
        "irrelevant_result_rejected_count": rejected_irrelevant,
        "evidence_urls": list(dict.fromkeys(evidence_urls)),
        "observations": observations,
        "observations_are_verified_facts": False,
        "demand_inferred": False,
        "buyer_intent_inferred": False,
        "willingness_to_pay_inferred": False,
        "market_share_inferred": False,
        "revenue_inferred": False,
        "automatic_external_execution_allowed": False,
        "execution_authority": "none",
    }


def execute_opportunity_research(
    radar: Mapping[str, Any],
    *,
    search_fn: SearchFn = search_web,
    max_candidates: int = 5,
    max_results_per_query: int = 3,
) -> dict[str, Any]:
    raw_candidates = radar.get("candidates")
    candidates = raw_candidates if isinstance(raw_candidates, list) else []
    selected = [
        row for row in candidates
        if isinstance(row, Mapping)
    ][:max(1, min(int(max_candidates), 10))]

    actions = [
        research_candidate(
            row,
            search_fn=search_fn,
            max_results_per_query=max_results_per_query,
        )
        for row in selected
    ]

    return {
        "schema_version": "empire.opportunity_research_batch.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "radar_candidate_count": len(candidates),
        "researched_candidate_count": len(actions),
        "observation_count": sum(
            int(row.get("observation_count") or 0)
            for row in actions
        ),
        "error_count": sum(
            int(row.get("error_count") or 0)
            for row in actions
        ),
        "actions": actions,
        "next_layer": "opportunity_factory_evidence_review",
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "revenue_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def refresh_opportunity_research(repo_root: Path) -> dict[str, Any]:
    radar_path = repo_root / RADAR
    try:
        radar = json.loads(radar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        radar = {
            "schema_version": "empire.predictive_cloud.opportunity_radar.v1",
            "candidates": [],
        }
    if not isinstance(radar, Mapping):
        raise ValueError("Opportunity Radar snapshot must be an object")

    payload = execute_opportunity_research(radar)
    path = repo_root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
