import json

from empire_os.buyer_acquisition_team import refresh_buyer_acquisition_plan


def _write(root, relative, payload):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload))


def test_verified_permit_supply_prioritizes_home_service_buyer_hunt(tmp_path):
    _write(
        tmp_path,
        "runtime/commercial_exchange/latest.json",
        {
            "inventory": [],
            "buyer_seats": [],
            "supply_gate_diagnostics": {},
            "seat_activation_blocker_counts": {},
        },
    )
    _write(
        tmp_path,
        "runtime/commercial_catalog/latest.json",
        {"products": []},
    )
    _write(
        tmp_path,
        "runtime/recovery/legacy_permit_inventory_summary.json",
        {
            "verified_current_inventory": 400,
            "verified_current_owner_identified": 336,
            "verified_current_project_only": 64,
            "niche_counts": {
                "general_contractor": 397,
                "plumbing": 103,
            },
        },
    )

    payload = refresh_buyer_acquisition_plan(tmp_path)

    demand = payload["permit_inventory_demand"]
    assert demand["status"] == "ACTIVE"
    assert demand["verified_current_inventory"] == 400
    assert demand["buyer_hunt_target_count"] == 2
    assert demand["commercial_ready_claimed"] is False
    assert demand["allocation_authority"] == "none"
    assert demand["outbound_authority"] == "none"

    targets = payload["priority_targets"][:2]
    assert {row["niche_family"] for row in targets} == {
        "general contractor",
        "plumbing",
    }
    assert all(row["territory"] == "nyc" for row in targets)
    assert all(row["buyer_hunt_required"] is True for row in targets)
    assert all(
        row["product_code"] == "permit_intelligence"
        for row in targets
    )
    assert all(
        row["canonical_inventory_claimed"] is False
        for row in targets
    )
    assert all(row["research_queries"] for row in targets)


def test_missing_permit_summary_fails_closed_without_claiming_supply(tmp_path):
    _write(
        tmp_path,
        "runtime/commercial_exchange/latest.json",
        {
            "inventory": [],
            "buyer_seats": [],
            "supply_gate_diagnostics": {},
            "seat_activation_blocker_counts": {},
        },
    )
    _write(
        tmp_path,
        "runtime/commercial_catalog/latest.json",
        {"products": []},
    )

    payload = refresh_buyer_acquisition_plan(tmp_path)

    demand = payload["permit_inventory_demand"]
    assert demand["status"] == "NOT_MATERIALIZED"
    assert demand["verified_current_inventory"] == 0
    assert demand["buyer_hunt_target_count"] == 0
    assert demand["actual_revenue"] is False
    assert payload["runtime_input_health"]["degraded"] is True
