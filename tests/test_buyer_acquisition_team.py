from datetime import datetime, timezone

from empire_os.buyer_acquisition_team import (
    build_buyer_acquisition_plan,
    build_demand_gap_queue,
    direct_buyer_profile,
)


def test_direct_lead_buyer_evidence_scores_above_generic_agency():
    direct = direct_buyer_profile({
        "business_name": "Pipeline Exchange",
        "notes": "We buy leads and pay per lead for B2B campaigns",
    })
    agency = direct_buyer_profile({
        "business_name": "Acme Marketing Agency",
        "notes": "SEO and content services",
    })

    assert direct["buyer_type"] == "direct_lead_buyer"
    assert direct["explicit_direct_buyer_evidence"] is True
    assert direct["direct_buyer_score"] > agency["direct_buyer_score"]
    assert direct["binding_commercial_evidence"] is False


def test_overflow_corridor_becomes_top_buyer_hunt_priority():
    exchange = {
        "inventory": [
            {
                "corridor_key": (
                    "corridor:v1:roofing:austin_tx:"
                    "qualified_lead:lead"
                ),
                "state": "overflow_no_capacity",
            },
            {
                "corridor_key": (
                    "corridor:v1:roofing:austin_tx:"
                    "qualified_lead:lead"
                ),
                "state": "overflow_no_capacity",
            },
        ],
        "buyer_seats": [],
    }

    queue = build_demand_gap_queue(exchange)

    assert len(queue) == 1
    assert queue[0]["overflow_count"] == 2
    assert queue[0]["buyer_hunt_required"] is True
    assert queue[0]["acquisition_should_continue"] is True
    assert queue[0]["rank"] == 1


def test_blocked_seats_do_not_count_as_active_capacity():
    corridor = (
        "corridor:v1:roofing:austin_tx:qualified_lead:lead"
    )
    exchange = {
        "inventory": [
            {"corridor_key": corridor, "state": "allocation_candidate"},
        ],
        "buyer_seats": [
            {
                "corridor_key": corridor,
                "seat_state": "blocked_missing_evidence",
                "remaining_capacity": 100,
            },
        ],
    }

    queue = build_demand_gap_queue(exchange)

    assert queue[0]["active_remaining_capacity"] == 0
    assert queue[0]["blocked_seat_count"] == 1
    assert queue[0]["buyer_hunt_required"] is True


def test_plan_automates_internal_team_but_not_live_send():
    plan = build_buyer_acquisition_plan(
        {
            "inventory": [],
            "buyer_seats": [],
            "supply_gate_diagnostics": {
                "prospects_seen": 200,
                "qualification_ready_count": 0,
            },
            "seat_activation_blocker_counts": {
                "buyer_not_commercially_activated": 168,
            },
        },
        generated_at=datetime(
            2026, 9, 23, 0, 0, tzinfo=timezone.utc
        ),
    )

    assert plan["phase"] == "4"
    assert plan["team_role_count"] >= 8
    assert plan["automation"]["buyer_research_planning"] is True
    assert plan["automation"]["decision_maker_resolution"] is True
    assert plan["automation"]["commercial_evidence_extraction"] is True
    assert plan["automation"]["live_outbound_send"] is False
    assert plan["canonical_settlement_rail"] == "USDT_BSC"
    assert plan["legacy_buyer_hunter_is_canonical"] is False
    assert plan["buyer_capacity_never_gates_acquisition"] is True
    assert plan["execution_authority"] == "none"
