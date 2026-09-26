from empire_os.competitor_public_review_overlap import (
    build_public_review_overlap_snapshot,
    discover_company_review_profiles,
    public_review_intelligence_signal,
)


def _fetch(url):
    pages = {
        "https://roofer-a.example": """
        <html><body>
          <a href="/reviews">Read Our Reviews</a>
          <a href="https://www.bbb.org/us/co/denver/profile/roofing/a">BBB</a>
        </body></html>
        """,
        "https://roofer-a.example/reviews": """
        <html><body>
          <a href="https://www.yelp.com/biz/roofer-a-denver">Yelp Reviews</a>
          <a href="https://g.page/r/example/review">Google Reviews</a>
        </body></html>
        """,
        "https://roofer-b.example": """
        <html><body>
          <a href="https://www.bbb.org/us/co/denver/profile/roofing/b">BBB</a>
          <a href="https://www.angi.com/companylist/us/co/denver/b.htm">Angi</a>
        </body></html>
        """,
    }
    return pages.get(url)


def _ecosystem_a():
    return {
        "entity_id": "entity-a",
        "surfaces": [{
            "source_ref": "https://roofer-a.example/reviews",
            "categories": ["testimonial"],
        }],
    }


def test_discovers_explicit_public_review_profiles():
    result = discover_company_review_profiles(
        entity_id="entity-a",
        company_name="Roofer A",
        company_website="roofer-a.example",
        ecosystem_row=_ecosystem_a(),
        fetch_fn=_fetch,
    )

    assert result["pages_observed"] == 2
    assert result["profile_count"] == 3
    assert result["platforms"] == ["bbb", "google", "yelp"]
    assert result["review_sentiment_inferred"] is False
    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False


def test_plain_google_maps_link_without_review_cue_is_not_counted():
    def fetch(url):
        return """
        <html><body>
          <a href="https://www.google.com/maps/place/example">Directions</a>
        </body></html>
        """

    result = discover_company_review_profiles(
        entity_id="entity-a",
        company_name="Roofer A",
        company_website="https://roofer-a.example",
        fetch_fn=fetch,
    )

    assert result["profile_count"] == 0


def test_snapshot_builds_platform_and_company_overlap():
    result = build_public_review_overlap_snapshot(
        companies=[
            {
                "entity_id": "entity-a",
                "company_name": "Roofer A",
                "company_domain": "roofer-a.example",
            },
            {
                "entity_id": "entity-b",
                "company_name": "Roofer B",
                "company_domain": "roofer-b.example",
            },
        ],
        ecosystem_snapshot={
            "companies": [_ecosystem_a()],
        },
        fetch_fn=_fetch,
        max_workers=2,
    )

    assert result["company_count"] == 2
    assert result["company_with_review_profile_count"] == 2
    assert result["review_platform_count"] == 4
    assert result["company_overlap_edge_count"] == 1

    edge = result["company_overlap_edges"][0]
    assert edge["left_company"] == "Roofer A"
    assert edge["right_company"] == "Roofer B"
    assert edge["shared_platforms"] == ["bbb"]
    assert edge["buyer_intent_inferred"] is False
    assert edge["commercial_intent_inferred"] is False


def test_signal_is_research_only():
    company = discover_company_review_profiles(
        entity_id="00000000-0000-0000-0000-000000000011",
        company_name="Roofer A",
        company_website="roofer-a.example",
        ecosystem_row=_ecosystem_a(),
        fetch_fn=_fetch,
    )
    signal = public_review_intelligence_signal(
        company,
        source_id="00000000-0000-0000-0000-000000000031",
    )

    assert signal["signal_type"] == "competitor_public_review_presence"
    assert signal["payload"]["research_candidate"] is True
    assert signal["payload"]["review_sentiment_inferred"] is False
    assert signal["payload"]["buyer_intent"] is False
    assert signal["payload"]["commercial_intent"] is False
    assert signal["payload"]["prospect_created"] is False
    assert signal["payload"]["outreach_enabled"] is False
    assert signal["execution_authority"] == "none"
