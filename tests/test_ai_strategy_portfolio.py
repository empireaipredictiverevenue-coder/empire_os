from empire_os.ai_strategy_portfolio import (
    ai_portfolio_gaps,
    build_ai_capability_portfolio,
    compare_ai_options,
    review_ai_portfolio_item,
)


def capability(key="entity-resolution", provider="provider-a", dependency=.7):
    return {
        "capability_key": key,
        "problem": "Resolve commercial entities accurately.",
        "strategic_advantage": "Improves proprietary commercial world model.",
        "evidence_refs": [f"e:{key}"],
        "strategic_value": .9,
        "proprietary_data_advantage": .95,
        "expected_quality_gain": .8,
        "privacy_importance": .8,
        "cost_sensitivity": .7,
        "switching_flexibility": .3,
        "confidence": .8,
        "owner": "ai-strategy",
        "task_class": "entity-resolution",
        "current_provider": provider,
        "current_model": "model-1",
        "evaluation_ref": f"eval:{key}",
        "observed_quality": .85,
        "cost_per_1k_tasks_cents": 5000,
        "switching_cost": .7,
        "dependency_weight": dependency,
    }


def test_portfolio_item_is_review_only():
    result = review_ai_portfolio_item(capability())
    assert result["portfolio_review_ready"] is True
    assert result["strategy_review"]["recommended_mode"] in {"BUILD","BUY","HYBRID","WATCH"}
    assert result["provider_activation"] is False
    assert result["model_promotion"] is False
    assert result["execution_authority"] == "none"


def test_portfolio_detects_provider_concentration():
    result = build_ai_capability_portfolio([
        capability("entity-resolution", "provider-a", .8),
        capability("premium-reasoning", "provider-a", .7),
        capability("multimodal", "provider-b", .2),
    ])
    assert result["provider_concentration"]["available"] is True
    assert "single_provider_dependency_high" in result["dependency_risks"]
    assert result["provider_activation"] is False


def test_unresolved_capability_preserves_missing_evidence():
    row = capability()
    row.pop("evaluation_ref")
    result = build_ai_capability_portfolio([row])
    assert result["unresolved_capabilities"] == ["entity-resolution"]
    assert "evaluation_ref_required_for_portfolio_decision" in result["items"][0]["blockers"]


def test_gap_analysis_flags_high_dependency_and_switching_cost():
    result = ai_portfolio_gaps([capability()])
    assert any(g["gap_type"] == "strategic_dependency" for g in result["gaps"])


def test_compare_options_uses_observed_quality_cost_latency_and_privacy():
    result = compare_ai_options(
        capability_key="premium-reasoning",
        options=[
            {
                "option_key": "provider-a:model-x",
                "observed_quality": .95,
                "observed_reliability": .95,
                "privacy_fit": .7,
                "switching_flexibility": .8,
                "cost_per_1k_tasks_cents": 10000,
                "p95_latency_ms": 2000,
                "evidence_refs": ["eval:a"],
            },
            {
                "option_key": "provider-b:model-y",
                "observed_quality": .8,
                "observed_reliability": .9,
                "privacy_fit": .8,
                "switching_flexibility": .9,
                "cost_per_1k_tasks_cents": 3000,
                "p95_latency_ms": 1000,
                "evidence_refs": ["eval:b"],
            },
        ],
    )
    assert len(result["options"]) == 2
    assert all(item["available"] for item in result["options"])
    assert result["provider_activation"] is False
    assert result["model_promotion"] is False
