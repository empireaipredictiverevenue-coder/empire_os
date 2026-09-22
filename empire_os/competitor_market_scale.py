"""Market-scale competitor audience orchestration for EmpireOS.

Runs the existing bounded competitor-audience sweep across a vetted market seed
set, then builds company/competitor overlap summaries. The output is research
intelligence only: it does not infer buyer intent, market share, prospect status,
commercial intent, or outreach authority.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Mapping

from empire_os.competitor_audience_sweep import (
    fetch_public_html,
    run_competitor_audience_sweep,
)
from empire_os.intelligence_materializer_transport import (
    PostgresIntelligenceMaterializer,
)
from empire_os.search_fabric.search import search as search_web


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/competitive_intelligence/competitor_market_scale_latest.json"
)

SweepFn = Callable[..., Mapping[str, Any]]


def _market_search(query: str, num: int = 10) -> Mapping[str, Any]:
    """Fast-fail market discovery over the two currently useful Bing paths."""
    for engine in ("bing_html", "bing_rss"):
        result = search_web(query, num=num, engine=engine)
        if isinstance(result, Mapping) and result.get("organic"):
            return result
    return {
        "organic": [],
        "searchParameters": {
            "q": query,
            "num": num,
            "engine": "market_fast_fail",
        },
        "credits_left": 999999,
    }


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def review_market_seed_config(raw: Mapping[str, Any]) -> dict[str, Any]:
    market_key = _clean(raw.get("market_key"))
    market_query = _clean(raw.get("market_query"))
    niche = _clean(raw.get("niche"))
    metro = _clean(raw.get("metro"))
    blockers: list[str] = []

    if not market_key:
        blockers.append("market_key_required")
    if not market_query:
        blockers.append("market_query_required")
    if not niche:
        blockers.append("niche_required")
    if not metro:
        blockers.append("metro_required")

    competitors = []
    seen_keys: set[str] = set()
    seen_domains: set[str] = set()

    for row in raw.get("competitors", []) or []:
        if not isinstance(row, Mapping):
            continue
        key = _clean(row.get("competitor_key"))
        name = _clean(row.get("competitor_name"))
        domain = _clean(row.get("competitor_domain")).lower()
        row_blockers: list[str] = []

        if not key:
            row_blockers.append("competitor_key_required")
        if not name:
            row_blockers.append("competitor_name_required")
        if not domain or "." not in domain:
            row_blockers.append("competitor_domain_required")
        if key and key in seen_keys:
            row_blockers.append("duplicate_competitor_key")
        if domain and domain in seen_domains:
            row_blockers.append("duplicate_competitor_domain")

        if key:
            seen_keys.add(key)
        if domain:
            seen_domains.add(domain)

        competitors.append({
            "competitor_key": key,
            "competitor_name": name,
            "competitor_domain": domain,
            "review_ready": not row_blockers,
            "blockers": row_blockers,
        })

    if not competitors:
        blockers.append("competitor_seed_required")
    if any(not row["review_ready"] for row in competitors):
        blockers.append("invalid_competitor_seed")

    return {
        "schema_version": "empire.competitor_market_seed_review.v1",
        "market_key": market_key,
        "market_query": market_query,
        "niche": niche,
        "metro": metro,
        "source_refs": [
            _clean(value)
            for value in raw.get("source_refs", []) or []
            if _clean(value)
        ],
        "competitor_count": len(competitors),
        "competitors": competitors,
        "review_ready": not blockers,
        "blockers": blockers,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "market_share_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def _aggregate_market_results(
    reviewed: Mapping[str, Any],
    sweeps: list[Mapping[str, Any]],
) -> dict[str, Any]:
    evidence_by_fingerprint: dict[
        tuple[str, str, str], dict[str, Any]
    ] = {}

    seed_meta = {
        _clean(row.get("competitor_key")): row
        for row in reviewed.get("competitors", []) or []
        if isinstance(row, Mapping)
    }

    for sweep in sweeps:
        for item in sweep.get("evidence", []) or []:
            if not isinstance(item, Mapping):
                continue
            entity_id = _clean(item.get("entity_id"))
            competitor_key = _clean(item.get("competitor_key"))
            source_ref = _clean(item.get("source_ref"))
            if not entity_id or not competitor_key or not source_ref:
                continue
            fingerprint = (entity_id, competitor_key, source_ref)
            evidence_by_fingerprint.setdefault(
                fingerprint,
                dict(item),
            )

    company_state: dict[str, dict[str, Any]] = {}
    competitor_state: dict[str, dict[str, Any]] = {}

    for (entity_id, competitor_key, source_ref), item in (
        evidence_by_fingerprint.items()
    ):
        company = company_state.setdefault(entity_id, {
            "entity_id": entity_id,
            "company_name": _clean(item.get("company_name")),
            "company_domain": _clean(item.get("company_domain")),
            "competitors": set(),
            "source_refs": set(),
            "evidence_count": 0,
        })
        company["competitors"].add(competitor_key)
        company["source_refs"].add(source_ref)
        company["evidence_count"] += 1

        meta = seed_meta.get(competitor_key, {})
        competitor = competitor_state.setdefault(competitor_key, {
            "competitor_key": competitor_key,
            "competitor_name": _clean(meta.get("competitor_name")),
            "competitor_domain": _clean(meta.get("competitor_domain")),
            "companies": set(),
            "source_refs": set(),
            "evidence_count": 0,
        })
        competitor["companies"].add(entity_id)
        competitor["source_refs"].add(source_ref)
        competitor["evidence_count"] += 1

    companies = []
    for value in company_state.values():
        companies.append({
            "entity_id": value["entity_id"],
            "company_name": value["company_name"],
            "company_domain": value["company_domain"],
            "competitor_count": len(value["competitors"]),
            "competitors": sorted(value["competitors"]),
            "source_count": len(value["source_refs"]),
            "evidence_count": value["evidence_count"],
            "research_candidate": True,
            "buyer_intent": False,
            "commercial_intent": False,
            "outreach_enabled": False,
        })
    companies.sort(
        key=lambda row: (
            -row["competitor_count"],
            -row["evidence_count"],
            row["company_name"].casefold(),
        )
    )

    competitors = []
    for key, value in competitor_state.items():
        competitors.append({
            "competitor_key": key,
            "competitor_name": value["competitor_name"],
            "competitor_domain": value["competitor_domain"],
            "company_count": len(value["companies"]),
            "company_entity_ids": sorted(value["companies"]),
            "source_count": len(value["source_refs"]),
            "evidence_count": value["evidence_count"],
        })
    competitors.sort(
        key=lambda row: (
            -row["company_count"],
            -row["evidence_count"],
            row["competitor_key"],
        )
    )

    edges = []
    keys = sorted(competitor_state)
    for left, right in itertools.combinations(keys, 2):
        shared = (
            competitor_state[left]["companies"]
            & competitor_state[right]["companies"]
        )
        if not shared:
            continue
        edges.append({
            "competitor_a": left,
            "competitor_b": right,
            "shared_company_count": len(shared),
            "shared_company_entity_ids": sorted(shared),
            "relationship": "observed_shared_company_overlap",
            "market_share_inferred": False,
        })
    edges.sort(
        key=lambda row: (
            -row["shared_company_count"],
            row["competitor_a"],
            row["competitor_b"],
        )
    )

    return {
        "unique_evidence_count": len(evidence_by_fingerprint),
        "company_count": len(companies),
        "competitor_with_evidence_count": len(competitors),
        "companies": companies,
        "competitors": competitors,
        "shared_audience_edges": edges,
        "shared_audience_edge_count": len(edges),
    }


def run_market_scale_sweep(
    *,
    writer: PostgresIntelligenceMaterializer,
    config: Mapping[str, Any],
    persist: bool = False,
    max_seeds: int | None = None,
    sweep_fn: SweepFn = run_competitor_audience_sweep,
    fetch_fn: Callable[[str], str | None] = fetch_public_html,
) -> dict[str, Any]:
    reviewed = review_market_seed_config(config)
    if not reviewed["review_ready"]:
        raise ValueError(
            "invalid_market_seed_config:"
            + ",".join(reviewed["blockers"])
        )

    seeds = [
        row for row in reviewed["competitors"]
        if row["review_ready"]
    ]
    if max_seeds is not None:
        seeds = seeds[:max(1, int(max_seeds))]

    sweeps: list[dict[str, Any]] = []

    source_cache = {
        url: fetch_fn(url)
        for url in reviewed["source_refs"]
    }

    def _market_fetch(url: str) -> str | None:
        if url in source_cache:
            return source_cache[url]
        return fetch_fn(url)

    def _run_seed(seed: Mapping[str, Any]) -> dict[str, Any]:
        result = sweep_fn(
            writer=writer,
            competitor_key=seed["competitor_key"],
            competitor_name=seed["competitor_name"],
            competitor_domain=seed["competitor_domain"],
            market_query=reviewed["market_query"],
            niche=reviewed["niche"],
            metro=reviewed["metro"],
            persist=persist,
            search_fn=_market_search,
            fetch_fn=_market_fetch,
            source_refs=reviewed["source_refs"],
        )
        return dict(result)

    workers = min(3, max(1, len(seeds)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_run_seed, seed): seed
            for seed in seeds
        }
        for future in as_completed(futures):
            sweeps.append(future.result())

    sweeps.sort(
        key=lambda row: _clean(
            row.get("signals", [{}])[0].get("payload", {}).get(
                "competitor_key"
            )
            if row.get("signals") else row.get("market_query")
        )
    )

    aggregate = _aggregate_market_results(reviewed, sweeps)

    return {
        "schema_version": "empire.competitor_market_scale.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market_key": reviewed["market_key"],
        "market_query": reviewed["market_query"],
        "niche": reviewed["niche"],
        "metro": reviewed["metro"],
        "configured_competitor_count": reviewed["competitor_count"],
        "executed_competitor_count": len(seeds),
        "source_refs": reviewed["source_refs"],
        "persist_requested": bool(persist),
        "persisted_signal_count": sum(
            int(row.get("persisted_count") or 0)
            for row in sweeps
        ),
        "existing_signal_count": sum(
            int(row.get("existing_count") or 0)
            for row in sweeps
        ),
        **aggregate,
        "sweeps": sweeps,
        "research_only": True,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "market_share_inferred": False,
        "prospect_created": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def write_market_scale_snapshot(
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


def build_market_scale_runtime(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    try:
        payload = _load_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {
            "available": False,
            "schema_version": "empire.competitor_market_scale.v1",
            "mode": "OBSERVE",
            "configured_competitor_count": 0,
            "executed_competitor_count": 0,
            "company_count": 0,
            "unique_evidence_count": 0,
            "shared_audience_edge_count": 0,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "market_share_inferred": False,
            "outreach_enabled": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run market-scale competitor audience sweeps"
    )
    parser.add_argument(
        "--repo-root",
        default=os.getenv("EMPIRE_REPO_ROOT", "/srv/empire_os"),
    )
    parser.add_argument(
        "--config",
        default="config/competitor_markets/denver_roofing.json",
    )
    parser.add_argument("--persist", action="store_true")
    parser.add_argument("--max-seeds", type=int)
    parser.add_argument("--run", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()

    if not args.run:
        print(json.dumps(
            build_market_scale_runtime(repo_root),
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = repo_root / config_path
    config = _load_json(config_path)

    writer = PostgresIntelligenceMaterializer.from_env()
    payload = run_market_scale_sweep(
        writer=writer,
        config=config,
        persist=args.persist,
        max_seeds=args.max_seeds,
    )
    write_market_scale_snapshot(repo_root, payload)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
