from empire_os.opportunity_radar import build_opportunity_radar


def test_radar_aggregates_observed_sources_without_inventing_truth():
    payload = build_opportunity_radar(
        generated_at="2026-09-22T21:00:00+00:00",
        market_gps={
            "generated_at": "2026-09-22T20:00:00+00:00",
            "research_queue": [{
                "niche": "roofing",
                "metro": "denver, co",
                "research_priority_score": 72,
                "evidence_refs": ["canonical:prospect_acquisitions"],
                "recommended_next_action": "deepen_market_research",
            }],
            "markets": [{
                "niche": "roofing",
                "metro": "denver, co",
                "commercial_demand_state": "not_observed",
                "product_candidate": None,
            }],
        },
        community_intent={
            "observed_at": "2026-09-22T20:15:00+00:00",
            "pain_solution_briefs": [{
                "pain_point": "search_visibility",
                "observed_mentions": 3,
                "average_intent_score": 65,
                "high_intent_mentions": 2,
                "evidence_urls": ["https://example.com/1"],
                "offer_key": "search_growth_command",
                "products": ["geo_ai_visibility"],
                "next_actions": ["collect_serp_evidence"],
                "opportunity_event": "opportunity_candidate_created",
                "evidence_strength": "moderate",
            }],
        },
        competitor_market={
            "generated_at": "2026-09-22T20:30:00+00:00",
            "market_key": "roofing-denver",
            "niche": "roofing",
            "metro": "denver, co",
            "research_gap_company_count": 1,
            "underserved_audience_candidates": [{
                "entity_id": "company:1",
            }],
        },
    )
    assert payload["candidate_count"] == 3
    assert payload["factory_ready_count"] == 0
    assert payload["automatic_research_allowed"] is True
    assert payload["automatic_external_execution_allowed"] is False
    assert payload["execution_authority"] == "none"
    assert all(
        row["revenue_inferred"] is False
        for row in payload["candidates"]
    )


def test_missing_sources_stay_unavailable():
    payload = build_opportunity_radar(
        market_gps=None,
        community_intent=None,
        competitor_market=None,
    )
    assert payload["candidate_count"] == 0
    assert payload["source_status"]["market_gps"]["available"] is False
    assert payload["source_status"]["community_intent"]["available"] is False
    assert payload["source_status"]["competitor_market"]["available"] is False
