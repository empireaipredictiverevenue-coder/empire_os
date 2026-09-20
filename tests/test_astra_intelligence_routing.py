from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.astra import AstraSnapshot
from empire_os.astra_api import create_astra_router
from empire_os.astra_intelligence_routing import review_intelligence_route


def snapshot(**overrides):
    values = {
        "execution_mode": "observe",
        "actual_revenue_cents": 100000,
        "premium_ai_budget_cents": 1000,
    }
    values.update(overrides)
    return AstraSnapshot(**values)


def test_deterministic_tasks_are_bounded_to_rules():
    review = review_intelligence_route(
        snapshot(),
        task_kind="scoring",
        expected_value_cents=100000,
        premium_cost_cents=100,
    )
    assert review.selected_route == "rules"
    assert review.premium_eligible is False
    assert "task_bounded_to_rules" in review.blockers


def test_language_tasks_are_bounded_to_local():
    review = review_intelligence_route(
        snapshot(),
        task_kind="copy",
        expected_value_cents=100000,
        premium_cost_cents=100,
    )
    assert review.selected_route == "local"
    assert "task_bounded_to_local" in review.blockers


def test_premium_requires_revenue_budget_cost_and_roi_hurdle():
    review = review_intelligence_route(
        snapshot(),
        task_kind="strategic_reasoning",
        expected_value_cents=500,
        premium_cost_cents=100,
    )
    assert review.selected_route == "premium"
    assert review.premium_eligible is True
    assert review.expected_value_multiple == 5.0
    assert review.minimum_premium_roi_multiple == 5
    assert review.premium_budget_headroom_cents == 900
    assert review.blockers == ()
    assert review.provider_activation is False
    assert review.premium_spend_execution is False
    assert review.budget_mutation is False
    assert review.model_promotion is False


def test_below_roi_hurdle_stays_local():
    review = review_intelligence_route(
        snapshot(),
        task_kind="strategic_reasoning",
        expected_value_cents=499,
        premium_cost_cents=100,
    )
    assert review.selected_route == "local"
    assert "expected_value_below_premium_roi_hurdle" in review.blockers


def test_no_actual_revenue_keeps_premium_route_closed():
    review = review_intelligence_route(
        snapshot(actual_revenue_cents=0),
        task_kind="strategic_reasoning",
        expected_value_cents=1000,
        premium_cost_cents=100,
    )
    assert review.selected_route == "local"
    assert "actual_revenue_evidence_required_for_premium" in review.blockers


def test_cost_over_budget_keeps_premium_route_closed():
    review = review_intelligence_route(
        snapshot(premium_ai_budget_cents=50),
        task_kind="strategic_reasoning",
        expected_value_cents=1000,
        premium_cost_cents=100,
    )
    assert review.selected_route == "local"
    assert "premium_cost_exceeds_budget" in review.blockers
    assert review.premium_budget_headroom_cents == 0


def test_api_route_review_never_activates_provider_or_spend():
    app = FastAPI()
    app.include_router(create_astra_router())
    response = TestClient(app).post(
        "/v1/astra/intelligence-route/preview",
        json={
            "snapshot": {
                "execution_mode": "observe",
                "actual_revenue_cents": 100000,
                "premium_ai_budget_cents": 1000,
            },
            "task_kind": "strategic_reasoning",
            "expected_value_cents": 500,
            "premium_cost_cents": 100,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "OBSERVE"
    assert body["side_effects"] == "none"
    assert body["execution_authority"] == "none"
    assert body["provider_activation"] is False
    assert body["premium_spend_execution"] is False
    assert body["budget_mutation"] is False
    assert body["model_promotion"] is False
    assert body["review"]["selected_route"] == "premium"
