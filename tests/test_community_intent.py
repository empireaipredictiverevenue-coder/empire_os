from empire_os.community_intent import (
    classify_pain_points,
    collect_reddit_rss_intent,
    collect_public_search_intent,
    normalize_search_result,
    observation_to_signal,
    score_intent,
)
from empire_os.community_intent_v2 import assess_intent_v2


def test_pain_and_intent_classification():
    text = "We are struggling with lead generation and losing revenue on follow up"
    pains = classify_pain_points(text)
    score, band = score_intent(text)
    assert "lead_generation" in pains
    assert "revenue_growth" in pains
    assert "sales_conversion" in pains
    assert score >= 60
    assert band == "high"


def test_linkedin_public_result_becomes_signal_not_prospect():
    row = normalize_search_result(
        platform="linkedin",
        query="looking for sales automation",
        result={
            "title": "Looking for sales automation recommendations",
            "link": "https://www.linkedin.com/posts/example",
            "snippet": "Our manual follow up is costing us leads.",
        },
        niche="b2b",
    )
    assert row is not None
    candidate = observation_to_signal(row)
    assert candidate.source == "linkedin_intent"
    assert candidate.raw["entity_kind"] == "signal"
    assert candidate.raw["outreach_authority"] == "none"


def test_domain_mismatch_is_rejected():
    assert normalize_search_result(
        platform="reddit",
        query="need leads",
        result={
            "title": "Need leads",
            "link": "https://example.com/post",
            "snippet": "Need more leads",
        },
    ) is None


def test_search_collector_dedupes_urls():
    def fake_search(query, limit):
        return {
            "organic": [
                {
                    "title": "Struggling with lead generation",
                    "link": "https://reddit.com/r/sales/comments/1",
                    "snippet": "Need better pipeline and follow up",
                },
                {
                    "title": "Duplicate",
                    "link": "https://reddit.com/r/sales/comments/1",
                    "snippet": "Need a sales tool",
                },
            ]
        }

    rows = collect_public_search_intent(
        platform="reddit",
        queries=("lead generation",),
        search_fn=fake_search,
    )
    assert len(rows) == 1


def test_reddit_atom_parser_builds_signal_only_observation():
    from empire_os.community_intent import parse_reddit_atom
    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Struggling with lead generation and follow up</title>
        <updated>2026-09-21T10:00:00+00:00</updated>
        <author><name>example_user</name></author>
        <link rel="alternate" href="https://www.reddit.com/r/sales/comments/abc/example/" />
        <content type="html">&lt;p&gt;We need a better pipeline and CRM follow up process.&lt;/p&gt;</content>
      </entry>
    </feed>"""
    rows = parse_reddit_atom(
        xml,
        query="lead generation",
        niche="b2b",
    )
    assert len(rows) == 1
    assert rows[0].source == "reddit"
    assert "lead_generation" in rows[0].pain_points
    assert rows[0].url.startswith("https://www.reddit.com/")


def test_linkedin_job_post_is_not_buyer_intent():
    from empire_os.community_intent import normalize_search_result
    row = normalize_search_result(
        platform="linkedin",
        query="sales automation",
        result={
            "title": "We are hiring an Inside Sales Representative",
            "link": "https://www.linkedin.com/posts/example",
            "snippet": "Join our team and apply now.",
        },
    )
    assert row is None



def test_v2_detects_demand_shortage_and_vendor_search():
    assessment = assess_intent_v2(
        "We need more qualified leads and are looking for a lead generation agency.",
        source_mode="reddit_public_search",
    )
    assert any(x.startswith("DEMAND_SHORTAGE.") for x in assessment.intent_types)
    assert any(x.startswith("VENDOR_SEARCH.") for x in assessment.intent_types)
    assert assessment.dimensions.intent_confidence >= 0.5
    assert assessment.dimensions.offer_fit == 0.9
    assert assessment.dimensions.identity_confidence is None
    assert assessment.dimensions.outreach_readiness is None
    assert assessment.canonical_buyer_intent is False
    assert assessment.revenue_inferred is False
    assert assessment.outbound_authority == "none"


def test_v2_detects_unprofitable_ads_and_spend_evidence():
    assessment = assess_intent_v2(
        "We spent $3000 on Google Ads and they are not profitable. Need a PPC specialist.",
        source_mode="reddit_public_search",
    )
    assert any(x.startswith("PAID_MEDIA_FAILURE.") for x in assessment.intent_types)
    assert any(x.startswith("VENDOR_SEARCH.") for x in assessment.intent_types)
    assert assessment.dimensions.ability_to_pay is not None
    assert assessment.dimensions.ability_to_pay >= 0.65
    assert assessment.dimensions.pain_severity >= 0.8


def test_v2_detects_poor_lead_quality_and_conversion_leakage():
    assessment = assess_intent_v2(
        "Our leads are poor quality, follow-up is too slow and the leads are not closing.",
        source_mode="linkedin_public_search",
    )
    assert any(x.startswith("PAID_MEDIA_FAILURE.") for x in assessment.intent_types)
    assert any(x.startswith("CONVERSION_FAILURE.") for x in assessment.intent_types)
    assert assessment.dimensions.pain_severity >= 0.8


def test_v2_detects_buyer_demand_without_claiming_verified_buyer_intent():
    assessment = assess_intent_v2(
        "We are buying qualified roofing leads and can take more volume.",
        source_mode="public_web_search",
    )
    assert any(x.startswith("BUYER_DEMAND.") for x in assessment.intent_types)
    assert assessment.canonical_buyer_intent is False
    assert assessment.dimensions.estimated_opportunity_value is None


def test_signal_payload_carries_truth_and_authority_guards():
    row = normalize_search_result(
        platform="reddit",
        query="need leads",
        result={
            "title": "Need more qualified leads",
            "link": "https://reddit.com/r/smallbusiness/comments/abc/example",
            "snippet": "We need more qualified appointments each week.",
        },
    )
    assert row is not None
    candidate = observation_to_signal(row)
    assert candidate.raw["buyer_intent_verified"] is False
    assert candidate.raw["revenue_verified"] is False
    assert candidate.raw["outreach_authority"] == "none"
    assessment = candidate.raw["community_intent"]["intent_assessment"]
    assert assessment["dimensions"]["identity_confidence"] is None
    assert assessment["dimensions"]["outreach_readiness"] is None


class _Response:
    def __init__(self, status_code):
        self.status_code = status_code
        self.headers = {"content-type": "application/atom+xml"}
        self.text = ""


def test_reddit_429_is_source_health_failure_not_zero_demand():
    result = collect_reddit_rss_intent(
        subreddit="smallbusiness",
        query="need leads",
        get_fn=lambda *args, **kwargs: _Response(429),
    )
    assert result["ok"] is False
    assert result["reason"] == "rate_limited"
    assert result["observations"] == []


def test_reddit_403_is_source_health_failure_not_zero_demand():
    result = collect_reddit_rss_intent(
        subreddit="smallbusiness",
        query="need leads",
        get_fn=lambda *args, **kwargs: _Response(403),
    )
    assert result["ok"] is False
    assert result["reason"] == "http_403"
    assert result["observations"] == []
