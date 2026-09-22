from empire_os.competitor_intelligence_feed import (
    build_competitor_intelligence_feed,
)


def _companies():
    return [
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
    ]


def test_feed_uses_canonical_companies_without_search_discovery():
    result = build_competitor_intelligence_feed(
        niche="roofing",
        metro="denver, co",
        companies=_companies(),
        market_scale={"companies": []},
        search_presence={
            "search_presence_available": False,
            "share_of_voice_available": False,
            "companies": [],
        },
    )

    assert result["canonical_company_count"] == 2
    assert result["tam"]["canonical_company_count"] == 2
    assert result["search_intelligence"][
        "canonical_competitor_domain_count"
    ] == 2
    assert result["search_intelligence"][
        "competitor_gap_inputs_available"
    ] is True
    assert result["search_intelligence"][
        "provider_reliability_blocking_canonical_roster"
    ] is False


def test_feed_projects_only_observed_context():
    result = build_competitor_intelligence_feed(
        niche="roofing",
        metro="denver, co",
        companies=_companies(),
        market_scale={
            "companies": [{
                "entity_id": "entity-a",
                "evidence_count": 2,
            }],
        },
        ecosystem={
            "companies": [{
                "entity_id": "entity-a",
                "surface_count": 3,
            }],
        },
        reviews={
            "companies": [{
                "entity_id": "entity-a",
                "profile_count": 4,
            }],
        },
        activity={
            "companies": [{
                "entity_id": "entity-a",
                "observation_count": 5,
            }],
        },
        search_presence={
            "search_presence_available": False,
            "share_of_voice_available": False,
            "companies": [],
        },
    )

    gps = result["revenue_gps"]
    assert gps["companies_with_research_context"] == 1
    assert gps["competitor_overlap_company_count"] == 1
    assert gps["ecosystem_company_count"] == 1
    assert gps["review_presence_company_count"] == 1
    assert gps["public_activity_company_count"] == 1
    assert gps["demand_inferred"] is False
    assert gps["revenue_opportunity_inferred"] is False
    assert gps["economics_estimate"] is None
    assert gps["prediction_available"] is False


def test_feed_never_promotes_competitor_context_to_gtm_authority():
    result = build_competitor_intelligence_feed(
        niche="roofing",
        metro="denver, co",
        companies=_companies(),
    )

    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False
    assert result["demand_inferred"] is False
    assert result["market_share_inferred"] is False
    assert result["revenue_opportunity_inferred"] is False
    assert result["prospect_created"] is False
    assert result["outreach_enabled"] is False
    assert result["execution_authority"] == "none"

    gtm = result["gtm"]
    assert gtm["market_context_only"] is True
    assert gtm["prospect_created"] is False
    assert gtm["outreach_enabled"] is False
    assert gtm["execution_authority"] == "none"


def test_search_overlay_does_not_become_market_share():
    result = build_competitor_intelligence_feed(
        niche="roofing",
        metro="denver, co",
        companies=_companies(),
        search_presence={
            "search_presence_available": True,
            "share_of_voice_available": True,
            "share_metric":
                "reciprocal_position_weighted_observed_search_presence",
            "companies": [{
                "entity_id": "entity-a",
                "canonical_search_verified": True,
                "generic_observation_count": 1,
            }],
        },
    )

    search = result["search_intelligence"]
    assert search["search_presence_overlay_available"] is True
    assert search["share_of_voice_available"] is True
    assert search["share_of_voice_metric"] == (
        "reciprocal_position_weighted_observed_search_presence"
    )
    assert search["market_share_inferred"] is False
