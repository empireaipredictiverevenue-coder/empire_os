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
