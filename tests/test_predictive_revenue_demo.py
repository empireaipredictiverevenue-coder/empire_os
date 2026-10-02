import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.predictive_revenue_demo import (
    build_predictive_revenue_demo,
    render_predictive_revenue_demo_html,
)
from empire_os.predictive_revenue_demo_api import (
    create_predictive_revenue_demo_router,
)


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def demo_root(tmp_path: Path) -> Path:
    root = tmp_path / "repo"

    write_json(root / "runtime/autonomous_revenue_os/latest.json", {
        "release_id": "autonomous-revenue-os-v1",
        "status": "ACTIVE",
        "cycle_at": "2026-10-02T16:49:10+00:00",
        "inventory": {
            "classified": 200,
            "counts": {
                "RAW_LEAD": 169,
                "PREQUALIFIED_LEAD": 31,
                "QUALIFIED_CALL": 0,
                "BOOKED_APPOINTMENT": 0,
                "CPA_OUTCOME": 0,
            },
        },
        "review_queue": [{}, {}],
        "next_action": {"action": "qualify_new_leads"},
        "communications_execution": False,
        "booking_execution": False,
    })
    write_json(root / "runtime/predictive_cloud/status_latest.json", {
        "available_component_count": 24,
        "component_count": 26,
        "unavailable_components": ["future_trend_intelligence"],
        "stale_components": ["market_gps"],
        "mode": "OBSERVE",
    })
    write_json(root / "runtime/astra/executive_latest.json", {
        "plan_id": "plan-1",
        "primary_goal": {"key": "advance_first_verified_revenue"},
        "plan_step_count": 8,
        "auto_dispatch_eligible_count": 7,
        "departments_in_plan": ["sales_revenue", "data_quant"],
        "goals": [{
            "key": "advance_first_verified_revenue",
            "priority": 98,
            "objective": "Advance genuine commercial state.",
            "reason": "recognized revenue is zero",
        }],
        "external_execution_performed": False,
    })
    write_json(root / "runtime/opportunity_radar/loop_latest.json", {
        "radar_candidate_count": 21,
        "research_observation_count": 2,
        "total_normalized_scores": 42,
        "factory_ready_count": 0,
        "factory_blocked_count": 21,
        "quant_decision_packet_available_count": 0,
        "quant_decision_packet_unavailable_count": 21,
    })
    write_json(root / "runtime/opportunity_factory/quant_review_latest.json", {
        "missing_field_counts": {
            "confidence": 21,
            "probability_success": 21,
        }
    })
    write_json(root / "runtime/opportunity_factory/value_latest.json", {
        "candidate_count": 21,
        "actual_revenue": False,
    })
    write_json(root / "runtime/buyer_acquisition/latest.json", {
        "buyer_pool_count": 6,
        "priority_target_count": 32,
        "product_demand_count": 36,
        "sellable_product_demand_count": 26,
    })
    write_json(root / "runtime/commercial_exchange/latest.json", {
        "buyer_seat_count": 1057,
        "corridor_count": 149,
        "inventory_count": 160,
        "supply_gate_diagnostics": {
            "exchange_inventory_ready_count": 78,
        },
    })
    write_json(root / "runtime/revenue_exchange/latest.json", {
        "market_count": 0,
    })
    write_json(root / "runtime/buyer_capacity_readiness/latest.json", {
        "commercially_activated": 0,
        "capacity_verified": 0,
        "terms_verified": 0,
        "highest_priority_blocker": "verified_commercial_terms",
    })
    write_json(root / "runtime/commercial_catalog/latest.json", {
        "product_count": 2,
        "active_count": 1,
        "binding_terms_ready_count": 1,
        "products": [{
            "active": True,
            "binding_terms_ready": True,
            "product_code": "permit_intelligence",
            "product_name": "Permit Intelligence",
            "product_family": "search_intelligence",
            "billing_model": "monthly_subscription",
            "currency": "USD",
            "price_basis": {
                "amount_cents": 49900,
                "unit": "per_month",
                "state": "VERIFIED",
            },
        }],
    })
    write_json(root / "runtime/revenue_pulse/latest.json", {
        "current_window": {
            "label": "current_24h",
            "acquisitions": 382,
            "qualified": 8,
            "buyer_reviews": 0,
            "delivered_outreach": 0,
            "commercial_replies": 0,
            "commercial_terms": 0,
            "verified_payments": 0,
            "fulfilments": 0,
        },
        "recognized_revenue_truth": {
            "recognized_revenue_cents": 0,
            "realized_gp_cents": 0,
            "forecast_included_in_truth": False,
        },
        "highest_priority_blocker": "buyer_conversation",
        "pulse_state": "pipeline_building",
    })
    write_json(root / "runtime/predictive_revenue/enterprise_targets_latest.json", {
        "target_count": 1,
        "targets": [{
            "account_name": "Example Enterprise",
            "account_type": "home_services_platform",
            "wave": "direct_enterprise",
            "target_product_codes": ["predictive_revenue_autonomous_os"],
            "observed_scale": ["national platform"],
            "observed_triggers": ["data transformation"],
            "observed_people": [{"name": "Alex", "title": "CEO"}],
            "fit_classification": "INTERNAL_HYPOTHESIS",
            "contact_verified": False,
            "budget_verified": False,
            "commercial_terms_verified": False,
            "outreach_authorized": False,
        }],
    })
    write_json(root / "runtime/predictive_revenue/enterprise_pool_latest.json", {
        "total_enterprise_candidate_count": 59,
        "eligible_rolling_candidate_count": 159,
    })
    write_json(root / "runtime/predictive_revenue/enterprise_contact_intelligence_latest.json", {
        "targeted_retry_queued_count": 32,
        "error_count": 0,
    })
    write_json(root / "runtime/economic_memory/latest.json", {
        "department_episode_count": 8,
        "outcome_conditioned_memory_count": 0,
        "verified_outcomes_only": True,
        "model_weight_mutation_authorized": False,
    })
    return root


