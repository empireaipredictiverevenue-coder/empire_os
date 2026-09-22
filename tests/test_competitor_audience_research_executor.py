from empire_os.competitor_audience_research_executor import (
    build_account_research_queries,
    execute_account_research,
    execute_snapshot_research,
)


def _company():
    return {
        "entity_id": "entity-golden",
        "company_name": "Golden Spike Roofing Inc",
        "company_website": "https://goldenspikeroofing.com",
        "competitors": ["elite-roofing-solar"],
        "evidence": [
            {
                "source_ref": "https://comparison.example/denver",
            }
        ],
    }


def _context(action="deep_account_research"):
    return {
        "entity_id": "entity-golden",
        "company_name": "Golden Spike Roofing Inc",
        "research_rank": 1,
        "next_best_research_action": action,
        "features": {
            "research_priority": 0.8433,
        },
    }


def _search_fn(query, num=5):
    if "goldenspikeroofing.com" in query:
        return {
            "searchParameters": {"engine": "bing_html"},
            "organic": [{
                "title": "Golden Spike Roofing",
                "link": "https://goldenspikeroofing.com/",
                "snippet": "Official roofing company website.",
                "position": 1,
                "relevance_score": 1.0,
            }],
        }
    return {
        "searchParameters": {"engine": "bing_html"},
        "organic": [
            {
                "title": "Denver roofing comparison",
                "link": "https://comparison.example/denver",
                "snippet": "Public roofing comparison.",
                "position": 1,
                "relevance_score": 0.9,
            },
            {
                "title": "Roofing directory",
                "link": "https://directory.example/golden-spike",
                "snippet": "Public company listing.",
                "position": 2,
                "relevance_score": 0.8,
            },
        ],
    }


def test_deep_research_plan_is_bounded_and_public_search_oriented():
    queries = build_account_research_queries(
        _company(),
        _context(),
    )

    assert queries
    assert len(queries) <= 10
    assert any("reviews" in query for query in queries)
    assert any("jobs hiring" in query for query in queries)
    assert any("comparison alternatives" in query for query in queries)


def test_executor_keeps_search_results_as_unverified_observations():
    result = execute_account_research(
        _company(),
        _context(),
        search_fn=_search_fn,
    )

    assert result["observation_count"] >= 2
    assert result["observations_are_verified_facts"] is False
    assert result["buyer_intent"] is False
    assert result["commercial_intent"] is False
    assert result["prospect_created"] is False
    assert result["outreach_enabled"] is False
    assert result["score_persistence_authorized"] is False
    assert result["outcome_update_authorized"] is False
    assert result["execution_authority"] == "none"

    assert all(
        row["verified_fact"] is False
        for row in result["observations"]
    )


def test_deep_research_can_be_ready_for_review_without_becoming_intent():
    result = execute_account_research(
        _company(),
        _context(),
        search_fn=_search_fn,
    )

    assert result["first_party_observation_count"] >= 1
    assert result["third_party_observation_count"] >= 2
    assert result["next_step"] == "account_research_brief_ready_for_review"
    assert result["buyer_intent"] is False
    assert result["outreach_enabled"] is False


def test_collect_more_evidence_stays_research_only():
    result = execute_account_research(
        _company(),
        _context("collect_additional_public_evidence"),
        search_fn=_search_fn,
    )

    assert result["next_step"] == (
        "review_additional_public_evidence_candidates"
    )
    assert result["commercial_intent"] is False
    assert result["execution_authority"] == "none"


def test_snapshot_executor_preserves_rank_and_no_authority():
    snapshot = {
        "companies": [_company()],
        "omega_cortex_context": [_context()],
    }

    result = execute_snapshot_research(
        snapshot,
        search_fn=_search_fn,
    )

    assert result["company_count"] == 1
    assert result["actions"][0]["research_rank"] == 1
    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False
    assert result["outreach_enabled"] is False
    assert result["execution_authority"] == "none"
