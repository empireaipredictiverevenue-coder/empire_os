"""Canonical Exchange inventory is observed, never inferred from sniper posts."""
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from empire_os.lead_exchange_live_inventory import build_lead_exchange_live_inventory
from empire_os.founder_lead_supply_api import (
    create_founder_lead_supply_router, read_lead_exchange_inventory,
)

NOW = datetime(2026, 10, 19, 13, 35, tzinfo=timezone.utc)


def fixture():
    row = lambda id, state, family="solar", metro="London": {
        "prospect_id": id, "state": state, "niche_family": family,
        "metro": metro, "corridor_key": "corridor:v1:solar:london:qualified_lead:lead",
        "candidate_count": 0, "empire_owned": state != "allocated",
        "private_email": "never-expose@example.com",
    }
    return {
        "schema_version": "empire.commercial_exchange_snapshot.v1",
        "mode": "OBSERVE",
        "observed_at": NOW.isoformat(),
        "source": "canonical_empiredb_projection",
        "canonical_backend": "empiredb",
        "execution_authority": "none",
        "automatic_external_delivery": False,
        "inventory": [
            row("prospect-1", "blocked_missing_evidence"),
            row("prospect-2", "overflow_no_capacity"),
            row("prospect-3", "allocation_candidate"),
            row("prospect-4", "allocated"),
        ],
        "inventory_count": 4,
        "inventory_state_counts": {
            "blocked_missing_evidence": 1, "overflow_no_capacity": 1,
            "allocation_candidate": 1, "allocated": 1,
        },
        "allocation_candidate_count": 1,
        "overflow_count": 1,
        "blocked_missing_evidence_count": 1,
        "allocated_count": 1,
        "buyer_seats": [
            {
                "buyer_id": "private-buyer-001",
                "buyer_name": "Confidential buyer",
                "seat_state": "active_capacity",
                "remaining_capacity": 1,
            },
        ],
        "buyer_seat_count": 1,
        "seat_state_counts": {"active_capacity": 1},
    }


def test_valid_canonical_snapshot_exposes_market_counts_not_records():
    result = build_lead_exchange_live_inventory(fixture(), now=NOW)
    assert result["state"] == "FRESH_CANONICAL_SNAPSHOT"
    assert result["selected_inventory_records"] == 4
    assert result["evidence_hold_records"] == 1
    assert result["buyer_capacity_waitlist_records"] == 1
    assert result["allocation_candidate_records"] == 1
    assert result["allocated_records"] == 1
    assert result["active_capacity_seat_records"] == 1
    assert result["delivery_ready_now"] == 0
    assert result["markets"][0]["niche"] == "solar"
    assert result["markets"][0]["selected_inventory_records"] == 4
    assert result["public_endpoint_activated"] is False
    assert result["outbound_authorized"] is False
    report = json.dumps(result)
    assert "private-buyer-001" not in report
    assert "prospect-1" not in report
    assert "Confidential buyer" not in report
    assert "never-expose" not in report


def test_scanner_packet_is_research_only_not_added_to_exchange_stock():
    p = {
        "schema_version": "empire.scrapling_sniper_handoff.v1",
        "state": "SNIPER_REVIEW_PACKET_PREPARED",
        "canonical_database_writes": False,
        "outbound_authorized": False,
        "live_sniper_queue_authorized": False,
        "company_name": "Private candidate",
    }
    result = build_lead_exchange_live_inventory(fixture(), now=NOW, sniper_packets=[p, p])
    assert result["selected_inventory_records"] == 4
    assert result["sniper_evidence"]["review_packet_count_not_inventory"] == 2
    assert result["sniper_evidence"]["included_in_canonical_inventory_count"] is False
    assert "Private candidate" not in json.dumps(result)


def test_missing_market_identity_does_not_erase_held_records():
    data = fixture()
    data["inventory"][0]["niche_family"] = None
    data["inventory"][0]["metro"] = None
    data["inventory"][0]["corridor_key"] = None
    result = build_lead_exchange_live_inventory(data, now=NOW)
    assert result["state"] == "FRESH_CANONICAL_SNAPSHOT"
    assert result["selected_inventory_records"] == 4
    assert result["evidence_hold_records"] == 1
    assert any(x["niche"] == "unclassified" for x in result["markets"])


