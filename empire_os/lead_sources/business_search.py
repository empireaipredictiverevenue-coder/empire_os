"""EmpireOS canonical adapter for the existing free business scraper.

Reuses /srv/empire_os/biz_scraper.py discovery only.  It does NOT call the
legacy save() function or write /root/feedback. Results enter the canonical
prospect ingest boundary as first-party business identities.
"""
from __future__ import annotations

from typing import Iterator

import biz_scraper

from empire_os.lead_sources import LeadCandidate, SourceInfo
from empire_os.geo_registry import market_by_metro


VERTICALS = (
    "roofing",
    "hvac",
    "plumbing",
    "solar",
    "restoration",
    "electrical",
    "pest_control",
    "painting",
    "commercial_roofing",
    "warehouse",
    "logistics",
    "managed_it",
    "marketing_agency",
)

_AGGREGATOR_TITLE_TERMS = (
    "best ",
    "top ",
    "companies in",
    "contractors in",
    "near me",
    "review)",
    "reviews)",
    "directory",
    "list of",
)


def _looks_like_business_result(name: str) -> bool:
    text = " ".join(str(name or "").strip().lower().split())
    if not text:
        return False
    return not any(term in text for term in _AGGREGATOR_TITLE_TERMS)


def run(metro: str = None) -> Iterator[LeadCandidate]:
    target_metro = str(metro or "").strip()
    if not target_metro:
        return

    market = market_by_metro(target_metro)

    for vertical in VERTICALS:
        try:
            rows = biz_scraper.scrape(vertical, target_metro, limit=8)
        except Exception:
            continue

        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("name") or "").strip()
            website = str(row.get("url") or "").strip()
            domain = str(row.get("domain") or "").strip()
            if (
                not name
                or not website
                or not domain
                or not _looks_like_business_result(name)
            ):
                continue

            yield LeadCandidate(
                name=name,
                phone="",
                niche=vertical,
                metro=target_metro,
                state=market.region_code if market else "",
                country_code=market.country_code if market else "",
                language_code=market.language_code if market else "",
                source_language=market.language_code if market else "",
                timezone=market.timezone if market else "",
                details=(
                    f"Business discovered by Empire free search scraper; "
                    f"first-party domain {domain}"
                ),
                source="biz_search",
                lead_score=75,
                url=website,
                raw={
                    "business_website": website,
                    "domain": domain,
                    "search_adapter": "biz_scraper",
                    "original": row,
                },
            )


def register_source(reg):
    reg(SourceInfo(
        name="biz_search",
        tier="stub",
        requires=[],
        description=(
            "Experimental fallback only. Consumer search backends are not trusted "
            "as a production acquisition source."
        ),
        run_fn=run,
    ))
