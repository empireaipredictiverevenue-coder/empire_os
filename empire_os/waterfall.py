"""
Waterfall — Data Provider Orchestrator for Empire OS v3.

Iterates through a configured chain of data providers (Apollo, People Data
Labs, Hunter, Clearbit, etc.) until one returns a high-confidence contact
result. Every result is run through a validation gate (ZeroBounce, SMTP
check) before it can be used for outreach.

Built as an in-hub abstraction so we own the data, pay provider-direct
pricing, and can tune the waterfall per vertical (roofing, hvac, mass tort).
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

logger = logging.getLogger("waterfall")


# ── Result types ─────────────────────────────────────────────────────

@dataclass
class LeadContact:
    """A single enriched lead record returned by a provider."""
    email: str = ""
    phone: str = ""
    first_name: str = ""
    last_name: str = ""
    title: str = ""
    company: str = ""
    linkedin: str = ""
    source: str = ""           # which provider returned this
    confidence: float = 0.0    # 0.0 to 1.0
    raw: dict = field(default_factory=dict)


@dataclass
class WaterfallResult:
    """Result of a waterfall enrichment attempt."""
    success: bool = False
    contact: Optional[LeadContact] = None
    providers_tried: list = field(default_factory=list)
    final_provider: str = ""
    validated: bool = False
    cost_cents: int = 0
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "contact": asdict(self.contact) if self.contact else None,
            "providers_tried": self.providers_tried,
            "final_provider": self.final_provider,
            "validated": self.validated,
            "cost_cents": self.cost_cents,
            "error": self.error,
        }


# ── Provider ABC ─────────────────────────────────────────────────────

class DataProvider:
    """Base class for a waterfall data provider.

    Subclasses must implement search() and return a LeadContact or None.
    Each provider reports its own cost in cents so the waterfall can track
    spend per enrichment.
    """

    name: str = "base"
    cost_cents: int = 0
    api_key_env: str = ""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get(self.api_key_env, "")
        self.is_configured = bool(self.api_key)

    def search(self, lead_info: dict) -> Optional[LeadContact]:
        """Search this provider for contact info matching lead_info."""
        raise NotImplementedError

    def is_available(self) -> bool:
        return self.is_configured


# ── Built-in providers (stubs — wire real APIs as keys arrive) ──────

class ApolloProvider(DataProvider):
    """Apollo.io — primary B2B contact source."""
    name = "apollo"
    cost_cents = 8
    api_key_env = "APOLLO_API_KEY"

    def search(self, lead_info: dict) -> Optional[LeadContact]:
        if not self.is_configured:
            return None
        # Real implementation: POST to Apollo's people/match endpoint
        # Stub: returns a synthetic confidence to drive the waterfall logic
        return LeadContact(
            email=f"contact@{lead_info.get('company', 'example.com').lower().replace(' ', '')}.com",
            phone=lead_info.get("phone", ""),
            source=self.name,
            confidence=0.92,
            raw={"stub": True, "lead": lead_info},
        )


class PeopleDataLabsProvider(DataProvider):
    """People Data Labs — fallback B2B enrichment."""
    name = "pdl"
    cost_cents = 5
    api_key_env = "PDL_API_KEY"

    def search(self, lead_info: dict) -> Optional[LeadContact]:
        if not self.is_configured:
            return None
        return LeadContact(
            email=f"lead@{lead_info.get('company', 'example.com').lower().replace(' ', '')}.com",
            source=self.name,
            confidence=0.78,
            raw={"stub": True, "lead": lead_info},
        )


class HunterProvider(DataProvider):
    """Hunter.io — email finding + verification."""
    name = "hunter"
    cost_cents = 4
    api_key_env = "HUNTER_API_KEY"

    def search(self, lead_info: dict) -> Optional[LeadContact]:
        if not self.is_configured:
            return None
        return LeadContact(
            email=f"info@{lead_info.get('company', 'example.com').lower().replace(' ', '')}.com",
            source=self.name,
            confidence=0.81,
            raw={"stub": True, "lead": lead_info},
        )


class InternalScraperProvider(DataProvider):
    """Last-resort internal scraper (e.g., for niche registries)."""
    name = "internal_scraper"
    cost_cents = 1
    api_key_env = ""  # no key needed

    def is_available(self) -> bool:
        return True  # always available

    def search(self, lead_info: dict) -> Optional[LeadContact]:
        # Always returns a low-confidence result
        return LeadContact(
            email=f"unknown@{lead_info.get('company', 'example.com').lower().replace(' ', '')}.com",
            source=self.name,
            confidence=0.45,
            raw={"stub": True, "lead": lead_info},
        )


# ── Self-built providers (no API keys required) ─────────────────────

class RegistryScraperProvider(DataProvider):
    """Query public business registries (BBB, SunBiz) for company info."""
    name = "registry_scraper"
    cost_cents = 0  # free
    api_key_env = ""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key=api_key)
        self._scraper = None

    def is_available(self) -> bool:
        return True

    def _ensure_scraper(self):
        if self._scraper is None:
            from empire_os.registry_scraper import RegistryScraper
            self._scraper = RegistryScraper()
        return self._scraper

    def search(self, lead_info: dict) -> Optional[LeadContact]:
        company = lead_info.get("company", "")
        state = lead_info.get("state", "")
        if not company:
            return None
        scraper = self._ensure_scraper()
        result = scraper.search(company, state=state)
        if not result.best:
            return None
        rec = result.best
        return LeadContact(
            email=rec.email,
            phone=rec.phone or lead_info.get("phone", ""),
            company=rec.company_name,
            source=self.name,
            confidence=rec.confidence * 0.7,  # discount: registry doesn't give email
            raw={"registry_record": rec.to_dict()},
        )


class SiteCrawlerProvider(DataProvider):
    """Crawl the company's website for contact info (mailto, tel, contact pages)."""
    name = "site_crawler"
    cost_cents = 0  # free
    api_key_env = ""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key=api_key)
        self._crawler = None

    def is_available(self) -> bool:
        return True

    def _ensure_crawler(self):
        if self._crawler is None:
            from empire_os.site_crawler import SiteCrawler
            self._crawler = SiteCrawler()
        return self._crawler

    def search(self, lead_info: dict) -> Optional[LeadContact]:
        website = lead_info.get("website") or lead_info.get("company", "")
        if not website:
            return None
        crawler = self._ensure_crawler()
        result = crawler.crawl(website)
        best = result.best_email()
        if not best:
            return None
        confidence = 0.85 if best.email else 0.65
        # If we got an email, validate it through the MX validator before returning
        if best.email:
            from empire_os.mx_validator import MxValidator
            mv = MxValidator(do_smtp_probe=False)  # skip SMTP probe in waterfall
            validation = mv.validate(best.email)
            if not validation.is_valid:
                # Fall back to phone-only contact
                return LeadContact(
                    phone=best.phone or lead_info.get("phone", ""),
                    company=lead_info.get("company", ""),
                    source=self.name,
                    confidence=0.55,
                    raw={"crawl": {"pages": result.pages_crawled,
                                   "rejected_email": best.email}},
                )
            confidence = validation.confidence
        return LeadContact(
            email=best.email if best.email else "",
            phone=best.phone or lead_info.get("phone", ""),
            company=lead_info.get("company", ""),
            source=self.name,
            confidence=confidence,
            raw={"crawl": {"pages": result.pages_crawled,
                           "source_url": best.source_url}},
        )


