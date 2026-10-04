from datetime import datetime, timezone

from empire_os.community_intent import (
    capture_external_intent_evidence,
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



def test_external_agent_intent_capture_queues_signal_not_prospect():
    calls = []

    def fake_enqueue(candidate, *, quality):
        calls.append((candidate, quality))
        return {
            "decision": "created",
            "signal_id": "sig-intent-1",
            "status": "unresolved",
            "source": candidate.source,
            "execution_authority": "none",
        }

    result = capture_external_intent_evidence(
        source="agent_research",
        url="https://reddit.com/r/roofing/comments/example",
        title="Need more qualified appointments",
        text=(
            "We need more leads. Google Ads has not been consistently "
            "profitable and we are looking for marketing help."
        ),
        niche="roofing",
        metro="US",
        observed_at="2026-10-04T08:00:00Z",
        evidence_urls=["https://roofing-company.example/roof-replacement"],
        now=datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc),
        enqueue_fn=fake_enqueue,
    )

    assert result["decision"] == "created"
    assert result["canonical_prospect_created"] is False
    assert result["outreach_authority"] == "none"
    assert result["evidence_urls"] == [
        "https://roofing-company.example/roof-replacement"
    ]
    candidate, _quality = calls[0]
    assert candidate.source == "agent_research_intent"
    assert candidate.raw["entity_kind"] == "signal"
    assert candidate.raw["evidence_urls"] == [
        "https://roofing-company.example/roof-replacement"
    ]


def test_reddit_atom_preserves_external_first_party_link_for_identity_seed():
    from empire_os.community_intent import parse_reddit_atom

    xml = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Need more roofing appointments</title>
        <updated>2026-10-04T08:00:00+00:00</updated>
        <author><name>roof_owner</name></author>
        <link rel="alternate" href="https://www.reddit.com/r/Roofing/comments/abc/example/" />
        <content type="html">&lt;p&gt;We need more leads and our Google Ads are not consistently profitable. &lt;a href="https://roofing-company.example/roof-replacement"&gt;our page&lt;/a&gt;&lt;/p&gt;</content>
      </entry>
    </feed>"""
    rows = parse_reddit_atom(
        xml,
        query="qualified appointments",
        niche="roofing",
        metro="US",
    )

    assert len(rows) == 1
    assert rows[0].evidence_urls == (
        "https://roofing-company.example/roof-replacement",
    )
    assert rows[0].intent_band in {"medium", "high"}


def test_future_external_intent_evidence_fails_closed():
    try:
        capture_external_intent_evidence(
            source="agent_research",
            url="https://example.com/post",
            text="Need more leads",
            observed_at="2026-10-05T12:00:00Z",
            now=datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc),
            enqueue_fn=lambda *_args, **_kwargs: {},
        )
    except ValueError as exc:
        assert "future intent evidence rejected" in str(exc)
    else:
        raise AssertionError("future intent evidence must fail closed")
