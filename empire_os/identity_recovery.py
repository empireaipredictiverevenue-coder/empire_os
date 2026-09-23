"""Targeted decision-maker identity recovery using Empire-owned intelligence.

This module reuses Search Fabric, Site Probe, Registry Scraper and existing
buyer ranking rules. It never invents a person or email and never performs
outreach.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any
from urllib.parse import urlparse

from empire_os.buyer_discovery import rank_site_people
from empire_os.companies_house_identity import find_companies_house_principals
from empire_os.registry_scraper import RegistryScraper
from empire_os.official_license_identity import find_official_license_principals
from empire_os.search_fabric.search import search
from empire_os.search_fabric.site_probe import probe_site


DECISION_ROLES = (
    "owner",
    "founder",
    "co-founder",
    "president",
    "principal",
    "chief executive officer",
    "ceo",
    "managing director",
    "general manager",
)


@dataclass(frozen=True)
class IdentityEvidence:
    name: str
    title: str
    source: str
    source_url: str
    confidence: float
    first_party: bool
    authoritative_registry: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _host(value: str) -> str:
    raw = urlparse(str(value or "").strip()).netloc.lower()
    return raw[4:] if raw.startswith("www.") else raw


def _same_host(left: str, right: str) -> bool:
    return bool(_host(left)) and _host(left) == _host(right)


def _is_uk_context(metro: str, website: str) -> bool:
    location = str(metro or "").strip().casefold()
    host = _host(website)
    return (
        any(term in location for term in (
            "united kingdom", "great britain", "england",
            "scotland", "wales", "northern ireland",
        ))
        or host.endswith(".uk")
    )


def _state_hint(metro: str) -> str:
    raw = str(metro or "").strip()
    if "," not in raw:
        return ""
    state = raw.rsplit(",", 1)[-1].strip().upper()
    return state if 2 <= len(state) <= 3 else ""


def _rank_people(evidence: dict[str, Any], website: str) -> list[IdentityEvidence]:
    ranked = rank_site_people(evidence.get("people") or [])
    rows: list[IdentityEvidence] = []
    for person in ranked:
        name = str(person.get("name") or "").strip()
        title = str(person.get("title") or "").strip()
        source_url = str(person.get("url") or website).strip()
        try:
            score = float(person.get("decision_score") or 0.0)
        except (TypeError, ValueError):
            score = 0.0
        if (
            name
            and title
            and score >= 0.70
            and _same_host(source_url, website)
        ):
            rows.append(IdentityEvidence(
                name=name,
                title=title,
                source="empire_first_party_people_probe",
                source_url=source_url,
                confidence=min(1.0, max(0.70, score)),
                first_party=True,
            ))
    return rows


def recover_identity(
    *,
    business_name: str,
    website: str,
    metro: str = "",
    max_search_results: int = 8,
) -> dict[str, Any]:
    """Recover a named decision maker with bounded, attributable evidence."""
    business_name = str(business_name or "").strip()
    website = str(website or "").strip()
    if not business_name or not website or not _host(website):
        return {
            "recovered": False,
            "identity": None,
            "sources_tried": [],
            "evidence": [],
        }

    evidence_rows: list[IdentityEvidence] = []
    sources_tried: list[str] = []

    # 1. Search Fabric discovers first-party people pages the crawler may not
    # have reached from normal navigation.
    domain = _host(website)
    queries = (
        f'site:{domain} "{business_name}" owner founder president',
        f'site:{domain} "{business_name}" team leadership',
    )
    seen_urls: set[str] = set()
    for query in queries:
        sources_tried.append("search_fabric")
        result = search(query, num=max(1, min(max_search_results, 10)))
        for organic in result.get("organic") or []:
            if not isinstance(organic, dict):
                continue
            link = str(organic.get("link") or "").strip()
            if (
                not link
                or link in seen_urls
                or not _same_host(link, website)
            ):
                continue
            seen_urls.add(link)
            probe = probe_site(
                link,
                max_pages=3,
                request_timeout=5.0,
                time_budget_seconds=15.0,
                page_priority="people",
            )
            if isinstance(probe, dict) and probe.get("ok") is True:
                evidence_rows.extend(_rank_people(probe, website))

    # 2. Official license records can provide a named professional tied to the
    # business. Treat that person as a search seed only; first-party evidence
    # must still show a commercial decision role before promotion.
    state_hint = _state_hint(metro)
    license_seeds: list[dict[str, Any]] = []
    if state_hint:
        sources_tried.append("official_license_registry")
        try:
            license_seeds = find_official_license_principals(
                company_name=business_name,
                state=state_hint,
            )
        except Exception:
            license_seeds = []
        for seed in license_seeds:
            person_name = str(seed.get("person_name") or "").strip()
            if not person_name:
                continue
            sources_tried.append("search_fabric")
            result = search(
                f'site:{domain} "{person_name}"',
                num=max(1, min(max_search_results, 10)),
            )
            for organic in result.get("organic") or []:
                if not isinstance(organic, dict):
                    continue
                link = str(organic.get("link") or "").strip()
                if (
                    not link
                    or link in seen_urls
                    or not _same_host(link, website)
                ):
                    continue
                seen_urls.add(link)
                probe = probe_site(
                    link,
                    max_pages=3,
                    request_timeout=5.0,
                    time_budget_seconds=15.0,
                    page_priority="people",
                )
                if not isinstance(probe, dict) or probe.get("ok") is not True:
                    continue
                for row in _rank_people(probe, website):
                    if row.name.casefold() == person_name.casefold():
                        evidence_rows.append(row)

    # 3. UK Companies House provides authoritative company/officer
    # association. Officers are search seeds only: a Companies House
    # directorship does not by itself prove commercial buyer authority.
    companies_house_seeds: list[dict[str, Any]] = []
    if _is_uk_context(metro, website):
        sources_tried.append("companies_house")
        try:
            companies_house_seeds = find_companies_house_principals(
                company_name=business_name,
            )
        except Exception:
            companies_house_seeds = []

        for seed in companies_house_seeds:
            person_name = str(seed.get("person_name") or "").strip()
            if not person_name:
                continue
            sources_tried.append("search_fabric")
            result = search(
                f'site:{domain} "{person_name}"',
                num=max(1, min(max_search_results, 10)),
            )
            for organic in result.get("organic") or []:
                if not isinstance(organic, dict):
                    continue
                link = str(organic.get("link") or "").strip()
                if (
                    not link
                    or link in seen_urls
                    or not _same_host(link, website)
                ):
                    continue
                seen_urls.add(link)
                probe = probe_site(
                    link,
                    max_pages=3,
                    request_timeout=5.0,
                    time_budget_seconds=15.0,
                    page_priority="people",
                )
                if not isinstance(probe, dict) or probe.get("ok") is not True:
                    continue
                for row in _rank_people(probe, website):
                    if row.name.casefold() == person_name.casefold():
                        evidence_rows.append(row)

    # 4. Public registry lookup contributes only when the scraper itself
    # returns an explicit owner name. No inference from company names.
    sources_tried.append("registry_scraper")
    try:
        registry = RegistryScraper(timeout=8, rate_limit_seconds=0.2).search(
            business_name,
            _state_hint(metro),
        )
        for record in registry.records:
            owner = str(record.owner_name or "").strip()
            if not owner or float(record.confidence or 0.0) < 0.90:
                continue
            evidence_rows.append(IdentityEvidence(
                name=owner,
                title="owner",
                source=f"empire_registry:{record.source}",
                source_url=str(record.source_url or "").strip(),
                confidence=float(record.confidence),
                first_party=False,
                authoritative_registry=True,
            ))
    except Exception:
        pass

    # Deduplicate and prefer first-party high-confidence evidence, then
    # authoritative registry evidence.
    unique: dict[tuple[str, str], IdentityEvidence] = {}
    for row in evidence_rows:
        key = (row.name.casefold(), row.title.casefold())
        current = unique.get(key)
        if current is None or row.confidence > current.confidence:
            unique[key] = row

    ranked = sorted(
        unique.values(),
        key=lambda row: (
            not row.first_party,
            not row.authoritative_registry,
            -row.confidence,
            row.name.casefold(),
        ),
    )
    best = ranked[0] if ranked else None
    return {
        "recovered": best is not None,
        "identity": best.as_dict() if best else None,
        "sources_tried": sorted(set(sources_tried)),
        "evidence": [row.as_dict() for row in ranked[:10]],
        "license_seeds": license_seeds,
        "companies_house_seeds": companies_house_seeds,
        "outbound_actions": False,
        "guessed_identity": False,
        "guessed_email": False,
    }
