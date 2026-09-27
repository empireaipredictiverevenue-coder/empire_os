from empire_os.typed_decision_commercial_observations import (
    buyer_corridor_record_to_observation,
    routing_task_to_observation,
)


def test_buyer_corridor_observation_is_non_mutating():
    r=buyer_corridor_record_to_observation({
        "buyer_ref":"buyer:1",
        "corridor_ref":"roofing:manchester",
        "observed_at":"2026-09-20T10:00:00Z",
        "source_ref":"buyer-fit:1",
    })
    assert r["ready"] is True
    assert r["task_key"]=="buyer_corridor_fit"
    assert r["buyer_activation"] is False
    assert r["territory_allocation"] is False
    assert r["commercial_mutation"] is False


def test_agent_routing_observation_cannot_change_model_route():
    r=routing_task_to_observation({
        "task_ref":"task:1",
        "task_text":"Classify this buyer reply and route it.",
        "observed_at":"2026-09-20T10:00:00Z",
        "source_ref":"runtime:task:1",
        "observed_current_route":"general_reasoning",
    })
    assert r["ready"] is True
    assert r["task_key"]=="agent_routing"
    assert r["provider_activation"] is False
    assert r["model_route_mutation"] is False
    assert r["observed_current_route"]=="general_reasoning"


def test_missing_commercial_evidence_fails_closed():
    r=buyer_corridor_record_to_observation({"buyer_ref":"buyer:1"})
    assert r["ready"] is False
    assert "corridor_ref_required" in r["blockers"]
