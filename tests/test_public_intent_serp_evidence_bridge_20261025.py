"""SERP evidence attaches only to valid original Keyword Universe idea."""
from datetime import datetime, timezone, timedelta
import pytest

from empire_os.public_intent_offer_method_bridge import (
    IntentOfferSpec, prepare_public_intent_offer_review,
)
from empire_os.public_intent_serp_evidence_bridge import review_existing_serp_snapshot
from empire_os.search_intelligence.serp import SerpSnapshot, SerpResultEvidence


NOW = datetime(2026, 10, 25, 23, 50, tzinfo=timezone.utc)


def proposal():
    return prepare_public_intent_offer_review(IntentOfferSpec(
        market_key="commercial-roofing",
        seed_keyword="commercial roof repair",
        icp_key="roofing-operator",
        buyer_problem="Repair versus replacement decision",
    ))


def sample(*, query="commercial roof repair cost", observed_at=None,
           available=True, quality_gate="lexical_v1", cache=False):
    return SerpSnapshot(
        query=query,
        observed_at=observed_at or (NOW - timedelta(hours=1)).isoformat(),
        engine="duckduckgo_html",
        quality_gate=quality_gate,
        cache=cache,
        available=available,
        results=(
            SerpResultEvidence(
                title="Sample fictional result",
                url="https://competitor.example/roofing",
                snippet="Synthetic for isolated regression",
                position=1, engine="duckduckgo_html",
                relevance_score=0.9,
                provenance=("synthetic_fixture",),
            ),
        ) if available else (),
        error="not_available" if not available else None,
    )


def test_competitor_gap_reuses_original_search_engine_and_preserves_evidence():
    r = review_existing_serp_snapshot(proposal(), sample(), now=NOW)
    assert r["owner"] == "empire_os.search_intelligence.competitor_gap"
    assert r["keyword_idea"] == "commercial roof repair cost"
    assert r["engine"] == "duckduckgo_html"
    assert r["available"] is True
    assert r["serp_evidence"]["observed_result_count"] == 1
    assert r["serp_evidence"]["empire_result_count"] == 0
    assert r["serp_evidence"]["content_gap"] == 1
    assert r["launch_recommendation"] == "HUMAN_REVIEW_RESEARCH_ONLY"
    for field in ("query_search_volume", "cpc", "organic_keyword_difficulty",
                  "estimated_traffic", "offer_payout", "predicted_profit", "realised_revenue"):
        assert r[field] is None
    assert r["publishing_authorized"] is False
    assert r["database_writes"] is False


def test_unavailable_snapshot_does_not_fabricate_rank_or_traffic():
    r=review_existing_serp_snapshot(proposal(), sample(available=False), now=NOW)
    assert r["available"] is False
    assert r["serp_evidence"]["content_gap"] is None
    assert r["launch_recommendation"] == "HOLD_NO_SERP_EVIDENCE"


def test_unreviewed_query_rejected():
    with pytest.raises(ValueError, match="not_in_original"):
        review_existing_serp_snapshot(proposal(), sample(query="free crypto profits"), now=NOW)


@pytest.mark.parametrize("observed", [
    "2026-09-01T12:00:00+00:00",
    "2026-10-26T12:00:00+00:00",
    "2026-10-25T22:00:00",
    "not_a_timestamp",
])
def test_stale_future_naive_and_invalid_timestamp_rejected(observed):
    with pytest.raises(ValueError, match="serp_observation"):
        review_existing_serp_snapshot(
            proposal(), sample(observed_at=observed), now=NOW)


def test_missing_quality_gate_or_cache_provenance_rejected():
    with pytest.raises(ValueError, match="provenance"):
        review_existing_serp_snapshot(proposal(), sample(quality_gate=None), now=NOW)
    with pytest.raises(ValueError, match="provenance"):
        review_existing_serp_snapshot(proposal(), sample(cache=None), now=NOW)