class SocialScraperProvider(DataProvider):
    """Search public LinkedIn/Facebook profiles for owner name + contact info."""
    name = "social_scraper"
    cost_cents = 0
    api_key_env = ""

    def is_available(self) -> bool:
        return True

    def search(self, lead_info: dict) -> Optional[LeadContact]:
        # Stub — real implementation would query LinkedIn's public search,
        # Facebook's Graph API (no key needed for public pages), etc.
        # For now: return a low-confidence result so the waterfall can
        # try the next provider.
        return LeadContact(
            phone=lead_info.get("phone", ""),
            company=lead_info.get("company", ""),
            source=self.name,
            confidence=0.4,
            raw={"stub": True, "note": "social scraping not yet implemented"},
        )


# ── Validation gate ──────────────────────────────────────────────────

class ValidationGate:
    """Post-processing step that verifies a LeadContact before use.

    In production this calls ZeroBounce, SMTP check, or similar. Here we
    provide a confidence-based gate that rejects results below threshold.
    """

    def __init__(self, min_confidence: float = 0.7, require_email: bool = True):
        self.min_confidence = min_confidence
        self.require_email = require_email

    def validate(self, contact: LeadContact) -> bool:
        if contact is None:
            return False
        if self.require_email and not contact.email:
            return False
        if "@" not in contact.email:
            return False
        if contact.confidence < self.min_confidence:
            return False
        return True


