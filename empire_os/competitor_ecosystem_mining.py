"""Bounded public ecosystem mining for competitor-market companies.

Discovers first-party case-study/project, testimonial/review, and partner/
association surfaces plus explicit external domains linked from those pages.
The output is research evidence only and does not infer customer status, buyer
intent, commercial intent, market share, or outreach authority.
"""
from __future__ import annotations

import argparse
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urljoin, urlparse

from empire_os.competitor_audience_sweep import (
    fetch_public_html,
    load_resolved_market_entities,
)
from empire_os.intelligence_materializer_transport import (
    COMPETITOR_ECOSYSTEM_SOURCE_KEY,
    PostgresIntelligenceMaterializer,
    persist_competitor_ecosystem_signal,
)


SNAPSHOT_RELATIVE_PATH = Path(
    "runtime/competitive_intelligence/"
    "competitor_ecosystem_latest.json"
)

_CATEGORY_TERMS = {
    "case_study": (
        "case study",
        "case studies",
        "project",
        "projects",
        "portfolio",
        "gallery",
        "our work",
        "recent work",
    ),
    "testimonial": (
        "testimonial",
        "testimonials",
        "review",
        "reviews",
        "success stories",
        "what our clients say",
        "what customers say",
    ),
    "partner": (
        "partner",
        "partners",
        "manufacturer",
        "manufacturers",
        "certification",
        "certifications",
        "association",
        "associations",
        "member",
        "membership",
        "preferred contractor",
    ),
}

