"""Tests for the Waterfall data provider orchestrator."""
from unittest.mock import MagicMock, patch

import pytest
from empire_os.waterfall import (
    ApolloProvider, PeopleDataLabsProvider, HunterProvider,
    InternalScraperProvider, ValidationGate, Waterfall,
    LeadContact, WaterfallResult, build_default_waterfall,
)


def _make_configured(provider_class, api_key="test-key"):
    """Bypass the env-var lookup for testing."""
    p = provider_class(api_key=api_key)
    return p


class TestLeadContact:
    def test_defaults(self):
        c = LeadContact(email="a@b.com")
        assert c.email == "a@b.com"
        assert c.confidence == 0.0
        assert c.source == ""

    def test_to_dict(self):
        c = LeadContact(email="x@y.com", company="Acme", confidence=0.9, source="apollo")
        d = c.__dict__
        assert d["email"] == "x@y.com"
        assert d["confidence"] == 0.9


class TestProviders:
    def test_apollo_unconfigured(self):
        with patch.dict("os.environ", {}, clear=True):
            p = ApolloProvider()
            assert p.is_configured is False
            assert p.search({"company": "Acme"}) is None

    def test_apollo_configured(self):
        p = _make_configured(ApolloProvider)
        result = p.search({"company": "Acme Roofing", "phone": "555-1234"})
        assert result is not None
        assert result.source == "apollo"
        assert result.confidence > 0.7
        assert "@" in result.email

    def test_pdl_configured(self):
        p = _make_configured(PeopleDataLabsProvider)
        result = p.search({"company": "Acme"})
        assert result.source == "pdl"

    def test_hunter_configured(self):
        p = _make_configured(HunterProvider)
        result = p.search({"company": "Acme"})
        assert result.source == "hunter"

    def test_internal_scraper_always_available(self):
        p = InternalScraperProvider()
        assert p.is_available() is True
        result = p.search({"company": "Acme"})
        assert result.source == "internal_scraper"
        assert result.confidence < 0.7  # low confidence


class TestValidationGate:
    def test_validates_email_and_confidence(self):
        gate = ValidationGate(min_confidence=0.7)
        assert gate.validate(LeadContact(email="a@b.com", confidence=0.9)) is True
        assert gate.validate(LeadContact(email="a@b.com", confidence=0.5)) is False
        assert gate.validate(LeadContact(email="", confidence=0.9)) is False
        assert gate.validate(LeadContact(email="not-an-email", confidence=0.9)) is False

    def test_custom_threshold(self):
        gate = ValidationGate(min_confidence=0.5)
        assert gate.validate(LeadContact(email="a@b.com", confidence=0.6)) is True


class TestWaterfall:
    def test_first_provider_wins(self):
        """If the first provider returns a valid result, no others are tried."""
        apollo = _make_configured(ApolloProvider)
        pdl = _make_configured(PeopleDataLabsProvider)
        wf = Waterfall(providers=[apollo, pdl])
        result = wf.enrich({"company": "Acme"})
        assert result.success is True
        assert result.final_provider == "apollo"
        assert result.providers_tried == ["apollo"]
        assert result.validated is True
        assert result.cost_cents == 8  # apollo cost

    def test_falls_through_to_next_provider(self):
        """If first provider fails, second is tried."""
        apollo = _make_configured(ApolloProvider)
        # Make apollo return None
        apollo.search = MagicMock(return_value=None)
        pdl = _make_configured(PeopleDataLabsProvider)
        wf = Waterfall(providers=[apollo, pdl])
        result = wf.enrich({"company": "Acme"})
        assert result.success is True
        assert result.final_provider == "pdl"
        assert result.providers_tried == ["apollo", "pdl"]

    def test_falls_through_to_internal_scraper(self):
        """If all real providers fail, internal scraper returns low-confidence."""
        apollo = _make_configured(ApolloProvider)
        apollo.search = MagicMock(return_value=None)
        scraper = InternalScraperProvider()
        # Default gate is 0.7, scraper returns 0.45 → should fail validation
        wf = Waterfall(providers=[apollo, scraper], gate=ValidationGate(min_confidence=0.4))
        # Lower threshold so scraper passes
        wf.gate = ValidationGate(min_confidence=0.4)
        result = wf.enrich({"company": "Acme"})
        assert result.success is True
        assert result.final_provider == "internal_scraper"

    def test_failure_when_all_providers_return_invalid(self):
        apollo = _make_configured(ApolloProvider)
        apollo.search = MagicMock(return_value=LeadContact(email="", confidence=0.5))
        scraper = InternalScraperProvider()
        scraper.search = MagicMock(return_value=None)
        wf = Waterfall(providers=[apollo, scraper])
        result = wf.enrich({"company": "Acme"})
        assert result.success is False
        assert result.error != ""

    def test_skips_unconfigured_providers(self):
        apollo = _make_configured(ApolloProvider)
        # Hunter is NOT configured
        with patch.dict("os.environ", {}, clear=True):
            hunter = HunterProvider()
            assert hunter.is_configured is False
        wf = Waterfall(providers=[apollo, hunter])
        result = wf.enrich({"company": "Acme"})
        assert result.success is True
        assert "hunter" not in result.providers_tried

    def test_metrics_tracking(self):
        apollo = _make_configured(ApolloProvider)
        pdl = _make_configured(PeopleDataLabsProvider)
        wf = Waterfall(providers=[apollo, pdl])
        wf.enrich({"company": "A"})
        wf.enrich({"company": "B"})
        wf.enrich({"company": "C"})
        assert wf.metrics["total_runs"] == 3
        assert wf.metrics["successes"] == 3
        assert wf.metrics["by_provider"]["apollo"]["wins"] == 3
        assert wf.metrics["by_provider"]["apollo"]["cost_cents"] == 24  # 8 × 3

    def test_provider_exception_doesnt_crash(self):
        apollo = _make_configured(ApolloProvider)
        apollo.search = MagicMock(side_effect=RuntimeError("API down"))
        pdl = _make_configured(PeopleDataLabsProvider)
        wf = Waterfall(providers=[apollo, pdl])
        result = wf.enrich({"company": "Acme"})
        # Apollo crashed, pdl should win
        assert result.success is True
        assert result.final_provider == "pdl"


class TestFactory:
    def test_build_default_waterfall(self):
        wf = build_default_waterfall()
        # 7 providers: self-built first (registry, site, social, internal),
        # then paid (apollo, pdl, hunter) as fallbacks
        assert len(wf.providers) == 7
        assert wf.providers[0].name == "registry_scraper"
        assert wf.providers[1].name == "site_crawler"
        assert wf.gate.min_confidence == 0.7

    def test_self_built_providers_come_first(self):
        """Free providers should be tried before paid ones."""
        wf = build_default_waterfall()
        names = [p.name for p in wf.providers]
        # Self-built should be first 2
        assert "registry_scraper" in names[:2]
        assert "site_crawler" in names[:2]
        # Paid providers (if unconfigured) should not block self-built wins
        # but should appear in the list
        assert "apollo" in names