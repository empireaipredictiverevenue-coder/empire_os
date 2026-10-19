"""Opt-in Scrapling extraction within Empire's OWN existing Waterfall.

No external crawling, production activation, new scheduler, database write,
consumer claimant handling, or contact verification. A pre-fetched, reviewed
business site document may be parsed as an unverified source observation.

This module only creates the existing Waterfall classes and returns conservative
LeadContact proposals; ValidationGate remains authoritative.
"""
from __future__ import annotations

from urllib.parse import urlparse

from empire_os.scrapling_contact_extractor import (
    ScraplingBusinessContactExtractor, _public_page,
)
from empire_os.site_crawler import SiteCrawler
from empire_os.waterfall import (
    DataProvider, LeadContact, Waterfall,
    RegistryScraperProvider, EmpireHunterProvider, ValidationGate,
)


class ReviewedScraplingSiteProvider(DataProvider):
    """A no-network replacement for a site's extraction step only."""

    name = "site_crawler_scrapling_offline"
    cost_cents = 0
    api_key_env = ""

    def __init__(
        self, *,
        plan: dict, html: str, source_url: str,
    ) -> None:
        super().__init__()
        self._plan = plan
        self._html = html
        self._source_url = source_url
        self._crawler = SiteCrawler(
            max_pages=1, offline_extractor=ScraplingBusinessContactExtractor(),
        )

    def is_available(self) -> bool:
        """Only a reviewed company-owned website can be parsed here."""
        plan = self._plan
        verified_site = plan.get("first_party_website_review_only")
        if (plan.get("schema_version") != "empire.waterfall_source_bridge.v1"
                or plan.get("state") != "EVIDENCE_REVIEW_READY"
                or plan.get("execution_authority") != "none"
                or plan.get("provider_execution_authorized") is not False
                or not plan.get("website_evidence_ref")):
            return False
        return (
            _public_page(self._source_url)
            and _public_page(verified_site)
            and urlparse(self._source_url).hostname == urlparse(verified_site).hostname
        )

    def search(self, lead_info: dict) -> LeadContact | None:
        if not self.is_available() or not isinstance(lead_info, dict):
            return None
        company = str(lead_info.get("company") or lead_info.get("business_name") or "").strip()
        observed = str(self._plan.get("observed_business") or "").strip()
        if not company or not observed or company.casefold() != observed.casefold():
            return None
        result = self._crawler.extract_offline_html(
            self._html, self._source_url, page_type="contact",
        )
        if result.error:
            return None
        best = result.best_email()
        if best is None:
            return None
        return LeadContact(
            email=best.email, phone=best.phone, company=company,
            source=self.name,
            # Directory / site contact discovery can never prove person-binding.
            # A role inbox is not a decision maker.
            confidence=0.60 if best.email else 0.40,
            raw={
                "bound_to_decision_maker": False,
                "verification_state": "OBSERVED_UNVERIFIED",
                "provenance_page": best.source_url,
                "source_id": self._plan.get("observed_source_id"),
                "source_document_sha256": self._plan.get("observed_document_sha256"),
                "scrapling_parser": "static_offline",
                "no_network_fetch": True,
                "page_count": result.pages_crawled,
                "commercial_authority": False,
            },
        )


class ReviewedOfflineWaterfall(Waterfall):
    """Existing Waterfall engine, explicitly disabled for active provider runs."""

    def enrich(self, lead_info: dict):
        raise PermissionError(
            "offline_source_review_is_not_permission_for_live_provider_execution"
        )

    def observe_scrapling_only(self, lead_info: dict) -> dict:
        """Inspect the static site snapshot and its existing ValidationGate."""
        provider = next(
            (p for p in self.providers if isinstance(p, ReviewedScraplingSiteProvider)),
            None,
        )
        if provider is None or not provider.is_available():
            raise ValueError("scrapling offline provider unavailable")
        candidate = provider.search(lead_info)
        return {
            "mode": "OFFLINE_REVIEW_ONLY",
            "observed": candidate is not None,
            "provider_name": provider.name,
            "existing_gate_would_pass": bool(candidate and self.gate.validate(candidate)),
            "contact_promotion_authorized": False,
            "outbound_authorized": False,
            "canonical_database_writes": False,
            "execution_authority": "none",
        }


def build_reviewed_scrapling_waterfall(
    *, source_report: dict, review, html: str, website_page_url: str,
    observed_at=None,
) -> tuple[ReviewedOfflineWaterfall, dict]:
    """Build EXISTING Waterfall with one offline parser enhancement.

    Must pass source review and independent company-owned-site review; even
    then no implicit call to .enrich(), no outbound, and no DB writes.
    """
    from empire_os.waterfall_source_bridge import build_waterfall_source_review

    plan = build_waterfall_source_review(
        source_report, record_index=0, review=review, now=observed_at,
    )
    if plan.get("state") != "EVIDENCE_REVIEW_READY":
        raise ValueError("governed source evidence review held")
    provider = ReviewedScraplingSiteProvider(
        plan=plan, html=html, source_url=website_page_url
    )
    if not provider.is_available():
        raise ValueError("source page not under verified owned company website")
    # Map reviewed provider order into existing native provider components,
    # replacing only the site extraction step. Running provider .enrich() is
    # disabled on this preview class, so this cannot accidentally hit HTTP.
    candidates = {
        "registry_scraper": RegistryScraperProvider(),
        "site_crawler": provider,
        "empire_hunter": EmpireHunterProvider(),
    }
    order = plan.get("provider_order_review_only") or []
    if set(order) != set(candidates) or len(order) != len(candidates):
        raise ValueError("reviewed provider order is incomplete or untrusted")
    flow = ReviewedOfflineWaterfall(
        providers=[candidates[name] for name in order],
        gate=ValidationGate(
            min_confidence=0.90,
            require_email=True,
            require_bound_contact=True,
        ),
        max_attempts=3,
    )
    return flow, plan