_BLOCKED_EXTERNAL = {
    "facebook.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "x.com",
    "twitter.com",
    "google.com",
    "maps.google.com",
    "goo.gl",
    "yelp.com",
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


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[dict[str, str]] = []
        self._href: str | None = None
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() != "a":
            return
        href = None
        for key, value in attrs:
            if key.lower() == "href" and value:
                href = str(value)
                break
        self._href = href
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._href and data.strip():
            self._parts.append(data.strip())

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self._href:
            return
        self.links.append({
            "href": self._href,
            "text": " ".join(self._parts).strip(),
        })
        self._href = None
        self._parts = []


def _classify_link(text: str, href: str) -> list[str]:
    joined = f"{_clean(text)} {_clean(href)}".lower().replace("-", " ")
    categories = []
    for category, terms in _CATEGORY_TERMS.items():
        if any(term in joined for term in terms):
            categories.append(category)
    return categories


def _external_domain(url: str, company_domain: str) -> str | None:
    host = _domain(url)
    if not host or host == company_domain:
        return None
    if host in _BLOCKED_EXTERNAL:
        return None
    if any(host.endswith("." + blocked) for blocked in _BLOCKED_EXTERNAL):
        return None
    return host


def discover_company_ecosystem(
    *,
    entity_id: str,
    company_name: str,
    company_website: str,
    fetch_fn=fetch_public_html,
    max_follow_pages: int = 6,
) -> dict[str, Any]:
    base = _clean(company_website)
    if base and "://" not in base:
        base = "https://" + base
    company_domain = _domain(base)
    if not base or not company_domain:
        return {
            "entity_id": entity_id,
            "company_name": company_name,
            "company_domain": company_domain,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "homepage_observed": False,
            "surface_count": 0,
            "case_study_surface_count": 0,
            "testimonial_surface_count": 0,
            "partner_surface_count": 0,
            "surfaces": [],
            "external_relationship_candidates": [],
            "customer_relationship_inferred": False,
            "partner_relationship_inferred": False,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
        }

    homepage = fetch_fn(base)
    if not homepage:
        return {
            "entity_id": entity_id,
            "company_name": company_name,
            "company_domain": company_domain,
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "homepage_observed": False,
            "surface_count": 0,
            "case_study_surface_count": 0,
            "testimonial_surface_count": 0,
            "partner_surface_count": 0,
            "surfaces": [],
            "external_relationship_candidates": [],
            "customer_relationship_inferred": False,
            "partner_relationship_inferred": False,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
        }

    parser = _LinkParser()
    parser.feed(homepage)

    surfaces_by_url: dict[str, dict[str, Any]] = {}
    for link in parser.links:
        href = urljoin(base, _clean(link.get("href")))
        if _domain(href) != company_domain:
            continue
        categories = _classify_link(link.get("text", ""), href)
        if not categories:
            continue
        row = surfaces_by_url.setdefault(href, {
            "source_ref": href,
            "link_text": _clean(link.get("text")),
            "categories": set(),
        })
        row["categories"].update(categories)

    surfaces = []
    external_by_key: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in list(surfaces_by_url.values())[:max(0, int(max_follow_pages))]:
        source_ref = row["source_ref"]
        categories = sorted(row["categories"])
        surfaces.append({
            "source_ref": source_ref,
            "link_text": row["link_text"],
            "categories": categories,
            "first_party": True,
            "observed": True,
        })

        page = fetch_fn(source_ref)
        if not page:
            continue
        child = _LinkParser()
        child.feed(page)
        for link in child.links:
            absolute = urljoin(source_ref, _clean(link.get("href")))
            external = _external_domain(absolute, company_domain)
            if not external:
                continue
            for category in categories:
                if category != "partner":
                    continue
                key = (category, external, source_ref)
                external_by_key.setdefault(key, {
                    "relationship_type": "public_partner_link_candidate",
                    "category": category,
                    "external_domain": external,
                    "anchor_text": _clean(link.get("text")),
                    "source_ref": source_ref,
                    "observed": True,
                    "partner_status_inferred": False,
                })

    return {
        "entity_id": entity_id,
        "company_name": company_name,
        "company_domain": company_domain,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "homepage_observed": True,
        "surface_count": len(surfaces),
        "case_study_surface_count": sum(
            1 for row in surfaces if "case_study" in row["categories"]
        ),
        "testimonial_surface_count": sum(
            1 for row in surfaces if "testimonial" in row["categories"]
        ),
        "partner_surface_count": sum(
            1 for row in surfaces if "partner" in row["categories"]
        ),
        "surfaces": surfaces,
        "external_relationship_candidates": list(external_by_key.values()),
        "customer_relationship_inferred": False,
        "partner_relationship_inferred": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
    }


def competitor_ecosystem_intelligence_signal(
    company: Mapping[str, Any],
    *,
    source_id: str,
) -> dict[str, Any]:
    entity_id = _clean(company.get("entity_id"))
    if not entity_id:
        raise ValueError("entity_id_required")

    surfaces = [
        dict(row)
        for row in company.get("surfaces", []) or []
        if isinstance(row, Mapping)
    ]
    if not surfaces:
        raise ValueError("ecosystem_surfaces_required")

    observed_at = _clean(company.get("observed_at"))
    if not observed_at:
        observed_at = datetime.now(timezone.utc).isoformat()

    external = [
        dict(row)
        for row in company.get("external_relationship_candidates", []) or []
        if isinstance(row, Mapping)
    ]

    return {
        "schema_version": "intelligence_signal_candidate.v1",
        "entity_id": entity_id,
        "signal_type": "competitor_ecosystem_evidence",
        "signal_domain": "competitive_intelligence",
        "observed_at": observed_at,
        "source_id": _clean(source_id),
        "strength": min(1.0, len(surfaces) / 3.0),
        "confidence": 0.85,
        "payload": {
            "company_name": _clean(company.get("company_name")),
            "company_domain": _clean(company.get("company_domain")),
            "surface_count": len(surfaces),
            "case_study_surface_count": int(
                company.get("case_study_surface_count") or 0
            ),
            "testimonial_surface_count": int(
                company.get("testimonial_surface_count") or 0
            ),
            "partner_surface_count": int(
                company.get("partner_surface_count") or 0
            ),
            "surfaces": surfaces,
            "external_relationship_candidates": external,
            "research_candidate": True,
            "customer_relationship_inferred": False,
            "partner_relationship_inferred": False,
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


def build_ecosystem_snapshot(
    *,
    companies: list[Mapping[str, Any]],
    fetch_fn=fetch_public_html,
    max_workers: int = 5,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []

    def _run(company: Mapping[str, Any]) -> dict[str, Any]:
        return discover_company_ecosystem(
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

    surfaces = [
        surface
        for company in rows
        for surface in company.get("surfaces", [])
    ]
    external = [
        rel
        for company in rows
        for rel in company.get("external_relationship_candidates", [])
    ]

    return {
        "schema_version": "empire.competitor_ecosystem_snapshot.v1",
        "mode": "OBSERVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "company_count": len(rows),
        "homepage_observed_count": sum(
            1 for row in rows if row["homepage_observed"]
        ),
        "case_study_company_count": sum(
            1 for row in rows if row.get("case_study_surface_count", 0) > 0
        ),
        "testimonial_company_count": sum(
            1 for row in rows if row.get("testimonial_surface_count", 0) > 0
        ),
        "partner_surface_company_count": sum(
            1 for row in rows if row.get("partner_surface_count", 0) > 0
        ),
        "surface_count": len(surfaces),
        "external_relationship_candidate_count": len(external),
        "companies": rows,
        "customer_relationship_inferred": False,
        "partner_relationship_inferred": False,
        "buyer_intent_inferred": False,
        "commercial_intent_inferred": False,
        "outreach_enabled": False,
        "execution_authority": "none",
    }


def write_ecosystem_snapshot(
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


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object at {path}")
    return payload


def refresh_ecosystem_snapshot(
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
    payload = build_ecosystem_snapshot(companies=companies)

    persistence = []
    if persist:
        with writer._connect(writer.dsn) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET LOCAL ROLE empire_intelligence_materializer"
                )
                source_id = writer._source_id(
                    cursor,
                    COMPETITOR_ECOSYSTEM_SOURCE_KEY,
                )

        for company in payload.get("companies", []):
            if int(company.get("surface_count") or 0) < 1:
                continue
            signal = competitor_ecosystem_intelligence_signal(
                company,
                source_id=source_id,
            )
            persistence.append(
                persist_competitor_ecosystem_signal(writer, signal)
            )

    payload["persist_requested"] = bool(persist)
    payload["persisted_signal_count"] = sum(
        1 for row in persistence if row.get("inserted") is True
    )
    payload["existing_signal_count"] = sum(
        1 for row in persistence if row.get("existing") is True
    )
    payload["persistence"] = persistence

    write_ecosystem_snapshot(repo_root, payload)
    return payload


def build_ecosystem_runtime(repo_root: Path) -> dict[str, Any]:
    path = repo_root / SNAPSHOT_RELATIVE_PATH
    try:
        payload = _load_json(path)
    except (OSError, json.JSONDecodeError, ValueError):
        return {
            "available": False,
            "schema_version": "empire.competitor_ecosystem_snapshot.v1",
            "mode": "OBSERVE",
            "company_count": 0,
            "homepage_observed_count": 0,
            "case_study_company_count": 0,
            "testimonial_company_count": 0,
            "partner_surface_company_count": 0,
            "surface_count": 0,
            "external_relationship_candidate_count": 0,
            "buyer_intent_inferred": False,
            "commercial_intent_inferred": False,
            "outreach_enabled": False,
            "execution_authority": "none",
        }
    return {"available": True, **payload}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mine bounded public competitor ecosystem surfaces"
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
            build_ecosystem_runtime(repo_root),
            indent=2,
            sort_keys=True,
            default=str,
        ))
        return 0

    writer = PostgresIntelligenceMaterializer.from_env()
    payload = refresh_ecosystem_snapshot(
        repo_root,
        writer,
        persist=args.persist,
    )
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
