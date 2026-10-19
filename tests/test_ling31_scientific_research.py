"""Ling 3.1 free route + source science must never claim unverified inference."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from empire_os.model_registry import ModelRegistry
from empire_os.model_router import ModelRouter
from empire_os.ling31_research_readiness import (
    MODEL_ID, ZEN_SLUG, probe_ling31_free,
    review_ling31_free_readiness, scientific_research_protocol,
)
from empire_os.revenue_stream_mining import build_revenue_stream_mining

NOW = datetime(2026, 10, 19, 18, 0, tzinfo=timezone.utc)
ROOT = Path(__file__).resolve().parents[1]


def test_free_opencode_model_registered_but_not_automatically_routable():
    registry = ModelRegistry(str(ROOT/"config/model_registry.json"))
    model = registry.get(MODEL_ID)
    assert model is not None
    assert model.provider == "opencode"
    assert model.model == "ling-3.1-flash-free"
    assert model.free is True
    assert model.enabled is False
    assert model.available is False
    assert model.allow_untrusted_input is False
    assert "payment" in model.disallowed_tasks
    assert "outbound" in model.disallowed_tasks
    assert "revenue_truth" in model.disallowed_tasks
    assert model.max_stakes == "normal"
    assert MODEL_ID not in {item.model_id for item in registry.all()}
    selection = ModelRouter(registry=registry).route(
        task="research",
        messages=[{"role":"user","content":"Check public-source calibration issues"}],
        budget_remaining=0.0,
        remaining_queries=1,
    )
    assert selection.model.model_id != MODEL_ID


def test_readiness_does_not_mistake_catalogued_model_for_working_inference():
    registry = ModelRegistry(str(ROOT/"config/model_registry.json"))
    result = review_ling31_free_readiness(as_of=NOW, registry=registry)
    assert result["model_catalogue_entry_present"] is True
    assert result["router_blocks_unverified_model"] is True
    assert result["actual_live_inference_verified"] is False
    assert result["status"] == "FREE_CATALOGUED_RUNTIME_UNAVAILABLE"
    assert result["configured_to_use_paid_endpoint"] is False
    assert result["source_contacts_and_secrets_to_model_authorized"] is False
    assert result["model_calibrated_on_EmpireOS"] is False


class StubClient:
    def __init__(self, response, *, name=ZEN_SLUG, key=True):
        self.model = name
        self.api_key = "REDACTED_STUB" if key else None
        self.response = response
        self.calls = []
    def chat(self, messages, **kwargs):
        self.calls.append((messages, kwargs))
        return self.response


@pytest.mark.parametrize("answer,expected", [
    ("PONG", True),
    ("other answer", False),
    ('{"error":"zen_failed"}', False),
    (None, False),
])
def test_single_public_probe_never_activates_route_or_uses_private_data(
    answer, expected,
):
    client = StubClient(answer)
    result = probe_ling31_free(client_factory=lambda: client)
    assert result["successful_inference"] is expected
    assert result["model_activated"] is False
    assert result["charged_paid_model"] is False
    assert result["execution_authority"] == "none"
    assert len(client.calls) == 1
    prompt, params = client.calls[0]
    assert prompt == [{"role":"user","content":"Respond exactly with PONG."}]
    assert params["max_tokens"] == 12


def test_no_credentials_never_invokes_provider():
    client = StubClient("PONG", key=False)
    result = probe_ling31_free(client_factory=lambda: client)
    assert result["status"] == "NO_EXISTING_ZEN_CREDENTIALS"
    assert client.calls == []


def test_slug_cannot_change_to_paid_or_unknown_route():
    client = StubClient("PONG", name="ling-3.1-flash")
    with pytest.raises(ValueError, match="no paid fallback"):
        probe_ling31_free(client_factory=lambda: client)
    assert client.calls == []


def test_scientific_protocol_uses_existing_reasoning_but_no_posterior(tmp_path):
    result = build_revenue_stream_mining(tmp_path, as_of=NOW)
    review = scientific_research_protocol(result, as_of=NOW)
    assert review["scientific_reasoning_is_heuristic"] is True
    assert review["probability_calibrated"] is False
    assert review["posterior_probability"] is None
    assert review["control_results_verified"] is False
    assert len(review["controls_to_execute"]) == 7
    assert review["scientific_agent_invoked"] is False
    assert review["openmanus_executed"] is False
    assert review["ling_inference_invoked"] is False
    assert review["research_brief_for_optional_agents"]["tool_execution_authorized"] is False
    assert review["research_brief_for_optional_agents"]["max_external_spend_cents"] == 0
    assert review["execution_authority"] == "none"


def test_scientific_sources_fail_closed_if_status_or_aggregate_tampered(tmp_path):
    result = build_revenue_stream_mining(tmp_path, as_of=NOW)
    forged = deepcopy(result)
    forged["sources"]["competitor"]["status"] = "PAID_BY_CUSTOMER"
    with pytest.raises(ValueError, match="science source status"):
        scientific_research_protocol(forged, as_of=NOW)
    forged = deepcopy(result)
    forged["sources"]["competitor"]["aggregate"] = {"private":"fake"}
    with pytest.raises(ValueError, match="untrusted aggregate"):
        scientific_research_protocol(forged, as_of=NOW)


def test_source_science_cannot_grant_commercial_execution(tmp_path):
    result = build_revenue_stream_mining(tmp_path, as_of=NOW)
    forged = deepcopy(result)
    forged["execution_authority"] = "full"
    with pytest.raises(ValueError):
        scientific_research_protocol(forged, as_of=NOW)