def test_demo_is_living_proof_and_keeps_modelled_value_separate(tmp_path):
    payload = build_predictive_revenue_demo(demo_root(tmp_path))

    assert payload["living_proof"] is True
    assert payload["mode"] == "LIVE_READ_ONLY"
    assert payload["revenue_operating_system"]["inventory_counts"]["PREQUALIFIED_LEAD"] == 31
    assert payload["predictive_cloud"]["available_component_count"] == 24
    assert payload["buyer_market"]["buyer_seat_count"] == 1057
    assert payload["enterprise_predictive_revenue"]["private_deployment"]["price_cents"] == 25_000_000
    assert payload["enterprise_predictive_revenue"]["private_deployment"]["actual_revenue"] is False
    assert payload["revenue_truth"]["recognized_revenue_cents"] == 0
    assert payload["revenue_truth"]["actual_revenue"] is False
    assert payload["truth_contract"]["predicted_is_not_actual_revenue"] is True
    assert payload["side_effects"] == "none"
    assert payload["execution_authority"] == "none"


def test_demo_preserves_missing_quant_evidence_as_incomplete(tmp_path):
    payload = build_predictive_revenue_demo(demo_root(tmp_path))

    intelligence = payload["opportunity_intelligence"]
    assert intelligence["prediction_state"] == "EVIDENCE_INCOMPLETE"
    assert intelligence["quant_decision_packet_available_count"] == 0
    assert intelligence["quant_missing_field_counts"]["confidence"] == 21


def test_demo_catalog_only_surfaces_active_binding_ready_products(tmp_path):
    payload = build_predictive_revenue_demo(demo_root(tmp_path))

    rows = payload["commercial_catalog"]["active_binding_products"]
    assert rows == [{
        "product_code": "permit_intelligence",
        "product_name": "Permit Intelligence",
        "product_family": "search_intelligence",
        "billing_model": "monthly_subscription",
        "currency": "USD",
        "amount_cents": 49900,
        "unit": "per_month",
        "price_state": "VERIFIED",
        "actual_revenue": False,
    }]


def test_demo_api_and_live_html_are_read_only(tmp_path):
    app = FastAPI()
    app.include_router(create_predictive_revenue_demo_router(demo_root(tmp_path)))
    client = TestClient(app)

    response = client.get("/v1/predictive-revenue/demo")
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "LIVE_READ_ONLY"
    assert body["execution_authority"] == "none"

    html = client.get("/v1/predictive-revenue/demo/live")
    assert html.status_code == 200
    assert "Predictive Revenue" in html.text
    assert "Living proof chain" in html.text
    assert "$250,000+" in html.text
    assert "Recognized revenue truth" in html.text
    assert "forecast/modelled value excluded" in html.text


def test_rendered_html_does_not_turn_private_model_into_revenue(tmp_path):
    payload = build_predictive_revenue_demo(demo_root(tmp_path))
    html = render_predictive_revenue_demo_html(payload)

    assert "$250,000+" in html
    assert "modelled economics, not revenue" in html
    assert "Recognized revenue truth" in html
    assert "$0" in html
