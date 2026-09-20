from empire_os.strategic_scenarios import (
    build_scenario_set,
    review_scenario,
    scenario_gaps,
    stress_test_strategy,
)


def scenario(sid="search-shift", stype="search_ai_behavior", probability=.5):
    return {
        "scenario_id": sid,
        "scenario_type": stype,
        "title": "AI answer engines reduce classic organic clicks",
        "hypothesis": "More discovery moves to answer engines.",
        "time_horizon_days": 180,
        "estimated_probability": probability,
        "confidence": .6,
        "impacts": {
            "search_visibility": -.25,
            "ai_visibility": .20,
            "time_to_revenue": .10,
        },
        "response_options": [{
            "option_id": "geo-strengthen",
            "summary": "Increase citation-worthy primary research and answer assets.",
            "reversible": True,
            "evidence_refs": ["strategy:geo"],
        }],
        "evidence_refs": [f"scenario:{sid}"],
    }


def test_scenario_is_never_forecast_or_actual():
    result = review_scenario(scenario())
    assert result["review_ready"] is True
    assert result["scenario_only"] is True
    assert result["forecast"] is False
    assert result["actual_outcome"] is False
    assert result["execution_authority"] == "none"


def test_scenario_set_only_computes_expected_impact_with_valid_probability_set():
    a = scenario("a", "search_ai_behavior", .6)
    b = scenario("b", "competitor", .4)
    b["impacts"] = {
        "search_visibility": -.10,
        "ai_visibility": -.10,
        "time_to_revenue": .05,
    }
    result = build_scenario_set([a, b])
    assert result["probability_set_valid"] is True
    assert result["expected_impacts"]["search_visibility"] is not None
    assert result["forecast"] is False

    unknown = scenario("unknown", "regulation", None)
    result2 = build_scenario_set([unknown])
    assert result2["probability_set_valid"] is False
    assert result2["expected_impacts"]["search_visibility"] is None


def test_stress_test_ranks_adverse_scenarios_without_execution():
    bad = scenario("provider-shock", "model_cost", .5)
    bad["impacts"] = {"model_cost": .8, "time_to_revenue": .2}
    mild = scenario("mild", "competitor", .5)
    mild["impacts"] = {"competitive_pressure": .1}
    result = stress_test_strategy(
        baseline={
            "model_cost": .3,
            "time_to_revenue": .4,
            "competitive_pressure": .2,
        },
        scenarios=[mild, bad],
    )
    assert result["stress_results"][0]["scenario_id"] == "provider-shock"
    assert result["stress_results"][0]["stress_rank"] == 1
    assert result["execution_enabled"] is False
    assert result["forecast"] is False


def test_scenario_gap_analysis_exposes_uncovered_risks():
    result = scenario_gaps([scenario()])
    assert "regulation" in result["missing_scenario_types"]
    assert "data_source" in result["missing_scenario_types"]
    assert result["forecast"] is False
