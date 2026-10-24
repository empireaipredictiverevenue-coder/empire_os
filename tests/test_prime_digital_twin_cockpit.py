"""Original Founder read-only synthetic Twin cockpit and fixture isolation."""
from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from empire_os.prime_digital_twin_cockpit import build_prime_digital_twin_cockpit
from empire_os.founder_dashboard_service import build_founder_dashboard_service


def test_cockpit_renders_original_synthetic_baseline_without_source_connections():
    item = build_prime_digital_twin_cockpit()
    assert item["schema_version"] == "empire.prime.original_private_digital_twin_cockpit.v1"
    assert item["mode"] == "SIMULATION"
    assert item["selected_scenario_id"] == "pricing_resolution"
    assert item["selected_fractal"]["total_nodes"] == 7
    assert item["all_synthetic_baseline"]["scripted_scenarios"] == 16
    assert item["all_synthetic_baseline"]["scripted_contract_passes"] == 16
    assert item["all_synthetic_baseline"]["fractal_nodes_at_depth_two"] == 112
    assert item["real_world_predictive_accuracy"] is None
    assert item["recognized_revenue_cents"] is None
    assert item["real_buyer_intent_verified"] is False
    assert item["real_messages_sent"] is False
    assert item["original_empiredb_writes"] is False
    assert item["local_model_selfplay"]["status"] == "NOT_RUN"
    assert item["local_model_active_in_this_read_only_request"] is False


def test_original_fictional_conversation_is_visualisable_but_not_real_buyer():
    item = build_prime_digital_twin_cockpit(
        scenario_id="scope_reopened", fractal_depth=1,
    )
    talk = item["selected_scenario"]["simulated_dialogue"]
    assert len(talk) == 4
    assert item["selected_fractal"]["total_nodes"] == 3
    assert all(message["simulated"] is True for message in talk)
    assert all(message["real_person"] is False for message in talk)
    assert item["selected_scenario"]["outcome_state_not_provider_verified"] == "REOPENED"


def test_original_fictional_optout_cannot_trigger_a_seller_message():
    item = build_prime_digital_twin_cockpit(
        scenario_id="explicit_optout", fractal_depth=0,
    )
    assert item["selected_scenario"]["synthetic_turn_count"] == 1
    assert item["selected_scenario"]["simulated_dialogue"][0]["actor"] == "FICTIONAL_BUYER_TWIN"
    assert item["selected_scenario"]["loop_guard"]["status"] == "SIMULATED_STOP_NO_FOLLOWUP"
    assert item["real_messages_sent"] is False


@pytest.mark.parametrize("scenario,depth", [
    ("private-person-id", -1),
    ("unknown", 1),
    ("https://bad.test", 1),
    ("pricing_resolution", 4),
    ("pricing_resolution", True),
])
def test_arbitrary_input_and_unbounded_fractal_depth_fail_closed(scenario,depth):
    with pytest.raises(ValueError):
        build_prime_digital_twin_cockpit(scenario_id=scenario, fractal_depth=depth)


def test_founder_read_service_exposes_only_get_rehearsal_and_no_inference_trigger():
    with TestClient(build_founder_dashboard_service()) as c:
        response = c.get("/v1/founder-dashboard/prime-digital-twin?scenario=privacy_silence&depth=1")
        assert response.status_code == 200
        body = response.json()
        assert body["selected_scenario_id"] == "privacy_silence"
        assert body["selected_fractal"]["total_nodes"] == 3
        assert body["local_model_active_in_this_read_only_request"] is False
        assert body["execution_authority"] == "none"
        assert body["real_messages_sent"] is False
        assert c.post("/v1/founder-dashboard/prime-digital-twin").status_code == 405


def test_original_founder_read_endpoint_rejects_arbitrary_text_and_depth():
    with TestClient(build_founder_dashboard_service()) as c:
        assert c.get("/v1/founder-dashboard/prime-digital-twin?scenario=not_in_catalog").status_code == 400
        assert c.get("/v1/founder-dashboard/prime-digital-twin?depth=9").status_code == 422
        assert c.get("/v1/founder-dashboard/prime-digital-twin?scenario=mail%40private.test").status_code == 400


def test_original_read_cockpit_does_not_invoke_local_model(monkeypatch):
    from empire_os.coder.llama_cpp_provider import LlamaCppProvider
    def forbidden(*args, **kwargs):
        raise AssertionError("Founder GET may not start local inference")
    monkeypatch.setattr(LlamaCppProvider, "chat", forbidden)
    result = build_prime_digital_twin_cockpit(fractal_depth=2)
    assert result["all_synthetic_baseline"]["fractal_nodes_at_depth_two"] == 112
