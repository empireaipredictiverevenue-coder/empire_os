from empire_os.opportunity_research import (
    build_opportunity_research_queries,
    execute_opportunity_research,
    research_candidate,
)


def _candidate(**overrides):
    row = {
        "opportunity_key": "market:roofing:denver",
        "opportunity_class": "market_research",
        "title": "roofing / denver",
        "niche": "roofing",
        "metro": "denver",
        "trigger": "observed_market_evidence",
    }
    row.update(overrides)
    return row


def fake_search(query, *, num):
    assert num <= 5
    return {
        "searchParameters": {"engine": "test"},
        "organic": [
            {
                "position": 1,
                "title": "Denver roofing market",
                "snippet": "Roofing services and companies in Denver.",
                "link": "https://example.com/denver-roofing",
            },
            {
                "position": 2,
                "title": "Unrelated cooking page",
                "snippet": "Pasta recipes.",
                "link": "https://example.com/pasta",
            },
        ],
    }


def test_query_plan_is_bounded():
    queries = build_opportunity_research_queries(_candidate())
    assert 1 <= len(queries) <= 3
    assert any("roofing" in query.lower() for query in queries)


def test_research_keeps_search_results_as_observations_only():
    result = research_candidate(
        _candidate(),
        search_fn=fake_search,
        max_results_per_query=3,
    )
    assert result["observation_count"] >= 1
    assert result["irrelevant_result_rejected_count"] >= 1
    assert result["observations_are_verified_facts"] is False
    assert result["demand_inferred"] is False
    assert result["buyer_intent_inferred"] is False
    assert result["revenue_inferred"] is False
    assert result["execution_authority"] == "none"


def test_batch_is_bounded_and_noncommercial():
    radar = {
        "candidates": [_candidate() for _ in range(20)],
    }
    result = execute_opportunity_research(
        radar,
        search_fn=fake_search,
        max_candidates=4,
    )
    assert result["radar_candidate_count"] == 20
    assert result["researched_candidate_count"] == 4
    assert result["outreach_enabled"] is False
    assert result["execution_authority"] == "none"
