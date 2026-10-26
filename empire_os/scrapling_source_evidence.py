"""Scrapling-backed, offline, source-governed extraction proposals.

Never fetches a URL, registers a live source, writes EmpireDB, or offers lead
inventory.  A separate reviewed collector may pass already-retrieved HTML.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from ipaddress import ip_address
from typing import Any, Callable
from urllib.parse import urlparse, urljoin
import re

from empire_os.source_intelligence import SOURCES

MAX_ROWS = 25
ALLOWED_SOURCE_USE = "internal_acquisition"


class EvidenceSourceHold(ValueError):
    """Source evidence may not be promoted to an extraction proposal."""


class ScraplingNotInstalled(RuntimeError):
    """Optional parser absent; do not silently switch parsing engines."""


def _public_url(value: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise EvidenceSourceHold("url_not_clean")
    parsed = urlparse(value)
    try:
        invalid_port = bool(parsed.port)
    except ValueError as exc:
        raise EvidenceSourceHold("unsafe_url") from exc
    if (parsed.scheme != "https" or not parsed.hostname or
            parsed.username or parsed.password or invalid_port or
            len(value) > 2048 or "\\" in value):
        raise EvidenceSourceHold("unsafe_url")
    host = parsed.hostname.lower().rstrip(".")
    if (host == "localhost" or host.endswith((".local", ".internal", ".localhost"))
            or "." not in host):
        raise EvidenceSourceHold("non_public_hostname")
    try:
        ip_address(host)
    except ValueError:
        if not re.fullmatch(r"[a-z0-9.-]+", host):
            raise EvidenceSourceHold("invalid_hostname")
    else:
        raise EvidenceSourceHold("ip_literal_disallowed")
    return value


@dataclass(frozen=True)
class ReviewedRecipe:
    source_id: str
    source_url: str
    niche: str
    metro: str
    row_css: str
    name_css: str
    website_css: str = ""
    field_phone_css: str = ""
    max_rows: int = 25
    terms_reviewed: bool = False
    robots_reviewed: bool = False
    privacy_reviewed: bool = False
    review_evidence_refs: tuple[str, ...] = ()

    def validate(self) -> Any:
        if self.source_id not in SOURCES:
            raise EvidenceSourceHold("source_not_registered")
        contract = SOURCES[self.source_id]
        if ALLOWED_SOURCE_USE not in contract.allowed_uses:
            raise EvidenceSourceHold("internal_use_not_licensed")
        if not (self.terms_reviewed and self.robots_reviewed
                and self.privacy_reviewed):
            raise EvidenceSourceHold("governance_review_missing")
        if (len(self.review_evidence_refs) < 3
                or any(not isinstance(ref, str) or not ref.strip()
                       for ref in self.review_evidence_refs)):
            raise EvidenceSourceHold("review_evidence_refs_missing")
        if type(self.max_rows) is not int or not 1 <= self.max_rows <= MAX_ROWS:
            raise EvidenceSourceHold("unbounded_extraction")
        for value in (self.niche, self.metro, self.row_css, self.name_css):
            if not isinstance(value, str) or not value.strip() or len(value) > 150:
                raise EvidenceSourceHold("missing_scope_or_selector")
        url = _public_url(self.source_url)
        registered = urlparse(contract.url)
        supplied = urlparse(url)
        # A source-specific adapter needs explicit new policy for a different host.
        if supplied.hostname != registered.hostname:
            raise EvidenceSourceHold("url_not_in_registered_source_host")
        if self.website_css and len(self.website_css) > 150:
            raise EvidenceSourceHold("invalid_selector")
        if self.field_phone_css and len(self.field_phone_css) > 150:
            raise EvidenceSourceHold("invalid_selector")
        return contract


def _extract_first(row: Any, css: str) -> str:
    if not css:
        return ""
    value = row.css(css).get()
    return " ".join(str(value or "").split())[:500]


def _website(value: str, source_url: str) -> str:
    if not value:
        return ""
    try:
        # Only absolute HTTPS or source-relative HTTPS; never expose internal URL.
        candidate = urljoin(source_url, value)
        _public_url(candidate)
        return candidate
    except (EvidenceSourceHold, ValueError):
        return ""


def _business_key(name: str, site: str, niche: str, metro: str) -> str:
    normalized = " ".join(name.casefold().split())
    return "|".join((normalized, site.lower().rstrip("/"), niche.casefold(), metro.casefold()))


def extract_reviewed_page(
    *, recipe: ReviewedRecipe, html: str, observed_at: datetime,
    selector_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    """Build evidence-only prospects; caller must not count them as owned leads.

    Scraped row counts are *not* unique canonical EmpireDB prospect counts.
    Intent, valid email, customer consent and buyer capacity are NOT inferred.
    """
    contract = recipe.validate()
    if observed_at.tzinfo is None:
        raise EvidenceSourceHold("timestamp_not_timezone_aware")
    if not isinstance(html, str) or not html.strip() or len(html) > 2_000_000:
        raise EvidenceSourceHold("invalid_bounded_document")
    if selector_factory is None:
        try:
            from scrapling.parser import Selector
        except ImportError as exc:
            raise ScraplingNotInstalled("install scrapling in isolated optional runtime") from exc
        selector_factory = Selector
    page = selector_factory(html, url=recipe.source_url)
    rows = page.css(recipe.row_css)
    results = []
    seen = set()
    inspected = 0
    # Bounded work: cap raw inspected rows, not only accepted output records.
    for row in rows:
        if inspected >= recipe.max_rows:
            break
        inspected += 1
        name = _extract_first(row, recipe.name_css)
        if not name or len(name) < 3:
            continue
        site = _website(_extract_first(row, recipe.website_css), recipe.source_url)
        phone = _extract_first(row, recipe.field_phone_css)
        key = _business_key(name, site, recipe.niche, recipe.metro)
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "business_name": name,
            "source_link_observed": site,
            "business_website_verified": False,
            "public_phone_observed": phone,
            "niche_observed": recipe.niche,
            "metro_observed": recipe.metro,
            "source_id": recipe.source_id,
            "source_url": recipe.source_url,
            "data_use": ALLOWED_SOURCE_USE,
            "commercial_resale_authorized": False,
            "quality": "unverified_source_observation",
            "canonical_prospect_id": None,
        })
    return {
        "schema_version": "empire.scrapling_source_evidence.v1",
        "mode": "OFFLINE_REVIEW_ONLY",
        "source_id": recipe.source_id,
        "source_licence": contract.licence,
        "review_evidence_refs": list(recipe.review_evidence_refs),
        "source_raw_resale_policy": contract.raw_resale_allowed,
        "source_url": recipe.source_url,
        "observed_at": observed_at.astimezone(timezone.utc).isoformat(),
        "content_sha256": sha256(html.encode("utf-8")).hexdigest(),
        "rows_inspected_bounded": inspected,
        "records_observed": len(results),
        "bounded_by_recipe": inspected == recipe.max_rows,
        "canonical_empiredb_writes": False,
        "outbound_sent": False,
        "live_network_access": False,
        "sellable_inventory_verified": False,
        "buyer_intent_verified": False,
        "privacy_rights_require_separate_record_level_review": True,
        "records": results,
    }
