"""Five first-party candidate sites enter the original Scout once, research-only."""
from datetime import datetime, timezone

from empire_os.buyer_public_research_seed import build_public_research_seeds

NOW = datetime(2026, 10, 27, 15, 0, tzinfo=timezone.utc)

EXPECTED = {
    "tryleadledger.com": "roofing",
    "luxenworks.com": "roofing",
    "dependablecalls.com": "roofing",
    "oncall-24.com": "roofing",
    "join.leadswitchmedia.com": "insurance",
}


def test_reviewed_publisher_roster_preserves_original_scout_governance():
    calls = []
    def no_public_search(queries, num):
        calls.append((tuple(queries), num))
        return {}
    result = build_public_research_seeds(
        {}, search_fn=no_public_search, max_queries=8, results_per_query=4,
        include_volume=False, observed_at=NOW,
    )
    by_domain = {x["domain"]: x for x in result["seeds"]}
    assert len(calls) == 1  # zero additional calls from adding five source URLs
    assert result["query_count"] == 2  # existing bounded publisher-only rotation
    assert result["mode"] == "OBSERVE"
    assert result["outbound_sent"] is False
    assert result["database_write_performed"] is False
    assert result["commercial_authority"] == "none"
    assert result["execution_authority"] == "none"
    for domain, vertical in EXPECTED.items():
        assert domain in by_domain
        row = by_domain[domain]
        assert row["target_markets"] == ["USA"]
        assert vertical in row["target_verticals"]
        assert row["source_refs"] == [f"public:multimarket_review:USA:{domain}"]
        assert row["source_queries"] == []
        assert row["truth_class"] == "OBSERVED_PUBLIC_RESEARCH"
        assert row["identity_verified"] is False
        assert row["commercial_terms_verified"] is False
        assert row["buyer_capacity_verified"] is False
        assert row["buyer_price_verified"] is False
        assert row["outreach_authorized"] is False
        assert row["execution_authority"] == "none"
    # Existing well-known already-contacted networks were not reintroduced
    # through this addition (their historical contact states stay authoritative).
    assert len(result["seeds"]) == len(by_domain)


def test_search_repeat_does_not_duplicate_reviewed_identity():
    def returning_same_domain(queries, num):
        return {q:["luxenworks.com","tryleadledger.com"] for q in queries}
    result = build_public_research_seeds(
        {}, search_fn=returning_same_domain,
        max_queries=2, include_volume=False, observed_at=NOW)
    for domain in ("luxenworks.com","tryleadledger.com"):
        rows=[r for r in result["seeds"] if r["domain"]==domain]
        assert len(rows)==1
        assert rows[0]["outreach_authorized"] is False
        assert rows[0]["buyer_capacity_verified"] is False
        assert rows[0]["source_queries"]  # merged provenance, not duplicate


def test_ccdocs_roofing_first_party_offer_is_only_a_research_seed():
    result = build_public_research_seeds(
        {}, search_fn=lambda queries, num: {}, max_queries=2,
        include_volume=False, observed_at=NOW,
    )
    rows = [r for r in result["seeds"] if r["domain"] == "ccdocs.com"]
    assert len(rows) == 1
    row = rows[0]
    assert row["website"] == "https://ccdocs.com/sell-calls/roofing/"
    assert row["target_markets"] == ["USA"]
    assert "roofing" in row["target_verticals"]
    assert row["source_refs"] == ["public:multimarket_review:USA:ccdocs.com"]
    assert row["source_queries"] == []
    for field in ("identity_verified", "buyer_capacity_verified",
                  "commercial_terms_verified", "buyer_price_verified",
                  "outreach_authorized"):
        assert row[field] is False
    assert result["query_count"] == 2
    assert result["database_write_performed"] is False
    assert result["outbound_sent"] is False
    assert result["execution_authority"] == "none"


def test_next_wave_first_party_sources_remain_unapproved_and_distinct():
    result = build_public_research_seeds(
        {}, search_fn=lambda queries, num: {},
        max_queries=2, include_volume=False, observed_at=NOW,
    )
    rows = {r["domain"]: r for r in result["seeds"]}
    for domain, url in {
        "callthread.com": "https://callthread.com/site/publisher/homepage",
        "intergmedia.com": "https://intergmedia.com/pay-per-call/",
    }.items():
        row = rows[domain]
        assert row["website"] == url
        assert row["target_markets"] == ["USA"]
        assert "roofing" in row["target_verticals"]
        assert row["source_queries"] == []
        assert row["source_refs"] == [f"public:multimarket_review:USA:{domain}"]
        for key in ("identity_verified", "commercial_terms_verified",
                    "buyer_capacity_verified", "buyer_price_verified",
                    "outreach_authorized"):
            assert row[key] is False
    assert result["outbound_sent"] is False
    assert result["database_write_performed"] is False
    assert result["execution_authority"] == "none"
