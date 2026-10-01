from __future__ import annotations

import json
from pathlib import Path

from empire_os.founder_operational_truth import build_operational_truth


def _write(tmp_path: Path, name: str, payload: dict) -> Path:
    path = tmp_path / name
    path.write_text(json.dumps(payload))
    return path


def test_truth_board_surfaces_revenue_and_founder_gates(tmp_path: Path) -> None:
    paths = {
        "revenue_pulse": _write(tmp_path, "pulse.json", {
            "pulse_state": "conversation_blocked",
            "highest_priority_blocker": "buyer_conversation",
            "recognized_revenue_truth": {"recognized_revenue_cents": 0},
        }),
        "sell_now": _write(tmp_path, "sell.json", {
            "sell_now_count": 0,
            "ready_product_count": 26,
            "matched_route_count": 29,
            "needs_review_count": 29,
        }),
        "buyer_acquisition": _write(tmp_path, "buyers.json", {
            "outbound_sent": False,
            "icp_priority_target_count": 12,
            "sellable_product_demand_count": 26,
        }),
        "commercial_exchange": _write(tmp_path, "exchange.json", {
            "inventory_count": 10,
            "buyer_seat_count": 1057,
            "corridor_count": 69,
            "allocation_candidate_count": 0,
            "allocated_count": 0,
        }),
        "owned_campaigns": _write(tmp_path, "campaigns.json", {
            "campaigns_requested": 5,
            "campaigns_preflight_passed": 0,
            "campaigns_blocked": 5,
            "founder_db_approval_required": True,
            "publication_performed": False,
        }),
    }

    result = build_operational_truth(paths=paths)
    by_key = {lane["key"]: lane for lane in result["lanes"]}

    assert by_key["buyer_conversations"]["state"] == "BLOCKED"
    assert by_key["verified_revenue"]["state"] == "BLOCKED"
    assert by_key["sell_now"]["state"] == "BLOCKED"
    assert by_key["owned_free_traffic"]["state"] == "GATED"
    assert by_key["owned_free_traffic"]["founder_gate"] is True
    assert by_key["a2a_commerce"]["state"] == "GATED"
    assert by_key["buyer_acquisition"]["state"] == "READY"
    assert by_key["commercial_exchange"]["state"] == "BLOCKED"
    assert result["execution_authority"] == "none"
    assert result["external_send"] is False
    assert result["payment_action"] is False
    assert result["revenue_recognition"] is False


def test_missing_snapshots_stay_unknown(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    result = build_operational_truth(paths={
        "revenue_pulse": missing,
        "sell_now": missing,
        "buyer_acquisition": missing,
        "commercial_exchange": missing,
        "owned_campaigns": missing,
    })
    by_key = {lane["key"]: lane for lane in result["lanes"]}
    assert by_key["verified_revenue"]["state"] == "UNKNOWN"
    assert by_key["sell_now"]["state"] == "UNKNOWN"
    assert by_key["owned_free_traffic"]["state"] == "UNKNOWN"
