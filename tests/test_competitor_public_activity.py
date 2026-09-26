from empire_os.competitor_public_activity import (
    build_public_activity_snapshot,
    discover_company_public_activity,
    public_activity_intelligence_signal,
)


def _fetch(url):
    pages = {
        "https://roofer.example": """
        <html><body>
          <a href="/specials">Current Specials</a>
          <a href="/careers">Careers</a>
          <a href="/events">Events</a>
          <a href="/news">Company News</a>
        </body></html>
        """,
        "https://roofer.example/specials": "<html><body>Specials</body></html>",
        "https://roofer.example/careers": "<html><body>Careers</body></html>",
        "https://roofer.example/events": "<html><body>Events</body></html>",
        "https://roofer.example/news": "<html><body>News</body></html>",
    }
    return pages.get(url)


def test_discovers_all_public_activity_categories():
    result = discover_company_public_activity(
        entity_id="entity-1",
        company_name="Example Roofing",
        company_website="roofer.example",
        fetch_fn=_fetch,
    )

    assert result["homepage_observed"] is True
    assert result["observation_count"] == 4
    assert result["ads_offers_creative_count"] == 1
    assert result["hiring_count"] == 1
    assert result["event_count"] == 1
    assert result["company_activity_count"] == 1
    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False
    assert result["execution_authority"] == "none"


def test_snapshot_aggregates_company_categories():
    result = build_public_activity_snapshot(
        companies=[
            {
                "entity_id": "entity-1",
                "company_name": "Example Roofing",
                "company_domain": "roofer.example",
            },
            {
                "entity_id": "entity-2",
                "company_name": "No Activity Roofing",
                "company_domain": "none.example",
            },
        ],
        fetch_fn=_fetch,
        max_workers=2,
    )

    assert result["company_count"] == 2
    assert result["company_with_activity_count"] == 1
    assert result["observation_count"] == 4
    assert result["ads_offers_creative_company_count"] == 1
    assert result["hiring_company_count"] == 1
    assert result["event_company_count"] == 1
    assert result["public_activity_company_count"] == 1
    assert result["market_share_inferred"] is False
    assert result["outreach_enabled"] is False


def test_public_activity_signal_is_observe_only():
    company = discover_company_public_activity(
        entity_id="00000000-0000-0000-0000-000000000011",
        company_name="Example Roofing",
        company_website="roofer.example",
        fetch_fn=_fetch,
    )

    signal = public_activity_intelligence_signal(
        company,
        source_id="00000000-0000-0000-0000-000000000031",
    )

    assert signal["signal_type"] == "competitor_public_activity"
    assert signal["signal_domain"] == "competitive_intelligence"
    assert signal["payload"]["research_candidate"] is True
    assert signal["payload"]["buyer_intent"] is False
    assert signal["payload"]["commercial_intent"] is False
    assert signal["payload"]["prospect_created"] is False
    assert signal["payload"]["outreach_enabled"] is False
    assert signal["buyer_intent_inferred"] is False
    assert signal["commercial_intent_inferred"] is False
    assert signal["execution_authority"] == "none"


def test_external_links_are_not_promoted_as_first_party_activity():
    def fetch(url):
        if url == "https://roofer.example":
            return """
            <html><body>
              <a href="https://jobs.example/roofer">Jobs</a>
              <a href="https://events.example/show">Events</a>
            </body></html>
            """
        return None

    result = discover_company_public_activity(
        entity_id="entity-1",
        company_name="Example Roofing",
        company_website="roofer.example",
        fetch_fn=fetch,
    )

    assert result["observation_count"] == 0
