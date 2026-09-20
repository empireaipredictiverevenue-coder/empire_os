from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.strategy_api import create_strategy_router


def client():
    app = FastAPI()
    app.include_router(create_strategy_router())
    return TestClient(app)


def test_health_is_observe_only():
    body = client().get("/v1/strategy/health").json()
    assert body["execution_authority"] == "none"
    assert body["market_entry_execution"] is False
    assert body["publishing_enabled"] is False


def test_keyword_preview_does_not_publish():
    response = client().post(
        "/v1/strategy/keywords/rank/preview",
        json={"keywords": [{
            "keyword": "predictive revenue",
            "observed_demand": .8,
            "commercial_intent": .9,
            "product_fit": .95,
            "buyer_fit": .8,
            "coverage_gap": .9,
            "competitor_gap": .8,
            "ai_citation_gap": .8,
            "conversion_evidence": .6,
            "strategic_category_value": 1.0,
            "confidence": .8,
            "evidence_refs": ["kw:1"],
        }]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ranked"][0]["keyword"] == "predictive revenue"
    assert body["publishing_enabled"] is False


def test_ai_capability_review_never_activates_provider():
    response = client().post(
        "/v1/strategy/ai-capability/review",
        json={"data": {
            "capability_key": "verifier",
            "problem": "Need independent verification.",
            "strategic_advantage": "Higher trust.",
            "evidence_refs": ["e:1"],
            "strategic_value": .9,
            "proprietary_data_advantage": .4,
            "expected_quality_gain": .9,
            "privacy_importance": .5,
            "cost_sensitivity": .5,
            "switching_flexibility": .8,
            "confidence": .8,
        }},
    )
    assert response.status_code == 200
    assert response.json()["provider_activation"] is False


def test_market_domination_review_is_observe_only():
    response = client().post(
        "/v1/strategy/market-domination/review",
        json={"data": {
            "market_key": "uk-home-services",
            "territory_key": "manchester",
            "corridor_key": "roofing:manchester",
            "product_key": "territory-seat",
            "demand_strength": .8,
            "buyer_capacity_strength": .8,
            "competition_inverse": .6,
            "product_fit": .9,
            "data_advantage": .9,
            "search_authority": .7,
            "ai_visibility": .6,
            "partner_density": .7,
            "margin_potential": .85,
            "retention_expansion": .8,
            "confidence": .8,
            "verified_buyer_count": 2,
            "verified_capacity_units": 20,
            "verified_outcome_count": 5,
            "repeat_outcome_count": 2,
            "expected_gross_profit_cents": 400000,
            "realized_gross_profit_cents": 300000,
            "time_to_revenue_days": 18,
            "downside_cents": 50000,
            "evidence_refs": ["market:1", "buyer:1", "outcome:1"],
        }},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["market_entry_execution"] is False
    assert body["territory_allocation"] is False
    assert body["market_control_claimed"] is False
    assert body["execution_authority"] == "none"


def test_market_domination_portfolio_never_allocates():
    response = client().post(
        "/v1/strategy/market-domination/portfolio/preview",
        json={"markets": []},
    )
    assert response.status_code == 200
    assert response.json()["allocation_execution"] is False


def test_jev_strategy_surfaces_are_evaluation_only():
    catalog = client().get("/v1/strategy/jev/task-catalog")
    assert catalog.status_code == 200
    assert catalog.json()["provider_activation"] is False
    assert "reply_classification" in catalog.json()["candidate_tasks"]

    use_case_payload = {
        "task_key": "reply_classification",
        "risk_class": "medium",
        "decision_schema_ref": "schema:reply:v1",
        "baseline_ref": "baseline:reply:v1",
        "evaluation_dataset_refs": ["eval:reply:v1"],
        "deterministic_possible": False,
        "open_ended_generation": False,
        "requires_exact_math": False,
        "consequential_authority": False,
    }
    use_case = client().post(
        "/v1/strategy/jev/use-case/review",
        json={"data": use_case_payload},
    )
    assert use_case.status_code == 200
    assert use_case.json()["review_ready"] is True
    assert use_case.json()["provider_activation"] is False

    plan = client().post(
        "/v1/strategy/jev/eval-plan/preview",
        json={"use_cases": [use_case_payload]},
    )
    assert plan.status_code == 200
    assert plan.json()["ready_for_offline_eval"] == ["reply_classification"]
    assert plan.json()["credentials_required_now"] is False

    compare = client().post(
        "/v1/strategy/jev/providers/compare/preview",
        json={"rows": [{
            "provider_key": "jev",
            "accuracy": .91,
            "brier_score": .09,
            "p95_latency_ms": 300,
            "cost_per_million_input_tokens": .042,
            "operational_failure_rate": .01,
            "evidence_refs": ["private-eval:jev:v1"],
        }]},
    )
    assert compare.status_code == 200
    assert compare.json()["provider_activation"] is False
    assert compare.json()["recommendation_only"] is True


def test_competitive_search_presence_is_not_market_share():
    response = client().post(
        "/v1/strategy/competitive/search-presence/preview",
        json={
            "observations": [
                {
                    "query": "predictive revenue",
                    "domain": "empire-ai.co.uk",
                    "position": 1,
                    "observed_at": "2026-09-20T00:00:00Z",
                    "provenance": ["search_fabric"],
                },
                {
                    "query": "predictive revenue",
                    "domain": "competitor.example",
                    "position": 2,
                    "observed_at": "2026-09-20T00:00:00Z",
                    "provenance": ["search_fabric"],
                },
            ],
            "empire_domains": ["empire-ai.co.uk"],
            "competitor_domains": ["competitor.example"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["market_share"] is None
    assert body["market_share_inferred"] is False


def test_competitive_landscape_stays_observe_only():
    response = client().post(
        "/v1/strategy/competitive/landscape/preview",
        json={
            "competitor_profiles": [{
                "competitor_key": "c1",
                "domain": "competitor.example",
                "observed_facts": [{
                    "fact_type": "product",
                    "summary": "Observed product page.",
                    "source_ref": "web:c1:product",
                    "observed_at": "2026-09-20T00:00:00Z",
                    "confidence": .9,
                }],
            }],
            "search_observations": [],
            "ai_citation_observations": [],
            "empire_domains": ["empire-ai.co.uk"],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["market_entry_execution"] is False
    assert body["publishing_enabled"] is False
    assert body["outreach_enabled"] is False
    assert body["execution_authority"] == "none"


def test_keyword_universe_maps_search_to_product_without_publishing():
    response = client().post(
        "/v1/strategy/keyword-universe/preview",
        json={"keywords": [{
            "keyword": "predictive revenue",
            "cluster_key": "predictive-revenue",
            "intent_class": "category",
            "product_key": "predictive-revenue-os",
            "icp_key": "revenue-leader",
            "funnel_stage": "awareness",
            "cta_key": "review-opportunity",
            "free_tool_key": "revenue-leak-scanner",
            "evidence_refs": ["kw:predictive-revenue"],
            "observed_demand": .8,
            "commercial_intent": .7,
            "product_fit": .95,
            "buyer_fit": .9,
            "coverage_gap": .8,
            "competitor_gap": .7,
            "ai_citation_gap": .8,
            "conversion_evidence": .5,
            "strategic_category_value": 1.0,
            "confidence": .8,
        }]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["keywords"][0]["record"]["product_key"] == "predictive-revenue-os"
    assert body["publishing_enabled"] is False
    assert body["indexation_enabled"] is False
    assert body["execution_authority"] == "none"


def test_keyword_asset_backlog_is_draft_only():
    response = client().post(
        "/v1/strategy/keyword-universe/assets/preview",
        json={"keywords": [{
            "keyword": "permit intelligence",
            "cluster_key": "permit-intelligence",
            "intent_class": "product",
            "product_key": "permit-intelligence",
            "icp_key": "agency-data-buyer",
            "funnel_stage": "consideration",
            "cta_key": "view-permit-radar",
            "free_tool_key": "permit-opportunity-checker",
            "evidence_refs": ["kw:permit-intelligence"],
            "observed_demand": .7,
            "commercial_intent": .8,
            "product_fit": .95,
            "buyer_fit": .9,
            "coverage_gap": .8,
            "competitor_gap": .7,
            "ai_citation_gap": .7,
            "conversion_evidence": .4,
            "strategic_category_value": .9,
            "confidence": .8,
        }]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["assets"][0]["draft_only"] is True
    assert body["publishing_enabled"] is False
    assert body["indexation_enabled"] is False


def test_ai_portfolio_does_not_activate_or_promote():
    response = client().post(
        "/v1/strategy/ai-portfolio/preview",
        json={"capabilities": [{
            "capability_key": "entity-resolution",
            "problem": "Resolve commercial entities.",
            "strategic_advantage": "Improves world model quality.",
            "evidence_refs": ["e:entity"],
            "strategic_value": .9,
            "proprietary_data_advantage": .95,
            "expected_quality_gain": .8,
            "privacy_importance": .8,
            "cost_sensitivity": .7,
            "switching_flexibility": .3,
            "confidence": .8,
            "owner": "ai-strategy",
            "task_class": "entity-resolution",
            "current_provider": "provider-a",
            "current_model": "model-a",
            "evaluation_ref": "eval:entity",
            "observed_quality": .9,
            "cost_per_1k_tasks_cents": 5000,
            "switching_cost": .7,
            "dependency_weight": .8,
        }]},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["provider_activation"] is False
    assert body["model_promotion"] is False
    assert body["budget_commitment"] is False
    assert body["execution_authority"] == "none"


def test_ai_option_comparison_is_observed_evidence_only():
    response = client().post(
        "/v1/strategy/ai-portfolio/options/compare/preview",
        json={
            "capability_key": "premium-reasoning",
            "options": [{
                "option_key": "provider-a:model-x",
                "observed_quality": .95,
                "observed_reliability": .95,
                "privacy_fit": .7,
                "switching_flexibility": .8,
                "cost_per_1k_tasks_cents": 10000,
                "p95_latency_ms": 2000,
                "evidence_refs": ["eval:a"],
            }],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["options"][0]["available"] is True
    assert body["provider_activation"] is False
    assert body["model_promotion"] is False


def test_scenario_review_is_not_forecast_or_actual():
    response = client().post(
        "/v1/strategy/scenarios/review",
        json={"data": {
            "scenario_id": "search-shift",
            "scenario_type": "search_ai_behavior",
            "title": "AI answer engines reduce classic organic clicks",
            "hypothesis": "More discovery moves into answer engines.",
            "time_horizon_days": 180,
            "estimated_probability": .5,
            "confidence": .6,
            "impacts": {
                "search_visibility": -.25,
                "ai_visibility": .2,
                "time_to_revenue": .1,
            },
            "response_options": [{
                "option_id": "geo-strengthen",
                "summary": "Increase citation-worthy research and answer assets.",
                "reversible": True,
                "evidence_refs": ["strategy:geo"],
            }],
            "evidence_refs": ["scenario:search-shift"],
        }},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["scenario_only"] is True
    assert body["forecast"] is False
    assert body["actual_outcome"] is False
    assert body["execution_authority"] == "none"


def test_scenario_stress_test_never_executes_response():
    response = client().post(
        "/v1/strategy/scenarios/stress-test/preview",
        json={
            "baseline": {
                "model_cost": .3,
                "time_to_revenue": .4,
            },
            "scenarios": [{
                "scenario_id": "provider-shock",
                "scenario_type": "model_cost",
                "title": "Model provider cost shock",
                "hypothesis": "Premium reasoning cost rises materially.",
                "estimated_probability": 1.0,
                "confidence": .7,
                "impacts": {
                    "model_cost": .8,
                    "time_to_revenue": .2,
                },
                "evidence_refs": ["scenario:model-cost"],
            }],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["stress_results"][0]["scenario_id"] == "provider-shock"
    assert body["execution_enabled"] is False
    assert body["forecast"] is False
    assert body["execution_authority"] == "none"


def test_typed_decision_eval_api_is_offline_only():
    rows = []
    for i in range(25):
        truth = "positive" if i % 2 == 0 else "negative"
        rows.append({
            "case_id": f"c-{i}",
            "task_key": "reply_classification",
            "provider_key": "jev",
            "model_key": "system-one",
            "ground_truth": truth,
            "predicted": truth,
            "confidence": .9,
            "latency_ms": 120,
            "input_tokens": 40,
            "cost_cents": .001,
            "source_ref": f"eval:{i}",
        })
    response = client().post(
        "/v1/strategy/typed-decision/eval/preview",
        json={"rows": rows, "minimum_samples": 20},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["accuracy"] == 1.0
    assert body["provider_activation"] is False
    assert body["production_routing"] is False


def test_typed_decision_shadow_api_never_controls_live_route():
    response = client().post(
        "/v1/strategy/typed-decision/shadow/review",
        json={"data": {
            "shadow_id": "s1",
            "task_key": "reply_classification",
            "case_ref": "case:1",
            "incumbent_provider": "rules",
            "incumbent_decision": "negative",
            "candidate_provider": "jev",
            "candidate_decision": "positive",
            "candidate_confidence": .74,
            "decision_schema_ref": "schema:reply:v1",
        }},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["candidate_controlled_live_routing"] is False
    assert body["execution_performed"] is False


def test_category_strategy_api_never_claims_leadership():
    response = client().post(
        "/v1/strategy/category/review",
        json={"data": {
            "category_key": "predictive-revenue",
            "category_name": "Predictive Revenue Operating System",
            "narrative": "See revenue earlier and learn from realized GP.",
            "evidence_refs": ["strategy:category"],
            "proof_refs": ["proof:1"],
            "category_clarity": .8,
            "problem_urgency": .8,
            "differentiation": .8,
            "proof_strength": .8,
            "search_presence": .8,
            "ai_citation_presence": .8,
            "content_authority": .8,
            "partner_amplification": .8,
            "customer_language_alignment": .8,
            "commercial_conversion_evidence": .8,
        }},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["leadership_claimed"] is False
    assert body["publishing_enabled"] is False


def test_partnership_strategy_api_never_outreaches_or_contracts():
    response = client().post(
        "/v1/strategy/partnership/review",
        json={"data": {
            "partner_key": "agency-1",
            "partner_type": "agency",
            "strategic_thesis": "Extend distribution.",
            "evidence_refs": ["partner:1"],
            "strategic_fit": .8,
            "distribution_reach": .8,
            "data_synergy": .7,
            "product_synergy": .8,
            "commercial_economics": .8,
            "brand_trust": .8,
            "learning_value": .8,
            "switching_cost_value": .6,
            "execution_feasibility": .8,
            "exclusivity_risk": .2,
            "dependency_risk": .2,
        }},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outreach_enabled"] is False
    assert body["contracting_enabled"] is False


def test_strategy_control_tower_is_read_only():
    response = client().post(
        "/v1/strategy/control-tower/preview",
        json={
            "market_portfolio": {"markets": [{"identity": {"corridor_key": "roofing:manchester"}}]},
            "category_portfolio": {"categories": [{"category_key": "predictive-revenue"}]},
            "keyword_portfolio": {"keywords": [{"record": {"keyword": "predictive revenue"}}]},
            "competitive_landscape": {
                "search_presence": {"available": True},
                "ai_citation_presence": {"available": True},
            },
            "ai_portfolio": {"capabilities": [{"capability_key": "entity-resolution"}]},
            "partnership_portfolio": {"partners": [{"partner_key": "agency-1"}]},
            "scenario_set": {"scenarios": [{"scenario_id": "search-shift"}]},
            "max_brief_items": 5,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["control_tower"]["execution_authority"] == "none"
    assert body["control_tower"]["market_entry_execution"] is False
    assert body["brief"]["execution_performed"] is False


def test_typed_decision_dataset_api_marks_fixture_unfit_for_promotion():
    rows = [{
        "case_id": "r1",
        "task_key": "reply_classification",
        "inputs": {"body_text": "Please unsubscribe me."},
        "ground_truth": "unsubscribe",
        "label_source": "deterministic_regression_fixture",
        "source_ref": "fixture:r1",
        "synthetic_test_fixture": True,
    }]
    freeze = client().post(
        "/v1/strategy/typed-decision/dataset/freeze/preview",
        json={"dataset_id": "reply-fixture", "version": "v1", "rows": rows},
    )
    assert freeze.status_code == 200
    manifest = freeze.json()
    assert manifest["synthetic_test_fixture_count"] == 1
    assert manifest["eligible_for_production_promotion_evidence"] is False

    verify = client().post(
        "/v1/strategy/typed-decision/dataset/verify",
        json={"data": manifest},
    )
    assert verify.status_code == 200
    assert verify.json()["valid"] is True

    ready = client().post(
        "/v1/strategy/typed-decision/dataset/readiness/preview",
        json={"manifest": manifest, "minimum_per_label": 1},
    )
    assert ready.status_code == 200
    assert ready.json()["ready_for_provider_promotion_eval"] is False
    assert "synthetic_test_fixtures_present" in ready.json()["blockers"]
