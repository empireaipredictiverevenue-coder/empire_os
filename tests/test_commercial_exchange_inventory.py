from datetime import datetime, timezone

from empire_os.commercial_exchange_inventory import (
    build_exchange_snapshot,
    corridor_key,
    project_buyer_seats,
)


PROSPECT_ID = "11111111-1111-4111-8111-111111111111"
ENTITY_ID = "22222222-2222-4222-8222-222222222222"


def prospect(pid=PROSPECT_ID, niche="roofing", metro="Austin, TX"):
    return {
        "id": pid,
        "business_name": "Austin Roof Co",
        "niche": niche,
        "metro": metro,
    }


def qualification(pid=PROSPECT_ID):
    return {
        "prospect_id": pid,
        "entity_id": ENTITY_ID,
        "score": 82,
        "tier": "hot",
        "status": "scored",
        "scoring_version": "v1",
    }


def identity(pid=PROSPECT_ID):
    return {
        "prospect_id": pid,
        "entity_id": ENTITY_ID,
        "match_score": 1.0,
        "active": True,
    }


def buyer(*, cap=10, used=0, buyer_id="buyer-1"):
    return {
        "id": buyer_id,
        "buyer_name": "Roof Buyer",
        "niche": "roofing",
        "metro": "Austin, TX",
        "is_active": True,
        "status": "active",
        "daily_cap": cap,
        "calls_today": used,
        "priority": 50,
        "per_lead_rate": 75,
        "destination_phone": "+15125550123",
        "webhook_url": None,
        "reviewed_at": "2026-09-17T10:00:00Z",
        "commercial_activation_state": "activated",
        "commercial_activated_at": "2026-09-17T10:01:00Z",
        "commercial_terms_source": "manual_contract",
        "commercial_terms_reference": "contract:test",
        "commercial_terms_verified_at": "2026-09-17T10:01:00Z",
        "capacity_verified_at": "2026-09-17T10:01:00Z",
        "delivery_verified_at": "2026-09-17T10:01:00Z",
    }


def test_corridor_identity_is_deterministic():
    assert corridor_key("roofing", "austin, tx") == (
        "corridor:v1:roofing:austin_tx:qualified_lead:lead"
    )


def test_verified_buyer_becomes_active_seat_without_binding_price_claim():
    rows = project_buyer_seats([buyer()])
    assert len(rows) == 1
    seat = rows[0]
    assert seat["seat_state"] == "active_capacity"
    assert seat["remaining_capacity"] == 10
    assert seat["observed_rate"] == 75
    assert seat["binding_price_claimed"] is False
    assert seat["exclusivity_claimed"] is False


def test_full_buyer_creates_overflow_but_does_not_stop_acquisition():
    snapshot = build_exchange_snapshot(
        prospects=[prospect()],
        qualifications={PROSPECT_ID: qualification()},
        identity_links={PROSPECT_ID: identity()},
        buyers=[buyer(cap=1, used=1)],
        observed_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )
    assert snapshot["inventory_state_counts"] == {
        "overflow_no_capacity": 1
    }
    assert snapshot["overflow_count"] == 1
    assert snapshot["inventory"][0]["empire_owned"] is True
    assert snapshot["buyer_capacity_never_gates_acquisition"] is True


def test_capacity_available_creates_allocation_candidate_only():
    snapshot = build_exchange_snapshot(
        prospects=[prospect()],
        qualifications={PROSPECT_ID: qualification()},
        identity_links={PROSPECT_ID: identity()},
        buyers=[buyer()],
        observed_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )
    row = snapshot["inventory"][0]
    assert row["state"] == "allocation_candidate"
    assert row["candidate_count"] == 1
    assert row["empire_owned"] is True
    assert snapshot["automatic_external_delivery"] is False


def test_missing_identity_blocks_without_fake_inventory_route():
    snapshot = build_exchange_snapshot(
        prospects=[prospect()],
        qualifications={PROSPECT_ID: qualification()},
        identity_links={PROSPECT_ID: None},
        buyers=[buyer()],
        observed_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )
    row = snapshot["inventory"][0]
    assert row["state"] == "blocked_missing_evidence"
    assert row["reason"] == "missing_active_identity_link"
    assert row["empire_owned"] is True


def test_existing_allocation_is_not_counted_as_owned_overflow():
    snapshot = build_exchange_snapshot(
        prospects=[prospect()],
        qualifications={PROSPECT_ID: qualification()},
        identity_links={PROSPECT_ID: identity()},
        buyers=[],
        allocated_prospect_ids={PROSPECT_ID},
        observed_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )
    row = snapshot["inventory"][0]
    assert row["state"] == "allocated"
    assert row["empire_owned"] is False
    assert snapshot["allocated_count"] == 1


def test_unqualified_prospect_is_not_promoted_to_exchange_inventory():
    snapshot = build_exchange_snapshot(
        prospects=[prospect()],
        qualifications={PROSPECT_ID: None},
        identity_links={PROSPECT_ID: None},
        buyers=[buyer()],
        observed_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )
    assert snapshot["inventory"] == []
    assert snapshot["inventory_count"] == 0


def test_supply_gate_diagnostics_preserve_qualification_and_identity_blockers():
    ready_id = "33333333-3333-4333-8333-333333333333"
    blocked_id = "44444444-4444-4444-8444-444444444444"

    snapshot = build_exchange_snapshot(
        prospects=[
            prospect(pid=ready_id),
            prospect(pid=blocked_id),
        ],
        qualifications={
            ready_id: {
                **qualification(pid=ready_id),
                "entity_id": ENTITY_ID,
            },
            blocked_id: None,
        },
        identity_links={
            ready_id: {
                **identity(pid=ready_id),
                "entity_id": ENTITY_ID,
            },
            blocked_id: None,
        },
        buyers=[],
        observed_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )

    diagnostics = snapshot["supply_gate_diagnostics"]
    assert diagnostics["prospects_seen"] == 2
    assert diagnostics["qualification_ready_count"] == 1
    assert diagnostics["exchange_inventory_ready_count"] == 1
    assert diagnostics["qualification_blocker_counts"] == {
        "missing_qualification": 1
    }


def test_seat_activation_blockers_are_counted_without_weakening_gate():
    blocked = buyer()
    blocked["commercial_activation_state"] = "discovered"

    snapshot = build_exchange_snapshot(
        prospects=[],
        qualifications={},
        identity_links={},
        buyers=[blocked],
        observed_at=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )

    assert snapshot["seat_activation_blocker_counts"] == {
        "buyer_not_commercially_activated": 1
    }
    assert snapshot["buyer_seats"][0]["seat_state"] == (
        "blocked_missing_evidence"
    )
