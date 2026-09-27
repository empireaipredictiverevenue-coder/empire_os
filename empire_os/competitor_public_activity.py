"""Bounded first-party public activity mining for competitor companies.

Covers four evidence families in one pass:
- ads/offers/creative surfaces
- jobs/hiring surfaces
- events/webinars surfaces
- public company activity/news surfaces

Observations are evidence only. They do not establish demand, buyer intent,
commercial intent, revenue, market share, prospect status, or execution
authority.
"""
from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

from empire_os.competitor_audience_sweep import (
    fetch_public_html,
    load_resolved_market_entities,
)
from empire_os.competitor_ecosystem_mining import _LinkParser
from empire_os.intelligence_materializer_transport import (
    COMPETITOR_PUBLIC_ACTIVITY_SOURCE_KEY,
    PostgresIntelligenceMaterializer,
    persist_competitor_public_activity_signal,
)


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/competitive_intelligence/"
    "competitor_public_activity_latest.json"
)

CATEGORY_TERMS: dict[str, tuple[str, ...]] = {
    "ads_offers_creative": (
        "special",
        "specials",
        "offer",
        "offers",
        "coupon",
        "coupons",
        "discount",
        "discounts",
        "financing",
        "free estimate",
        "promotion",
        "promotions",
        "promo",
        "campaign",
        "commercial",
        "advertising",
        "video",
    ),
    "hiring": (
        "career",
        "careers",
        "job",
        "jobs",
        "hiring",
        "employment",
        "join our team",
        "work with us",
    ),
    "events": (
        "event",
        "events",
        "webinar",
        "webinars",
        "workshop",
        "workshops",
        "seminar",
        "seminars",
        "expo",
        "conference",
        "open house",
    ),
    "company_activity": (
        "news",
        "blog",
        "press",
        "media",
        "updates",
        "latest",
        "resources",
        "articles",
        "insights",
    ),
}


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _domain(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    if "://" not in text:
        text = "https://" + text
    return (urlparse(text).hostname or "").lower().removeprefix("www.")


def _categories(text: str, href: str) -> list[str]:
    joined = f"{_clean(text)} {_clean(href)}".lower().replace("-", " ")
    out = []
    for category, terms in CATEGORY_TERMS.items():
        if any(term in joined for term in terms):
            out.append(category)
    return out


def discover_company_public_activity(
    *,
    entity_id: str,
    company_name: str,
    company_website: str,
    fetch_fn=fetch_public_html,
    max_follow_pages: int = 10,
) -> dict[str, Any]:
    base = _clean(company_website)
    if base and "://" not in base:
        base = "https://" + base

    observed_at = datetime.now(timezone.utc).isoformat()
    company_domain = _domain(base)
    empty = {
        "entity_id": _clean(entity_id),
        "company_name": _clean(company_name),
        "company_domain": company_domain,
        "observed_at": observed_at,
        "homepage_observed": False,
        "observation_count": 0,
        "ads_offers_creative_count": 0,
        "hiring_count": 0,
        "event_count": 0,
        "company_activity_count": 0,
        "observations": [],
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }
    if not base or not company_domain:
        return empty

    homepage = fetch_fn(base)
    if not homepage:
        return empty

    parser = _LinkParser()
    parser.feed(homepage)

    candidates: dict[str, dict[str, Any]] = {}
    for link in parser.links:
        href = urljoin(base, _clean(link.get("href")))
        if _domain(href) != company_domain:
            continue
        categories = _categories(_clean(link.get("text")), href)
        if not categories:
            continue
        row = candidates.setdefault(
            href,
            {
                "source_ref": href,
                "link_text": _clean(link.get("text")),
                "categories": set(),
            },
        )
        row["categories"].update(categories)

    observations: list[dict[str, Any]] = []
    for row in list(candidates.values())[:max(0, int(max_follow_pages))]:
        source_ref = row["source_ref"]
        categories = sorted(row["categories"])
        page_observed = fetch_fn(source_ref) is not None
        for category in categories:
            observations.append({
                "category": category,
                "evidence_key": (
                    f"{category}:"
                    f"{source_ref.lower().rstrip('/')}"
                ),
                "source_ref": source_ref,
                "link_text": row["link_text"],
                "first_party": True,
                "page_observed": page_observed,
                "observed_at": observed_at,
                "buyer_intent_inferred": False,
                "commercial_intent_inferred": False,
            })

    observations.sort(
        key=lambda row: (row["category"], row["source_ref"])
    )

    return {
        **empty,
        "homepage_observed": True,
        "observation_count": len(observations),
        "ads_offers_creative_count": sum(
            1 for row in observations
            if row["category"] == "ads_offers_creative"
        ),
        "hiring_count": sum(
            1 for row in observations
            if row["category"] == "hiring"
        ),
        "event_count": sum(
            1 for row in observations
            if row["category"] == "events"
        ),
        "company_activity_count": sum(
            1 for row in observations
            if row["category"] == "company_activity"
        ),
        "observations": observations,
    }


def public_activity_intelligence_signal(
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
        raise ValueError("public_activity_observations_required")

    return {
        "schema_version": "intelligence_signal_candidate.v1",
        "entity_id": entity_id,
        "signal_type": "competitor_public_activity",
        "signal_domain": "competitive_intelligence",
        "observed_at": _clean(company.get("observed_at")),
        "source_id": _clean(source_id),
        "strength": min(1.0, len(observations) / 4.0),
        "confidence": 0.85,
        "payload": {
            "company_name": _clean(company.get("company_name")),
            "company_domain": _clean(company.get("company_domain")),
            "observation_count": len(observations),
            "ads_offers_creative_count": int(
                company.get("ads_offers_creative_count") or 0
            ),
            "hiring_count": int(company.get("hiring_count") or 0),
            "event_count": int(company.get("event_count") or 0),
            "company_activity_count": int(
                company.get("company_activity_count") or 0
            ),
            "observations": observations,
            "research_candidate": True,
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


def build_public_activity_snapshot(
    *,
    companies: list[Mapping[str, Any]],
    fetch_fn=fetch_public_html,
    max_workers: int = 5,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def _run(company: Mapping[str, Any]) -> dict[str, Any]:
        return discover_company_public_activity(
            entity_id=_clean(company.get("entity_id") or company.get("id")),
            company_name=_clean(
                company.get("company_name") or company.get("canonical_name")
            ),
            company_website=_clean(
                company.get("company_domain")
                or company.get("canonical_website")
            ),
            fetch_fn=fetch_fn,
        )

    workers = min(max(1, int(max_workers)), max(1, len(companies)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [executor.submit(_run, row) for row in companies]
        for future in as_completed(futures):
            rows.append(future.result())

    rows.sort(key=lambda row: row["company_name"].casefold())

    return {
        "schema_version": "empire.competitor_public_activity.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "company_count": len(rows),
        "homepage_observed_count": sum(
            1 for row in rows if row["homepage_observed"]
        ),
        "company_with_activity_count": sum(
            1 for row in rows if row["observation_count"] > 0
        ),
        "observation_count": sum(
            row["observation_count"] for row in rows
        ),
        "ads_offers_creative_company_count": sum(
            1 for row in rows
            if row["ads_offers_creative_count"] > 0
        ),
        "hiring_company_count": sum(
            1 for row in rows if row["hiring_count"] > 0
        ),
        "event_company_count": sum(
            1 for row in rows if row["event_count"] > 0
        ),
        "public_activity_company_count": sum(
            1 for row in rows
            if row["company_activity_count"] > 0
        ),
        "companies": rows,
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


def write_public_activity_snapshot(
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


def refresh_public_activity_snapshot(
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
    payload = build_public_activity_snapshot(companies=companies)

    persistence = []
    if persist:
        with writer._connect(writer.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET LOCAL ROLE empire_intelligence_materializer"
                )
                source_id = writer._source_id(
                    cursor,
                    COMPETITOR_PUBLIC_ACTIVITY_SOURCE_KEY,
                )

        for company in payload["companies"]:
            if int(company.get("observation_count") or 0) < 1:
                continue
            signal = public_activity_intelligence_signal(
                company,
                source_id=source_id,
            )
            persistence.append(
                persist_competitor_public_activity_signal(
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

    write_public_activity_snapshot(repo_root, payload)
    return payload


def build_public_activity_runtime(
    repo_root: Path,
) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    try:
        payload = _load_json(path)
    except (OSError, ValueError, json.JSONDecodeError):
        return {
            "available": False,
            "schema_version": "empire.competitor_public_activity.v1",
            "mode": "OBSERVE",
            "company_count": 0,
            "homepage_observed_count": 0,
            "company_with_activity_count": 0,
            "observation_count": 0,
            "ads_offers_creative_company_count": 0,
            "hiring_company_count": 0,
            "event_company_count": 0,
            "public_activity_company_count": 0,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "market_share_inferred": False,
            "outreach_enabled": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mine bounded first-party public company activity"
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
            build_public_activity_runtime(repo_root),
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0

    writer = PostgresIntelligenceMaterializer.from_env()
    payload = refresh_public_activity_snapshot(
        repo_root,
        writer,
        persist=args.persist,
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
