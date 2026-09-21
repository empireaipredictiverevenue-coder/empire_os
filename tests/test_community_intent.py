from empire_os.community_intent import (
    classify_pain_points,
    collect_public_search_intent,
    normalize_search_result,
    observation_to_signal,
    score_intent,
)


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
