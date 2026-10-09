"""Bounded OBSERVE-only research for Predictive Cloud Opportunity Radar.

This executor uses Empire Search Fabric to collect public search observations for
radar candidates. Search results are evidence candidates only. They do not prove
demand, buyer intent, willingness to pay, market share, economics or revenue.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Callable, Mapping

from empire_os.search_fabric.search import (
    search as search_web,
    search_resilient as search_with_public_recovery,
)


RADAR = Path("runtime/opportunity_radar/latest.json")
INTAKE = Path("runtime/opportunity_factory/intake_latest.json")
OUTPUT = Path("runtime/opportunity_radar/research_latest.json")
# Research observations are reusable leads to evidence, not verified facts.
# Expire stale observations rather than accumulating them indefinitely.
CACHE_TTL_DAYS = 7
PUBLIC_EVIDENCE_BLOCKERS = frozenset({
    "urgency_normalized_score_required",
    "independent_evidence_required",
    "trigger_required",
    "niche_required",
})

SearchFn = Callable[..., Mapping[str, Any]]


def _clean(value: Any) -> str:
    return " ".join(str(value or "").strip().split())


def _tokens(value: Any) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9]+", _clean(value).lower()))


def build_opportunity_research_queries(
    candidate: Mapping[str, Any],
    *,
    evidence_blockers: tuple[str, ...] = (),
) -> tuple[str, ...]:
    """Build small, deterministic public-research queries."""
    kind = _clean(candidate.get("opportunity_class"))
    niche = _clean(candidate.get("niche")).replace("_", " ")
    metro = _clean(candidate.get("metro"))
    title = _clean(candidate.get("title"))
    trigger = _clean(candidate.get("trigger"))

    queries: list[str] = []
    blockers = set(evidence_blockers) & PUBLIC_EVIDENCE_BLOCKERS
    # Overquoting entire niche+metro combinations produces false negatives.
    # Search broadly, retaining the original lexical quality filter.
    base = " ".join(value for value in (niche, metro) if value) or title
    base = " ".join(base.split()[:12])
    sector = niche.casefold()
    year = datetime.now(timezone.utc).year
    if base and "urgency_normalized_score_required" in blockers:
        if any(word in sector for word in ("lawyer", "legal", "tort", "attorney", "litigation")):
            issue = "court filing claims deadline"
        elif any(word in sector for word in ("roof", "contractor", "construction", "hvac")):
            issue = "storm permit insurance claim deadline"
        elif "solar" in sector:
            issue = "installation grant regulatory deadline"
        elif any(word in sector for word in ("revenue", "saas", "software", "enterprise")):
            issue = "enterprise procurement budget contract renewal"
        else:
            issue = "government public notice deadline"
        queries.append(f"{base} {year} {issue}")
    if base and "independent_evidence_required" in blockers:
        queries.append(f"{base} official public records statistics")
    if base and "trigger_required" in blockers:
        queries.append(f"{base} recent event government notice")

    if kind == "market_research":
        if base:
            queries.extend((
                f"{base} market activity",
                f"{base} services competitors pricing",
                f"{base} market trends",
            ))
    elif kind == "community_pain":
        pain = " ".join((title or trigger).split()[:10])
        if pain:
            queries.extend((
                f"{pain} small business",
                f"{pain} software service",
                f"{pain} problem",
            ))
    elif kind == "competitive_research_gap":
        if base:
            queries.extend((
                f"{base} companies",
                f"{base} competitors",
                f"{base} services",
            ))
    elif base:
        queries.append(base)

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
    evidence_blockers: tuple[str, ...] = (),
    recovery_fn: SearchFn | None = None,
) -> dict[str, Any]:
    queries = build_opportunity_research_queries(
        candidate, evidence_blockers=evidence_blockers
    )
    observations: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    rejected_irrelevant = 0
    degraded_queries = 0
    zero_result_queries = 0
    resilient_queries = 0

    for index, query in enumerate(queries):
        # One recovery opportunity per candidate. Otherwise public web
        # retries across 3 queries can exceed the service execution budget.
        recovery = (
            recovery_fn if recovery_fn is not None
            else (search_with_public_recovery if search_fn is search_web else None)
        )
        use_recovery = index == 0 and recovery is not None
        provider = recovery if use_recovery else search_fn
        if use_recovery:
            resilient_queries += 1
        try:
            result = provider(
                query,
                num=max(1, min(int(max_results_per_query), 5)),
            )
        except Exception as exc:
            degraded_queries += 1
            zero_result_queries += 1
            observations.append({
                "query": query,
                "observation_type": "search_error",
                "error_type": type(exc).__name__,
                "verified_fact": False,
            })
            continue

        if not isinstance(result, Mapping):
            degraded_queries += 1
            zero_result_queries += 1
            continue
        params = result.get("searchParameters")
        state = params.get("search_state") if isinstance(params, Mapping) else None
        if (
            result.get("error")
            or state == "PROVIDER_DEGRADED"
            or result.get("search_operational_status") == "DEGRADED"
        ):
            degraded_queries += 1
        if not result.get("organic"):
            zero_result_queries += 1

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
        "evidence_gap_targets": sorted(set(evidence_blockers) & PUBLIC_EVIDENCE_BLOCKERS),
        "observation_count": sum(
            row.get("observation_type") == "public_search_result"
            for row in observations
        ),
        "error_count": sum(
            row.get("observation_type") == "search_error"
            for row in observations
        ),
        "irrelevant_result_rejected_count": rejected_irrelevant,
        "degraded_query_count": degraded_queries,
        "zero_result_query_count": zero_result_queries,
        "resilient_query_count": resilient_queries,
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


def _candidate_fingerprint(
    candidate: Mapping[str, Any], blockers: tuple[str, ...]
) -> str:
    source = {
        "opportunity_key": candidate.get("opportunity_key"),
        "opportunity_class": candidate.get("opportunity_class"),
        "niche": candidate.get("niche"),
        "metro": candidate.get("metro"),
        "trigger": candidate.get("trigger"),
        "title": candidate.get("title"),
        "evidence_refs": candidate.get("evidence_refs"),
        "public_evidence_blockers": sorted(
            set(blockers) & PUBLIC_EVIDENCE_BLOCKERS
        ),
    }
    return hashlib.sha256(
        json.dumps(source, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _observed_at(raw: Any, fallback: Any = None) -> datetime | None:
    for value in (raw, fallback):
        if not isinstance(value, str):
            continue
        try:
            ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if ts.tzinfo is not None:
            return ts.astimezone(timezone.utc)
    return None


def execute_opportunity_research(
    radar: Mapping[str, Any],
    *,
    search_fn: SearchFn = search_web,
    max_candidates: int = 5,
    max_results_per_query: int = 3,
    intake: Mapping[str, Any] | None = None,
    previous: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Rotate bounded owned Search Fabric work, retaining fresh observations.

    When called without prior state this preserves the legacy single-batch
    behaviour. The scheduled caller supplies the prior batch and intake so
    every candidate gets a turn rather than searching the first five forever.
    """
    raw = radar.get("candidates")
    candidates = [row for row in (raw if isinstance(raw, list) else [])
                  if isinstance(row, Mapping)]
    limit = max(1, min(int(max_candidates), 10))
    current = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    if current.tzinfo is None:
        raise ValueError("research clock must be timezone aware")
    current = current.astimezone(timezone.utc)
    prior = previous if isinstance(previous, Mapping) else {}
    prior_by_key = {
        _clean(row.get("opportunity_key")): row
        for row in (prior.get("actions") or [])
        if isinstance(row, Mapping) and _clean(row.get("opportunity_key"))
    }
    blocked_by_key = {
        _clean(row.get("opportunity_key")): tuple(
            str(value) for value in (row.get("blockers") or [])
            if isinstance(value, str)
        )
        for row in ((intake or {}).get("items") or [])
        if isinstance(row, Mapping) and _clean(row.get("opportunity_key"))
    }

    # The stateful path deduplicates Radar keys before spending research calls.
    if previous is not None or intake is not None:
        unique: dict[str, Mapping[str, Any]] = {}
        for row in candidates:
            key = _clean(row.get("opportunity_key"))
            if key and key not in unique:
                unique[key] = row
        candidates = list(unique.values())
        def order(row: Mapping[str, Any]) -> tuple[Any, ...]:
            key = _clean(row.get("opportunity_key"))
            prior_row = prior_by_key.get(key)
            public = set(blocked_by_key.get(key, ())) & PUBLIC_EVIDENCE_BLOCKERS
            stamp = _observed_at(
                prior_row.get("researched_at") if prior_row else None,
                prior.get("generated_at"),
            )
            changed = (
                bool(prior_row and prior_row.get("candidate_fingerprint"))
                and prior_row["candidate_fingerprint"]
                != _candidate_fingerprint(row, blocked_by_key.get(key, ()))
            )
            # New candidates are first, with highest observed priority
            # within that group. Previously researched candidates rotate
            # by age so low-priority niches still get regular coverage.
            try:
                raw_score = row.get("observed_priority_score")
                priority = (
                    float(raw_score) if not isinstance(raw_score, bool)
                    else 0.0
                )
                if not math.isfinite(priority):
                    priority = 0.0
            except (ValueError, TypeError, OverflowError):
                priority = 0.0
            return (
                0 if not prior_row else 1,
                0 if changed else 1,
                0 if public else 1,
                -priority if not prior_row else 0.0,
                stamp or datetime.min.replace(tzinfo=timezone.utc),
                key,
            )
        ordered = sorted(candidates, key=order)
        new_or_changed = [
            row for row in ordered
            if _clean(row.get("opportunity_key")) not in prior_by_key
            or (
                prior_by_key[_clean(row.get("opportunity_key"))].get(
                    "candidate_fingerprint"
                )
                and prior_by_key[_clean(row.get("opportunity_key"))][
                    "candidate_fingerprint"
                ] != _candidate_fingerprint(
                    row,
                    blocked_by_key.get(_clean(row.get("opportunity_key")), ()),
                )
            )
        ]
        # If only four unsearched candidates remain, make four calls, not
        # a fifth unnecessary refresh just to fill the batch capacity.
        selected = (new_or_changed if new_or_changed else ordered)[:limit]
    else:
        selected = candidates[:limit]

    fresh_actions: list[dict[str, Any]] = []
    for row in selected:
        key = _clean(row.get("opportunity_key"))
        blockers = blocked_by_key.get(key, ())
        action = research_candidate(
            row,
            search_fn=search_fn,
            max_results_per_query=max_results_per_query,
            evidence_blockers=blockers,
        )
        action["researched_at"] = current.isoformat()
        action["candidate_fingerprint"] = _candidate_fingerprint(row, blockers)
        action["reused_cached_observations"] = False
        fresh_actions.append(action)

    fresh_by_key = {
        action["opportunity_key"]: action for action in fresh_actions
        if action.get("opportunity_key")
    }
    all_actions: list[dict[str, Any]] = []
    cached_count = 0
    expired_count = 0
    if previous is not None or intake is not None:
        for row in candidates:
            key = _clean(row.get("opportunity_key"))
            if key in fresh_by_key:
                all_actions.append(fresh_by_key[key])
                continue
            cached = prior_by_key.get(key)
            if not cached:
                continue
            stamp = _observed_at(
                cached.get("researched_at"), prior.get("generated_at")
            )
            if (
                stamp is None or stamp > current + timedelta(minutes=5)
                or current - stamp > timedelta(days=CACHE_TTL_DAYS)
            ):
                expired_count += 1
                continue
            if (
                cached.get("candidate_fingerprint")
                and cached["candidate_fingerprint"]
                != _candidate_fingerprint(row, blocked_by_key.get(key, ()))
            ):
                # Never transfer observations across materially changed input.
                expired_count += 1
                continue
            reusable = dict(cached)
            reusable["reused_cached_observations"] = True
            all_actions.append(reusable)
            cached_count += 1
    else:
        all_actions = fresh_actions

    return {
        "schema_version": "empire.opportunity_research_batch.v2",
        "mode": "OBSERVE",
        "generated_at": current.isoformat(),
        "radar_candidate_count": len(raw) if isinstance(raw, list) else 0,
        "researched_candidate_count": len(fresh_actions),
        "covered_candidate_count": len(all_actions),
        "cached_candidate_count": cached_count,
        "expired_cached_candidate_count": expired_count,
        "new_observation_count": sum(int(x.get("observation_count") or 0)
                                     for x in fresh_actions),
        "observation_count": sum(int(x.get("observation_count") or 0)
                                 for x in all_actions),
        "error_count": sum(int(x.get("error_count") or 0)
                           for x in fresh_actions),
        "degraded_query_count": sum(
            int(x.get("degraded_query_count") or 0)
            for x in fresh_actions
        ),
        "zero_result_query_count": sum(
            int(x.get("zero_result_query_count") or 0)
            for x in fresh_actions
        ),
        "resilient_query_count": sum(
            int(x.get("resilient_query_count") or 0)
            for x in fresh_actions
        ),
        "actions": all_actions,
        "cache_ttl_days": CACHE_TTL_DAYS,
        "research_rotation_enabled": previous is not None or intake is not None,
        "next_layer": "opportunity_factory_evidence_review",
        "observations_are_verified_facts": False,
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

    prior_path = repo_root / OUTPUT
    try:
        prior = json.loads(prior_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        prior = {}
    try:
        intake = json.loads((repo_root / INTAKE).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        intake = {}
    payload = execute_opportunity_research(
        radar,
        intake=intake if isinstance(intake, Mapping) else {},
        previous=prior if isinstance(prior, Mapping) else {},
    )
    path = repo_root / OUTPUT
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    tmp.replace(path)
    return payload
