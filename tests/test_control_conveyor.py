from empire_os.control_conveyor import build_conveyor


def test_conveyor_assigns_first_false_stage_to_owner():
    payload = build_conveyor({
        "loop_complete": False,
        "stages": [
            {"stage": "real_acquisition", "observed": True, "count": 20},
            {"stage": "qualification_v2", "observed": True, "count": 10},
            {"stage": "buyer_conversation", "observed": False, "count": 0},
            {"stage": "commercial_terms", "observed": False, "count": 0},
        ],
    })
    assert payload["current_blocker"] == "buyer_conversation"
    assert payload["owner_component"] == "conversation_os"
    assert payload["authority"] == "internal_write"
    assert payload["next_event"] == "buyer_conversation_observed"
    assert payload["controls_execution"] is False


def test_payment_blocker_requires_founder_gate():
    payload = build_conveyor({
        "stages": [
            {"stage": "buyer_conversation", "observed": True},
            {"stage": "verified_payment", "observed": False},
        ],
    })
    assert payload["current_blocker"] == "verified_payment"
    assert payload["owner_component"] == "payment_governor"
    assert payload["authority"] == "founder_gate"


def test_unknown_stage_stays_unknown():
    payload = build_conveyor({
        "stages": [{"stage": "future_signal", "observed": None}],
    })
    assert payload["unknown_stages"] == ["future_signal"]
    assert payload["current_blocker"] is None


def test_capacity_allocation_and_outcome_have_explicit_owners():
    payload = build_conveyor({
        "stages": [
            {"stage": "verified_buyer_capacity", "observed": False},
            {"stage": "inventory_allocation", "observed": False},
            {"stage": "commercial_outcome", "observed": False},
        ],
    })
    stages = {row["stage"]: row for row in payload["stages"]}
    assert stages["verified_buyer_capacity"]["owner_component"] == "buyer_capacity"
    assert stages["verified_buyer_capacity"]["authority"] == "internal_write"
    assert stages["inventory_allocation"]["owner_component"] == "fulfilment"
    assert stages["commercial_outcome"]["owner_component"] == "outcome_feedback"
