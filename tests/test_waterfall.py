"""Tests for the Waterfall data provider orchestrator."""
from unittest.mock import MagicMock, patch

import pytest
from empire_os.waterfall import (
    ApolloProvider,
    EmpireHunterProvider,
    HunterProvider,
    InternalScraperProvider,
    LeadContact,
    PeopleDataLabsProvider,
    ValidationGate,
    Waterfall,
    WaterfallResult,
    build_default_waterfall,
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

    def test_retired_external_providers_remain_unavailable(self):
        for provider_class in (
            ApolloProvider,
            PeopleDataLabsProvider,
            HunterProvider,
        ):
            p = _make_configured(provider_class)
            assert p.is_available() is False
            assert p.search(
                {"company": "Acme Roofing"}
            ) is None

    def test_empire_hunter_is_native_and_available(self):
        assert EmpireHunterProvider().is_available() is True

    def test_internal_scraper_disabled_until_real_implementation(self):
        p = InternalScraperProvider()
        assert p.is_available() is False
        assert p.search({"company": "Acme"}) is None


class TestValidationGate:
    def test_validates_bound_email_and_confidence(self):
        gate = ValidationGate(min_confidence=0.7)
        bound = {"bound_to_decision_maker": True}
        assert gate.validate(LeadContact(email="a@b.com", confidence=0.9, raw=bound)) is True
        assert gate.validate(LeadContact(email="a@b.com", confidence=0.5, raw=bound)) is False
        assert gate.validate(LeadContact(email="", confidence=0.9, raw=bound)) is False
        assert gate.validate(LeadContact(email="not-an-email", confidence=0.9, raw=bound)) is False
        assert gate.validate(LeadContact(email="a@b.com", confidence=0.9, raw={})) is False

    def test_custom_threshold_can_still_require_binding(self):
        gate = ValidationGate(min_confidence=0.5)
        assert gate.validate(LeadContact(email="a@b.com", confidence=0.6,
                                         raw={"bound_to_decision_maker": True})) is True


class _StubProvider:
    def __init__(
        self,
        name,
        result=None,
        *,
        available=True,
        cost_cents=0,
    ):
        self.name = name
        self.result = result
        self.available = available
        self.cost_cents = cost_cents

    def is_available(self):
        return self.available

    def search(self, lead_info):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


class TestWaterfall:
    def test_first_provider_wins(self):
        first = _StubProvider(
            "first",
            LeadContact(
                email="jane@acme.test",
                confidence=0.95,
                source="first",
                raw={"bound_to_decision_maker": True},
            ),
            cost_cents=2,
        )
        second = _StubProvider("second")
        wf = Waterfall(providers=[first, second])
        result = wf.enrich({"company": "Acme"})
        assert result.success is True
        assert result.final_provider == "first"
        assert result.providers_tried == ["first"]
        assert result.cost_cents == 2

    def test_falls_through_to_next_provider(self):
        first = _StubProvider("first", None)
        second = _StubProvider(
            "second",
            LeadContact(
                email="jane@acme.test",
                confidence=0.9,
                source="second",
                raw={"bound_to_decision_maker": True},
            ),
        )
        result = Waterfall(
            providers=[first, second]
        ).enrich({"company": "Acme"})
        assert result.success is True
        assert result.final_provider == "second"
        assert result.providers_tried == ["first", "second"]

    def test_unavailable_provider_is_skipped(self):
        retired = _StubProvider(
            "retired_external",
            available=False,
        )
        native = _StubProvider(
            "native",
            LeadContact(
                email="jane@acme.test",
                confidence=0.95,
                raw={"bound_to_decision_maker": True},
            ),
        )
        result = Waterfall(
            providers=[retired, native]
        ).enrich({"company": "Acme"})
        assert result.success is True
        assert result.providers_tried == ["native"]

    def test_failure_when_all_results_are_invalid(self):
        invalid = _StubProvider(
            "invalid",
            LeadContact(email="", confidence=0.5),
        )
        result = Waterfall(
            providers=[invalid]
        ).enrich({"company": "Acme"})
        assert result.success is False
        assert result.error

    def test_metrics_tracking(self):
        native = _StubProvider(
            "native",
            LeadContact(
                email="jane@acme.test",
                confidence=0.95,
                raw={"bound_to_decision_maker": True},
            ),
            cost_cents=1,
        )
        wf = Waterfall(providers=[native])
        for company in ("A", "B", "C"):
            wf.enrich({"company": company})
        assert wf.metrics["total_runs"] == 3
        assert wf.metrics["successes"] == 3
        assert wf.metrics["by_provider"]["native"]["wins"] == 3
        assert wf.metrics["by_provider"]["native"]["cost_cents"] == 3

    def test_provider_exception_doesnt_crash(self):
        broken = _StubProvider(
            "broken",
            RuntimeError("native source down"),
        )
        fallback = _StubProvider(
            "fallback",
            LeadContact(
                email="jane@acme.test",
                confidence=0.95,
                raw={"bound_to_decision_maker": True},
            ),
        )
        result = Waterfall(
            providers=[broken, fallback]
        ).enrich({"company": "Acme"})
        assert result.success is True
        assert result.final_provider == "fallback"


class TestFactory:
    def test_default_waterfall_is_internal_only(self):
        wf = build_default_waterfall()
        names = [provider.name for provider in wf.providers]
        assert names == [
            "registry_scraper",
            "site_crawler",
            "empire_hunter",
        ]
        assert not {"apollo", "pdl", "hunter"} & set(names)
        assert wf.gate.min_confidence == 0.90
        assert wf.gate.require_bound_contact is True
