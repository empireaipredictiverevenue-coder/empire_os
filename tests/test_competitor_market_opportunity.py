from empire_os.competitor_market_opportunity import (
    build_market_opportunity_projection,
)


def _market_scale():
    return {
        "market_key": "denver-co-roofing",
        "market_query": "Denver CO roofing",
        "niche": "roofing",
        "metro": "denver, co",
        "competitor_with_evidence_count": 9,
        "unique_evidence_count": 9,
        "shared_audience_edge_count": 36,
        "companies": [{
            "entity_id": "entity-golden",
            "company_name": "Golden Spike Roofing Inc",
            "company_domain": "goldenspikeroofing.com",
            "competitor_count": 9,
            "evidence_count": 9,
        }],
    }


def _entities():
    return [
        {
            "entity_id": "entity-golden",
            "company_name": "Golden Spike Roofing Inc",
            "company_domain": "goldenspikeroofing.com",
        },
        {
            "entity_id": "entity-colorado",
            "company_name": "Colorado's Best Roofing",
            "company_domain": "roofingcolorado.com",
        },
        {
            "entity_id": "entity-metro",
            "company_name": "Metro City Roofing",
            "company_domain": "metrocityroofing.com",
        },
    ]


def test_projection_finds_resolved_companies_without_competitor_evidence():
    result = build_market_opportunity_projection(
        market_scale=_market_scale(),
        resolved_entities=_entities(),
    )

    assert result["resolved_company_count"] == 3
    assert result["observed_company_count"] == 1
    assert result["research_gap_company_count"] == 2

    names = [
        row["company_name"]
        for row in result["underserved_audience_candidates"]
    ]
    assert names == [
        "Colorado's Best Roofing",
        "Metro City Roofing",
    ]


def test_projection_does_not_infer_demand_or_revenue_from_missing_evidence():
    result = build_market_opportunity_projection(
        market_scale=_market_scale(),
        resolved_entities=_entities(),
    )

    assert result["underserved_demand_inferred"] is False
    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False
    assert result["market_share_inferred"] is False
    assert result["revenue_opportunity_inferred"] is False
    assert result["outreach_enabled"] is False
    assert result["execution_authority"] == "none"

    for row in result["underserved_audience_candidates"]:
        assert row["underserved_demand_inferred"] is False
        assert row["revenue_opportunity_inferred"] is False
        assert row["outreach_enabled"] is False


def test_territory_heatmap_represents_evidence_coverage_only():
    result = build_market_opportunity_projection(
        market_scale=_market_scale(),
        resolved_entities=_entities(),
    )

    territory = result["territory_heatmap"][0]
    assert territory["metro"] == "denver, co"
    assert territory["resolved_company_count"] == 3
    assert territory["company_with_competitor_evidence_count"] == 1
    assert territory["company_without_competitor_evidence_count"] == 2
    assert territory["evidence_coverage_ratio"] == 0.3333
    assert territory["observed_competitor_count"] == 9
    assert territory["unique_evidence_count"] == 9
    assert territory["shared_audience_edge_count"] == 36
    assert territory["heat_metric"] == "competitor_evidence_coverage_gap"
    assert territory["demand_heat_inferred"] is False
    assert territory["market_share_inferred"] is False
