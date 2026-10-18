"""Offline regression tests: NewsJack intake into first-party Empire JEV traffic review."""
from __future__ import annotations

from copy import deepcopy

import pytest

from empire_os.jev_newsjack_traffic import review_newsjack_jev_traffic
from empire_os.typed_decision_provider import TypedDecisionResult

NOW = "2026-10-18T12:00:00+00:00"
PRIMARY = "https://www.gov.uk/government/news/solar-guidance"
DEST = "https://empire-ai.co.uk/industries/solar"


def signal():
    return {
        "signal_id": "news:solar:01",
        "title": "Solar installation policy update for UK businesses",
        "sector": "solar", "market": "GB",
        "primary_source_url": PRIMARY,
        "published_at": "2026-10-17T12:00:00+00:00",
        "observed_at": "2026-10-18T08:00:00+00:00",
        "evidence_refs": ["capture:official-news:01"],
        "corroboration_evidence_refs": ["capture:independent:02"],
        "independent_corroboration_verified": True,
        "destination_url": DEST,
        "destination_live_verified": True,
        "destination_evidence_refs": ["own:live:solar-page"],
        "search_observation": {
            "source_kind": "GSC", "trusted_reader_verified": True,
            "query": "solar installation UK", "impressions": 30,
            "clicks": 2, "source_ref": "gsc:row:123",
            "observed_at": "2026-10-17T09:00:00+00:00",
        },
    }


def run(signals, provider=None):
    return review_newsjack_jev_traffic(
        signals, as_of=NOW, approved_sectors=["solar", "roofing"],
        approved_markets=["GB", "US"], approved_destination_urls=[DEST],
        provider=provider,
    )


class ShadowProvider:
    provider_key = "offline-fixture"

    def __init__(self, label="content_brief", confidence=0.94, authority="none", shadow=True):
        self.label = label
        self.confidence = confidence
        self.authority = authority
        self.shadow = shadow
        self.calls = 0

    def evaluate(self, request):
        self.calls += 1
        request.validate()
        assert request.allowed_labels == ("irrelevant", "research", "content_brief")
        return TypedDecisionResult(
            provider_key=self.provider_key, model_key="synthetic-fixture",
            task_key=request.task_key, decision_schema_ref=request.decision_schema_ref,
            state_ref=request.state_ref, label=self.label,
            confidence=self.confidence, latency_ms=0,
            source_ref="fixture:shadow:1", shadow_only=self.shadow,
            execution_authority=self.authority,
        )


def test_complete_evidence_with_mock_jev_proposes_brief_not_publication():
    output = run([signal()], ShadowProvider())
    assert output["candidate_count"] == 1
    row = output["candidates"][0]
    assert row["status"] == "CONTENT_BRIEF_REVIEW"
    assert row["search_observation"]["impressions"] == 30
    assert row["destination_url"] == DEST
    assert row["content_brief_recommendation_only"] is True
    assert row["actual_visitors"] is None
    assert row["actual_revenue"] is False
    assert row["execution_authority"] == "none"
    assert output["publishing_enabled"] is False
    assert output["newsjack_installed_or_invoked"] is False


def test_real_provider_not_assumed_even_with_strong_fixture_evidence():
    row = run([signal()])["candidates"][0]
    assert row["status"] == "RESEARCH_REVIEW"
    assert "jev_shadow_decision_not_evaluated" in row["missing_evidence"]
    assert row["jev_shadow_decision"] is None


def test_stale_duplicate_or_future_news_is_held_without_inference():
    old = signal()
    old["published_at"] = "2026-09-20T00:00:00+00:00"
    future = signal()
    future["signal_id"] = "future"
    future["primary_source_url"] = "https://example.org/solar"
    future["observed_at"] = "2026-10-20T00:00:00+00:00"
    duplicate = signal()
    duplicate["signal_id"] = "duplicate"
    provider = ShadowProvider()
    rows = run([old, future, duplicate], provider)["candidates"]
    assert all(row["status"] == "HOLD_EVIDENCE" for row in rows)
    assert any("stale_news_signal" in row["missing_evidence"] for row in rows)
    assert any("duplicate_news_url" in row["missing_evidence"] for row in rows)
    assert any("future_or_inconsistent_timestamp" in row["missing_evidence"] for row in rows)
    assert provider.calls == 0


def test_source_domain_and_unapproved_market_blocked():
    a = signal()
    a["primary_source_url"] = "https://localhost/private"
    b = signal()
    b["signal_id"] = "other"
    b["primary_source_url"] = "https://example.com/story"
    b["market"] = "FR"
    assert run([a, b])["status_counts"] == {"HOLD_EVIDENCE": 2}


def test_gsc_without_reader_attestation_not_treated_as_observed():
    item = signal()
    item["search_observation"]["trusted_reader_verified"] = False
    row = run([item], ShadowProvider())["candidates"][0]
    assert row["status"] == "RESEARCH_REVIEW"
    assert row["search_observation"] is None
    assert "trusted_gsc_demand_observation_missing" in row["missing_evidence"]


def test_fake_evidence_and_non_shadow_provider_cannot_promote():
    item = signal()
    item["independent_corroboration_verified"] = False
    result = run([item], ShadowProvider())["candidates"][0]
    assert result["status"] == "RESEARCH_REVIEW"
    assert "independent_corroboration_required" in result["missing_evidence"]
    assert run([signal()], ShadowProvider(shadow=False))["candidates"][0]["status"] == "RESEARCH_REVIEW"
    assert run([signal()], ShadowProvider(authority="publish"))["candidates"][0]["status"] == "RESEARCH_REVIEW"


def test_low_confidence_or_irrelevant_is_not_content_brief():
    assert run([signal()], ShadowProvider(confidence=0.5))["candidates"][0]["status"] == "RESEARCH_REVIEW"
    assert run([signal()], ShadowProvider(label="irrelevant", confidence=0.13))["candidates"][0]["status"] == "RESEARCH_REVIEW"
    assert run([signal()], ShadowProvider(label="irrelevant"))["candidates"][0]["status"] == "NOT_RELEVANT"


def test_invalid_scope_and_unbounded_intake_rejected():
    with pytest.raises(ValueError):
        review_newsjack_jev_traffic([signal()], as_of="2026-10-18",
                                    approved_sectors=["solar"], approved_markets=["GB"])
    with pytest.raises(ValueError):
        run([signal()] * 101)
    with pytest.raises(ValueError):
        review_newsjack_jev_traffic([], as_of=NOW,
                                    approved_sectors=["solar"], approved_markets=["GB"],
                                    approved_destination_urls=["http://empire-ai.co.uk"])
    with pytest.raises(ValueError):
        review_newsjack_jev_traffic([], as_of=NOW,
                                    approved_sectors=["solar"], approved_markets=["GB"],
                                    approved_destination_urls=["https://example.org/landing"])