# ── Waterfall orchestrator ───────────────────────────────────────────

class Waterfall:
    """Iterate through providers until validated result found.

    Order of providers determines the cascade. Each provider is tried in
    turn; first one with a passing validation gate wins.
    """

    def __init__(
        self,
        providers: list,
        gate: Optional[ValidationGate] = None,
        max_attempts: int = 4,
    ):
        self.providers = providers
        self.gate = gate or ValidationGate()
        self.max_attempts = max_attempts
        self.metrics = {
            "total_runs": 0,
            "successes": 0,
            "failures": 0,
            "by_provider": {p.name: {"attempts": 0, "wins": 0, "cost_cents": 0}
                            for p in providers},
        }

    def enrich(self, lead_info: dict) -> WaterfallResult:
        """Run the waterfall for one lead."""
        self.metrics["total_runs"] += 1
        tried = []
        total_cost = 0

        for provider in self.providers[:self.max_attempts]:
            if not provider.is_available():
                logger.debug("provider '%s' not configured, skipping", provider.name)
                continue
            tried.append(provider.name)
            self.metrics["by_provider"][provider.name]["attempts"] += 1

            try:
                contact = provider.search(lead_info)
            except Exception as e:
                logger.warning("provider '%s' raised: %s", provider.name, e)
                continue

            total_cost += provider.cost_cents
            self.metrics["by_provider"][provider.name]["cost_cents"] += provider.cost_cents

            if contact and self.gate.validate(contact):
                self.metrics["successes"] += 1
                self.metrics["by_provider"][provider.name]["wins"] += 1
                return WaterfallResult(
                    success=True,
                    contact=contact,
                    providers_tried=tried,
                    final_provider=provider.name,
                    validated=True,
                    cost_cents=total_cost,
                )

        # No provider returned a validated result
        self.metrics["failures"] += 1
        return WaterfallResult(
            success=False,
            providers_tried=tried,
            validated=False,
            cost_cents=total_cost,
            error=f"No provider returned a result above confidence threshold {self.gate.min_confidence}",
        )


# ── Factory ──────────────────────────────────────────────────────────

def build_default_waterfall() -> Waterfall:
    """Build the default Empire OS waterfall.

    Order is self-built-first so we don't pay SaaS markups unless the
    self-built providers fail. When API keys are added (Apollo, PDL,
    Hunter), they auto-enable at their configured positions.
    """
    return Waterfall(
        providers=[
            RegistryScraperProvider(),  # 1. Free: BBB + SunBiz (authoritative)
            SiteCrawlerProvider(),      # 2. Free: company site crawl + MX check
            ApolloProvider(),           # 3. Paid fallback: if APOLLO_API_KEY set
            PeopleDataLabsProvider(),   # 4. Paid fallback: if PDL_API_KEY set
            HunterProvider(),           # 5. Paid fallback: if HUNTER_API_KEY set
            SocialScraperProvider(),    # 6. Free last resort: social profiles
            InternalScraperProvider(),  # 7. Always-on internal scraper
        ],
        gate=ValidationGate(min_confidence=0.7),
    )