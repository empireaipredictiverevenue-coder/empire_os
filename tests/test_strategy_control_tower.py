from empire_os.strategy_control_tower import (
    build_strategy_brief,
    build_strategy_control_tower,
)


def packet():
    return build_strategy_control_tower(
        market_portfolio={"markets": [{"identity": {"corridor_key": "roofing:manchester"}}]},
        category_portfolio={"categories": [{"category_key": "predictive-revenue"}]},
        keyword_portfolio={"keywords": [{"record": {"keyword": "predictive revenue"}}]},
        competitive_landscape={
            "search_presence": {"available": True},
            "ai_citation_presence": {"available": True},
        },
        ai_portfolio={"capabilities": [{"capability_key": "entity-resolution"}]},
        partnership_portfolio={"partners": [{"partner_key": "agency-1"}]},
        scenario_set={"scenarios": [{"scenario_id": "search-shift"}]},
    )


def test_control_tower_is_observe_only():
    r=packet()
    assert r["execution_authority"]=="none"
    assert r["market_entry_execution"] is False
    assert r["publishing_enabled"] is False
    assert r["provider_activation"] is False
    assert r["executive_signals"]["strategic_gap_count"]==0


def test_missing_packets_become_gaps_not_fake_scores():
    r=build_strategy_control_tower(
        market_portfolio={},
        category_portfolio={},
        keyword_portfolio={},
        competitive_landscape={},
        ai_portfolio={},
        partnership_portfolio={},
        scenario_set={},
    )
    areas={g["area"] for g in r["strategic_gaps"]}
    assert "markets" in areas
    assert "category" in areas
    assert "keywords" in areas
    assert "competitive_search" in areas
    assert "competitive_ai_visibility" in areas
    assert "scenarios" in areas


def test_strategy_brief_is_decision_support_only():
    b=build_strategy_brief(packet(),max_items=5)
    assert b["decision_support_only"] is True
    assert b["execution_performed"] is False
    assert b["item_count"]==5
