"""Public review-platform overlap intelligence for EmpireOS.

This module discovers explicit links from company-controlled public pages to
well-known public review/profile platforms, builds company/platform overlap, and
optionally persists append-only Intelligence Fabric evidence.

It does not scrape private review data, infer sentiment, infer buyer/commercial
intent, create prospects, or enable outreach.
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib.parse import urljoin, urlparse

from empire_os.competitor_audience_sweep import (
    fetch_public_html,
    load_resolved_market_entities,
)
from empire_os.competitor_ecosystem_mining import _LinkParser
from empire_os.intelligence_materializer_transport import (
    COMPETITOR_PUBLIC_REVIEW_SOURCE_KEY,
    PostgresIntelligenceMaterializer,
    persist_competitor_public_review_signal,
)


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/competitive_intelligence/"
    "competitor_public_review_overlap_latest.json"
)

_REVIEW_PLATFORMS: dict[str, tuple[str, ...]] = {
    "google": (
        "google.com",
        "maps.app.goo.gl",
        "g.page",
    ),
    "bbb": ("bbb.org",),
    "yelp": ("yelp.com",),
    "angi": ("angi.com", "angieslist.com"),
    "homeadvisor": ("homeadvisor.com",),
    "houzz": ("houzz.com",),
    "thumbtack": ("thumbtack.com",),
    "guildquality": ("guildquality.com",),
    "birdeye": ("birdeye.com",),
    "porch": ("porch.com",),
    "trustpilot": ("trustpilot.com",),
}

_REVIEW_CUES = (
    "review",
    "reviews",
    "rating",
    "ratings",
    "stars",
    "testimonial",
    "testimonials",
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


def _platform_for_url(url: str, text: str = "") -> str | None:
    host = _domain(url)
    if not host:
        return None

    platform = None
    for key, suffixes in _REVIEW_PLATFORMS.items():
        if any(host == suffix or host.endswith("." + suffix) for suffix in suffixes):
            platform = key
            break
    if platform is None:
        return None

    if platform != "google":
        return platform

    joined = f"{_clean(url)} {_clean(text)}".lower()
    if host in {"g.page", "maps.app.goo.gl"}:
        return platform
    if any(cue in joined for cue in _REVIEW_CUES):
        return platform
    return None


def _pages_for_company(
    *,
    company_website: str,
    ecosystem_row: Mapping[str, Any] | None,
) -> list[str]:
    base = _clean(company_website)
    if base and "://" not in base:
        base = "https://" + base

    pages: list[str] = []
    if base:
        pages.append(base)

    if isinstance(ecosystem_row, Mapping):
        for surface in ecosystem_row.get("surfaces", []) or []:
            if not isinstance(surface, Mapping):
                continue
            categories = surface.get("categories")
            if not isinstance(categories, list):
                continue
            if "testimonial" not in categories:
                continue
            source_ref = _clean(surface.get("source_ref"))
            if source_ref:
                pages.append(source_ref)

    return list(dict.fromkeys(pages))[:5]


def discover_company_review_profiles(
    *,
    entity_id: str,
    company_name: str,
    company_website: str,
    ecosystem_row: Mapping[str, Any] | None = None,
    fetch_fn=fetch_public_html,
) -> dict[str, Any]:
    observed_at = datetime.now(timezone.utc).isoformat()
    company_domain = _domain(company_website)
    profiles: dict[tuple[str, str], dict[str, Any]] = {}
    pages_observed = 0

    for source_ref in _pages_for_company(
        company_website=company_website,
        ecosystem_row=ecosystem_row,
    ):
        html = fetch_fn(source_ref)
        if not html:
            continue
        pages_observed += 1

        parser = _LinkParser()
        parser.feed(html)
        for link in parser.links:
            href = urljoin(source_ref, _clean(link.get("href")))
            platform = _platform_for_url(
                href,
                _clean(link.get("text")),
            )
            if not platform:
                continue

            profile_url = href.split("#", 1)[0]
            key = (platform, profile_url)
            profiles.setdefault(key, {
                "platform": platform,
                "profile_url": profile_url,
                "anchor_text": _clean(link.get("text")),
                "source_ref": source_ref,
                "observed_at": observed_at,
                "public_profile_presence": True,
                "review_sentiment_inferred": False,
            })

    profile_rows = sorted(
        profiles.values(),
        key=lambda row: (row["platform"], row["profile_url"]),
    )
    platforms = sorted({row["platform"] for row in profile_rows})

    return {
        "entity_id": _clean(entity_id),
        "company_name": _clean(company_name),
        "company_domain": company_domain,
        "observed_at": observed_at,
        "pages_observed": pages_observed,
        "profile_count": len(profile_rows),
        "platform_count": len(platforms),
        "platforms": platforms,
        "profiles": profile_rows,
        "review_sentiment_inferred": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def public_review_intelligence_signal(
    company: Mapping[str, Any],
    *,
    source_id: str,
) -> dict[str, Any]:
    entity_id = _clean(company.get("entity_id"))
    profiles = [
        dict(row)
        for row in company.get("profiles", []) or []
        if isinstance(row, Mapping)
    ]
    if not entity_id:
        raise ValueError("entity_id_required")
    if not profiles:
        raise ValueError("public_review_profiles_required")

    return {
        "schema_version": "intelligence_signal_candidate.v1",
        "entity_id": entity_id,
        "signal_type": "competitor_public_review_presence",
        "signal_domain": "competitive_intelligence",
        "observed_at": _clean(company.get("observed_at")),
        "source_id": _clean(source_id),
        "strength": min(1.0, len(profiles) / 3.0),
        "confidence": 0.85,
        "payload": {
            "company_name": _clean(company.get("company_name")),
            "company_domain": _clean(company.get("company_domain")),
            "profile_count": len(profiles),
            "platform_count": int(company.get("platform_count") or 0),
            "platforms": list(company.get("platforms", []) or []),
            "profiles": profiles,
            "research_candidate": True,
            "review_sentiment_inferred": False,
            "buyer_intent": False,
            "commercial_intent": False,
            "prospect_created": False,
            "outreach_enabled": False,
        },
        "persistence_performed": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def build_public_review_overlap_snapshot(
    *,
    companies: list[Mapping[str, Any]],
    ecosystem_snapshot: Mapping[str, Any] | None = None,
    fetch_fn=fetch_public_html,
    max_workers: int = 5,
) -> dict[str, Any]:
    ecosystem_by_entity = {}
    if isinstance(ecosystem_snapshot, Mapping):
        ecosystem_by_entity = {
            _clean(row.get("entity_id")): row
            for row in ecosystem_snapshot.get("companies", []) or []
            if isinstance(row, Mapping) and _clean(row.get("entity_id"))
        }

    rows: list[dict[str, Any]] = []

    def _run(company: Mapping[str, Any]) -> dict[str, Any]:
        entity_id = _clean(company.get("entity_id") or company.get("id"))
        return discover_company_review_profiles(
            entity_id=entity_id,
            company_name=_clean(
                company.get("company_name") or company.get("canonical_name")
            ),
            company_website=_clean(
                company.get("company_domain")
                or company.get("canonical_website")
            ),
            ecosystem_row=ecosystem_by_entity.get(entity_id),
            fetch_fn=fetch_fn,
        )

    workers = min(max(1, int(max_workers)), max(1, len(companies)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_run, row) for row in companies]
        for future in as_completed(futures):
            rows.append(future.result())

    rows.sort(key=lambda row: row["company_name"].casefold())

    platform_state: dict[str, dict[str, Any]] = {}
    for company in rows:
        for profile in company["profiles"]:
            platform = profile["platform"]
            state = platform_state.setdefault(platform, {
                "platform": platform,
                "companies": set(),
                "entity_ids": set(),
                "profile_urls": set(),
            })
            state["companies"].add(company["company_name"])
            state["entity_ids"].add(company["entity_id"])
            state["profile_urls"].add(profile["profile_url"])

    platforms = []
    for state in platform_state.values():
        platforms.append({
            "platform": state["platform"],
            "company_count": len(state["entity_ids"]),
            "companies": sorted(state["companies"]),
            "entity_ids": sorted(state["entity_ids"]),
            "unique_profile_count": len(state["profile_urls"]),
        })
    platforms.sort(
        key=lambda row: (-row["company_count"], row["platform"])
    )

    company_platforms = {
        row["entity_id"]: set(row["platforms"])
        for row in rows
        if row["platforms"]
    }
    company_names = {
        row["entity_id"]: row["company_name"]
        for row in rows
    }

    overlap_edges = []
    for left, right in itertools.combinations(
        sorted(company_platforms),
        2,
    ):
        shared = company_platforms[left] & company_platforms[right]
        if not shared:
            continue
        overlap_edges.append({
            "left_entity_id": left,
            "left_company": company_names[left],
            "right_entity_id": right,
            "right_company": company_names[right],
            "shared_platforms": sorted(shared),
            "shared_platform_count": len(shared),
            "relationship": "observed_shared_public_review_platform",
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
        })

    overlap_edges.sort(
        key=lambda row: (
            -row["shared_platform_count"],
            row["left_company"].casefold(),
            row["right_company"].casefold(),
        )
    )

    return {
        "schema_version": "empire.competitor_public_review_overlap.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "company_count": len(rows),
        "company_with_review_profile_count": sum(
            1 for row in rows if row["profile_count"] > 0
        ),
        "review_profile_count": sum(
            row["profile_count"] for row in rows
        ),
        "review_platform_count": len(platforms),
        "review_platforms": platforms,
        "company_overlap_edge_count": len(overlap_edges),
        "company_overlap_edges": overlap_edges,
        "companies": rows,
        "review_sentiment_inferred": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "market_share_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def write_public_review_overlap_snapshot(
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


def refresh_public_review_overlap_snapshot(
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
    ecosystem_path = (
        repo_root
        / "runtime/competitive_intelligence/"
        / "competitor_ecosystem_latest.json"
    )
    try:
        ecosystem = _load_json(ecosystem_path)
    except (OSError, ValueError, json.JSONDecodeError):
        ecosystem = {}

    companies = load_resolved_market_entities(
        writer,
        niche=_clean(market.get("niche")),
        metro=_clean(market.get("metro")),
    )
    payload = build_public_review_overlap_snapshot(
        companies=companies,
        ecosystem_snapshot=ecosystem,
    )

    persistence = []
    if persist:
        with writer._connect(writer.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET LOCAL ROLE empire_intelligence_materializer"
                )
                source_id = writer._source_id(
                    cursor,
                    COMPETITOR_PUBLIC_REVIEW_SOURCE_KEY,
                )

        for company in payload["companies"]:
            if int(company.get("profile_count") or 0) < 1:
                continue
            signal = public_review_intelligence_signal(
                company,
                source_id=source_id,
            )
            persistence.append(
                persist_competitor_public_review_signal(
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

    write_public_review_overlap_snapshot(repo_root, payload)
    return payload


def build_public_review_overlap_runtime(
    repo_root: Path,
) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    try:
        payload = _load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "available": False,
            "schema_version": "empire.competitor_public_review_overlap.v1",
            "mode": "OBSERVE",
            "company_count": 0,
            "company_with_review_profile_count": 0,
            "review_profile_count": 0,
            "review_platform_count": 0,
            "company_overlap_edge_count": 0,
            "review_sentiment_inferred": False,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "market_share_inferred": False,
            "outreach_enabled": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mine public review-platform overlap"
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
            build_public_review_overlap_runtime(repo_root),
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0

    writer = PostgresIntelligenceMaterializer.from_env()
    payload = refresh_public_review_overlap_snapshot(
        repo_root,
        writer,
        persist=args.persist,
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
