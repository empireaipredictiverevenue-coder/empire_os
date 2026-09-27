"""Canonical competitor-intelligence feed for downstream Empire systems.

The feed reuses already-resolved business_entities as the market roster, then
projects observed competitor evidence into read-only inputs for:
- TAM / Market Intelligence
- Revenue GPS / Market Sweeps
- GTM planning
- Search Intelligence

No buyer intent, commercial intent, demand, market share, revenue opportunity,
prospect creation, outreach, or execution authority is inferred here.
"""
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from empire_os.competitor_audience_sweep import (
    load_resolved_market_entities,
)
from empire_os.intelligence_materializer_transport import (
    PostgresIntelligenceMaterializer,
)


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/competitive_intelligence/"
    "competitor_intelligence_feed_latest.json"
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def _optional_json(path: Path) -> dict[str, Any]:
    try:
        return _load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {}


def _index_companies(
    snapshot: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    return {
        _clean(row.get("entity_id")): row
        for row in snapshot.get("companies", []) or []
        if isinstance(row, Mapping) and _clean(row.get("entity_id"))
    }


def build_competitor_intelligence_feed(
    *,
    niche: str,
    metro: str,
    companies: list[Mapping[str, Any]],
    market_scale: Mapping[str, Any] | None = None,
    ecosystem: Mapping[str, Any] | None = None,
    reviews: Mapping[str, Any] | None = None,
    activity: Mapping[str, Any] | None = None,
    search_presence: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    market_scale = dict(market_scale or {})
    ecosystem = dict(ecosystem or {})
    reviews = dict(reviews or {})
    activity = dict(activity or {})
    search_presence = dict(search_presence or {})

    ecosystem_by_entity = _index_companies(ecosystem)
    reviews_by_entity = _index_companies(reviews)
    activity_by_entity = _index_companies(activity)
    search_by_entity = _index_companies(search_presence)

    market_company_rows = {
        _clean(row.get("entity_id")): row
        for row in market_scale.get("companies", []) or []
        if isinstance(row, Mapping) and _clean(row.get("entity_id"))
    }

    rows = []
    for company in companies:
        entity_id = _clean(company.get("entity_id") or company.get("id"))
        if not entity_id:
            continue

        eco = ecosystem_by_entity.get(entity_id, {})
        rev = reviews_by_entity.get(entity_id, {})
        act = activity_by_entity.get(entity_id, {})
        sea = search_by_entity.get(entity_id, {})
        market = market_company_rows.get(entity_id, {})

        observed_feature_count = sum((
            1 if int(market.get("evidence_count") or 0) > 0 else 0,
            1 if int(eco.get("surface_count") or 0) > 0 else 0,
            1 if int(rev.get("profile_count") or 0) > 0 else 0,
            1 if int(act.get("observation_count") or 0) > 0 else 0,
            1 if bool(sea.get("canonical_search_verified")) else 0,
        ))

        rows.append({
            "entity_id": entity_id,
            "company_name": _clean(
                company.get("company_name")
                or company.get("canonical_name")
            ),
            "company_domain": _clean(
                company.get("company_domain")
                or company.get("canonical_website")
            ),
            "niche": _clean(niche),
            "metro": _clean(metro),
            "competitor_evidence_count": int(
                market.get("evidence_count") or 0
            ),
            "ecosystem_surface_count": int(
                eco.get("surface_count") or 0
            ),
            "public_review_profile_count": int(
                rev.get("profile_count") or 0
            ),
            "public_activity_observation_count": int(
                act.get("observation_count") or 0
            ),
            "canonical_search_verified": bool(
                sea.get("canonical_search_verified")
            ),
            "generic_search_observation_count": int(
                sea.get("generic_observation_count") or 0
            ),
            "observed_feature_family_count": observed_feature_count,
            "research_context_available": observed_feature_count > 0,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "demand_inferred": False,
            "revenue_opportunity_inferred": False,
            "prospect_created": False,
            "outreach_enabled": False,
        })

    rows.sort(key=lambda row: row["company_name"].casefold())
    domains = sorted({
        row["company_domain"]
        for row in rows
        if row["company_domain"]
    })

    search_overlay_available = bool(
        search_presence.get("search_presence_available")
    )
    share_of_voice_available = bool(
        search_presence.get("share_of_voice_available")
    )

    tam = {
        "schema_version": "empire.tam_competitor_context.v1",
        "canonical_company_count": len(rows),
        "niche": _clean(niche),
        "metro": _clean(metro),
        "entity_ids": [row["entity_id"] for row in rows],
        "company_domains": domains,
        "company_nodes": rows,
        "tam_size_inferred": False,
        "market_size_inferred": False,
        "revenue_inferred": False,
    }

    revenue_gps = {
        "schema_version": "empire.revenue_gps_market_context.v1",
        "canonical_company_count": len(rows),
        "companies_with_research_context": sum(
            1 for row in rows if row["research_context_available"]
        ),
        "competitor_overlap_company_count": sum(
            1 for row in rows
            if row["competitor_evidence_count"] > 0
        ),
        "ecosystem_company_count": sum(
            1 for row in rows
            if row["ecosystem_surface_count"] > 0
        ),
        "review_presence_company_count": sum(
            1 for row in rows
            if row["public_review_profile_count"] > 0
        ),
        "public_activity_company_count": sum(
            1 for row in rows
            if row["public_activity_observation_count"] > 0
        ),
        "market_context": rows,
        "demand_inferred": False,
        "revenue_opportunity_inferred": False,
        "economics_estimate": None,
        "prediction_available": False,
    }

    gtm = {
        "schema_version": "empire.gtm_market_context.v1",
        "canonical_company_count": len(rows),
        "company_context": rows,
        "market_context_only": True,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "prospect_created": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }

    search_intelligence = {
        "schema_version": "empire.search_competitor_context.v1",
        "canonical_competitor_domains": domains,
        "canonical_competitor_domain_count": len(domains),
        "competitor_gap_inputs_available": bool(domains),
        "search_presence_overlay_available": search_overlay_available,
        "share_of_voice_available": share_of_voice_available,
        "share_of_voice_metric": (
            search_presence.get("share_metric")
            if share_of_voice_available
            else None
        ),
        "provider_reliability_blocking_canonical_roster": False,
        "market_share_inferred": False,
    }

    return {
        "schema_version": "empire.competitor_intelligence_feed.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "niche": _clean(niche),
        "metro": _clean(metro),
        "canonical_company_count": len(rows),
        "feed_targets": [
            "tam_market_intelligence",
            "revenue_gps",
            "gtm",
            "search_intelligence",
        ],
        "tam": tam,
        "revenue_gps": revenue_gps,
        "gtm": gtm,
        "search_intelligence": search_intelligence,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "demand_inferred": False,
        "market_share_inferred": False,
        "revenue_opportunity_inferred": False,
        "prospect_created": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def write_feed_snapshot(
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


def refresh_feed_snapshot(
    repo_root: Path,
    writer: PostgresIntelligenceMaterializer,
) -> dict[str, Any]:
    runtime = repo_root / "runtime/competitive_intelligence"
    market_scale = _load_json(
        runtime / "competitor_market_scale_latest.json"
    )

    niche = _clean(market_scale.get("niche"))
    metro = _clean(market_scale.get("metro"))
    companies = load_resolved_market_entities(
        writer,
        niche=niche,
        metro=metro,
    )

    payload = build_competitor_intelligence_feed(
        niche=niche,
        metro=metro,
        companies=companies,
        market_scale=market_scale,
        ecosystem=_optional_json(
            runtime / "competitor_ecosystem_latest.json"
        ),
        reviews=_optional_json(
            runtime / "competitor_public_review_overlap_latest.json"
        ),
        activity=_optional_json(
            runtime / "competitor_public_activity_latest.json"
        ),
        search_presence=_optional_json(
            runtime / "competitor_search_presence_latest.json"
        ),
    )
    write_feed_snapshot(repo_root, payload)
    return payload


def build_feed_runtime(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    try:
        payload = _load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "available": False,
            "schema_version": "empire.competitor_intelligence_feed.v1",
            "mode": "OBSERVE",
            "canonical_company_count": 0,
            "feed_targets": [],
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "demand_inferred": False,
            "market_share_inferred": False,
            "revenue_opportunity_inferred": False,
            "prospect_created": False,
            "outreach_enabled": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build canonical competitor intelligence downstream feed"
    )
    parser.add_argument(
        "--repo-root",
        default=os.getenv("EMPIRE_REPO_ROOT", "/srv/empire_os"),
    )
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    if not args.refresh:
        print(json.dumps(
            build_feed_runtime(repo_root),
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0

    writer = PostgresIntelligenceMaterializer.from_env()
    payload = refresh_feed_snapshot(repo_root, writer)
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
