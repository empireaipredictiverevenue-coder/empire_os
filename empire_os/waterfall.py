"""
Waterfall — Empire-owned contact intelligence orchestrator.

The active production chain uses only Empire-owned/public-evidence sources.
Legacy third-party provider classes remain as inert compatibility tombstones
so historical imports fail closed rather than silently calling external APIs.
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


# ── Retired external-provider compatibility tombstones ───────────────

class _RetiredExternalProvider(DataProvider):
    """Historical import compatibility; never active in production."""

    def is_available(self) -> bool:
        return False

    def search(self, lead_info: dict) -> Optional[LeadContact]:
        return None


class ApolloProvider(_RetiredExternalProvider):
    name = "apollo"
    cost_cents = 0
    api_key_env = ""


class PeopleDataLabsProvider(_RetiredExternalProvider):
    name = "pdl"
    cost_cents = 0
    api_key_env = ""


class HunterProvider(_RetiredExternalProvider):
    """Retired Hunter.io adapter. Empire Hunter is the native replacement."""

    name = "hunter"
    cost_cents = 0
    api_key_env = ""


class InternalScraperProvider(DataProvider):
    """Last-resort internal scraper (e.g., for niche registries)."""
    name = "internal_scraper"
    cost_cents = 1
    api_key_env = ""  # no key needed

    def is_available(self) -> bool:
        return False

    def search(self, lead_info: dict) -> Optional[LeadContact]:
        # Disabled until a real evidence-backed scraper exists.
        return None


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
                    raw={"bound_to_decision_maker": False,
                         "crawl": {"pages": result.pages_crawled,
                                   "rejected_email": best.email}},
                )
            confidence = validation.confidence
        return LeadContact(
            email=best.email if best.email else "",
            phone=best.phone or lead_info.get("phone", ""),
            company=lead_info.get("company", ""),
            source=self.name,
            confidence=confidence,
            raw={"bound_to_decision_maker": False,
                 "crawl": {"pages": result.pages_crawled,
                           "source_url": best.source_url}},
        )




class EmpireHunterProvider(DataProvider):
    """Empire-owned first-party decision-maker contact intelligence."""

    name = "empire_hunter"
    cost_cents = 0
    api_key_env = ""

    def is_available(self) -> bool:
        return True

    def search(self, lead_info: dict) -> Optional[LeadContact]:
        website = str(
            lead_info.get("website")
            or lead_info.get("domain")
            or ""
        ).strip()
        if not website:
            return None

        from empire_os.hunter.domain_intelligence import analyze_domain

        report = analyze_domain(website)
        confirmed = report.confirmed_contacts
        if not confirmed:
            return None

        best = max(
            confirmed,
            key=lambda item: item.confidence,
        )
        parts = str(best.person_name or "").split()
        first_name = parts[0] if parts else ""
        last_name = parts[-1] if len(parts) > 1 else ""
        return LeadContact(
            email=best.email,
            first_name=first_name,
            last_name=last_name,
            title=str(best.person_title or ""),
            company=str(
                lead_info.get("company")
                or lead_info.get("business_name")
                or ""
            ),
            source=self.name,
            confidence=best.confidence,
            raw={
                "bound_to_decision_maker": best.person_bound,
                "verification_state": best.state.value,
                "first_party": best.first_party,
                "source_url": best.source_url,
                "reasons": list(best.reasons),
                "domain_pattern": report.pattern.as_dict(),
            },
        )


class SocialScraperProvider(DataProvider):
    """Search public LinkedIn/Facebook profiles for owner name + contact info."""
    name = "social_scraper"
    cost_cents = 0
    api_key_env = ""

    def is_available(self) -> bool:
        return False

    def search(self, lead_info: dict) -> Optional[LeadContact]:
        return None


# ── Validation gate ──────────────────────────────────────────────────

class ValidationGate:
    """Post-processing gate for evidence-backed contact records.

    A contact must meet the confidence floor and, by default, carry explicit
    decision-maker binding evidence. Generic or fabricated addresses fail closed.
    """

    def __init__(self, min_confidence: float = 0.7, require_email: bool = True,
                 require_bound_contact: bool = True):
        self.min_confidence = min_confidence
        self.require_email = require_email
        self.require_bound_contact = require_bound_contact

    def validate(self, contact: LeadContact) -> bool:
        if contact is None:
            return False
        if self.require_email and not contact.email:
            return False
        if "@" not in contact.email:
            return False
        if contact.confidence < self.min_confidence:
            return False
        if self.require_bound_contact and contact.raw.get("bound_to_decision_maker") is not True:
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
    """Build the production Empire-owned contact waterfall."""
    return Waterfall(
        providers=[
            RegistryScraperProvider(),
            SiteCrawlerProvider(),
            EmpireHunterProvider(),
        ],
        gate=ValidationGate(
            min_confidence=0.90,
            require_email=True,
            require_bound_contact=True,
        ),
        max_attempts=3,
    )