def test_missing_market_identity_cannot_be_called_allocatable():
    data = fixture()
    data["inventory"][2]["corridor_key"] = None
    assert build_lead_exchange_live_inventory(data, now=NOW)["state"] == "HOLD"


@pytest.mark.parametrize("field,value", [
    ("source", "canonical_supabase_projection"),
    ("canonical_backend", "supabase_legacy"),
    ("mode", "LIVE_EXECUTION"),
    ("automatic_external_delivery", True),
    ("execution_authority", "send"),
    ("inventory_count", 999),
    ("buyer_seat_count", 99),
    ("inventory_state_counts", {"allocation_candidate": 4}),
    ("seat_state_counts", {"active_capacity": 50}),
])
def test_invalid_snapshot_contracts_fail_closed(field, value):
    data = fixture()
    data[field] = value
    assert build_lead_exchange_live_inventory(data, now=NOW)["state"] == "HOLD"


def test_duplicate_canonical_id_cannot_inflate_count():
    data = fixture()
    data["inventory"][1]["prospect_id"] = "prospect-1"
    assert build_lead_exchange_live_inventory(data, now=NOW)["state"] == "HOLD"


def test_stale_snapshot_retained_as_historical_with_no_ready_claim():
    data = fixture()
    data["observed_at"] = (NOW - timedelta(days=1)).isoformat()
    result = build_lead_exchange_live_inventory(data, now=NOW)
    assert result["state"] == "STALE_CANONICAL_SNAPSHOT"
    assert result["snapshot_fresh"] is False
    assert result["selected_inventory_records"] == 4
    assert result["delivery_ready_now"] == 0


def test_untrusted_sniper_packet_blocks_all_claims():
    packet = {
        "schema_version": "empire.scrapling_sniper_handoff.v1",
        "state": "SNIPER_REVIEW_PACKET_PREPARED",
        "canonical_database_writes": False, "outbound_authorized": True,
    }
    assert build_lead_exchange_live_inventory(
        fixture(), sniper_packets=[packet], now=NOW
    )["state"] == "HOLD"


def test_missing_exchange_read_returns_unavailable_not_zero_stock(tmp_path):
    result = read_lead_exchange_inventory(tmp_path / "not-present.json")
    assert result["available"] is False
    assert result["state"] == "HOLD"
    assert result["delivery_ready_now"] == 0
    assert "selected_inventory_records" not in result


def test_private_founder_lead_supply_inventory_route_is_no_write(tmp_path):
    p = tmp_path / "exchange.json"
    data = fixture()
    data["observed_at"] = datetime.now(timezone.utc).isoformat()
    p.write_text(json.dumps(data))
    app = FastAPI()
    app.include_router(create_founder_lead_supply_router(
        report_path=tmp_path / "missing-lead-supply.json",
        exchange_path=p,
    ))
    response = TestClient(app).get("/v1/founder-lead-supply/inventory")
    assert response.status_code == 200
    result = response.json()
    assert result["available"] is True
    assert result["selected_inventory_records"] == 4
    assert result["delivery_ready_now"] == 0
    assert result["execution_authority"] == "none"
    assert "prospect-1" not in response.text
    assert "Confidential buyer" not in response.text
    assert p.read_text() == json.dumps(data)


def test_cli_uses_existing_local_exchange_snapshot_without_writing(tmp_path, capsys):
    from scripts.review_lead_exchange_live_inventory_20261019 import main
    data = fixture()
    data["observed_at"] = datetime.now(timezone.utc).isoformat()
    path = tmp_path / "latest.json"
    original = json.dumps(data)
    path.write_text(original)
    assert main(["--read-only", "--snapshot", str(path)]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["selected_inventory_records"] == 4
    assert result["delivery_ready_now"] == 0
    assert result["execution_authority"] == "none"
    assert path.read_text() == original


def test_cli_malformed_file_fails_without_source_leak(tmp_path, capsys):
    from scripts.review_lead_exchange_live_inventory_20261019 import main
    path = tmp_path / "latest.json"
    path.write_text("private person and company details not JSON")
    assert main(["--read-only", "--snapshot", str(path)]) == 2
    out = capsys.readouterr().out
    assert "private person" not in out
    assert json.loads(out)["state"] == "HOLD"
