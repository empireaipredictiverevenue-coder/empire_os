from __future__ import annotations

from empire_os.master_closure_ledger import (
    EXPECTED_MIGRATION_018_SHA256,
    classify_closure,
)


def test_current_closure_shape_classifies_real_gates() -> None:
    result = classify_closure(
        revenue_pulse={
            "highest_priority_blocker": "buyer_conversation",
            "recognized_revenue_truth": {"recognized_revenue_cents": 0},
        },
        sell_now={
            "ready_product_count": 26,
            "matched_route_count": 29,
            "sell_now_count": 0,
            "needs_review_count": 29,
        },
        buyer_acquisition={
            "outbound_sent": False,
            "icp_priority_target_count": 12,
        },
        commercial_exchange={
            "inventory_count": 10,
            "buyer_seat_count": 1057,
            "allocation_candidate_count": 0,
            "allocated_count": 0,
        },
        owned_campaigns={
            "campaigns_requested": 5,
            "campaigns_preflight_passed": 0,
            "campaigns_blocked": 5,
            "founder_db_approval_required": True,
            "publication_performed": False,
        },
        a2a_authentication_status="not_activated",
        production_dirty_total=191,
        production_failed_units=0,
        getlead_candidate_count=5,
        migration_018_sha256=EXPECTED_MIGRATION_018_SHA256,
        migration_025_exists=True,
    )
    by_key = {item["key"]: item for item in result["items"]}

    assert by_key["buyer_conversation"]["category"] == "EXTERNAL_SEND_GATE"
    assert by_key["sell_now"]["category"] == "INTERNAL_REVERSIBLE"
    assert by_key["owned_free_traffic"]["category"] == "FOUNDER_GATE"
    assert by_key["a2a_commerce"]["category"] == "INTERNAL_REVERSIBLE"
    assert by_key["buyer_acquisition_send"]["category"] == "EXTERNAL_SEND_GATE"
    assert by_key["commercial_exchange"]["category"] == "INTERNAL_REVERSIBLE"
    assert by_key["systemd_failed_units"]["category"] == "VERIFIED_COMPLETE"
    assert by_key["production_worktree"]["category"] == "CLEANUP"
    assert by_key["getlead_blitz_candidates"]["category"] == "CANDIDATE_PROMOTION"
    assert by_key["migration_018_protection"]["state"] == "CLEAR"
    assert by_key["migration_025_owned_campaign_intake"]["category"] == "FOUNDER_GATE"
    assert result["execution_authority"] == "none"
    assert result["external_send"] is False
    assert result["database_mutation"] is False
    assert result["payment_action"] is False
    assert result["revenue_recognition"] is False


def test_unknown_snapshots_do_not_become_complete() -> None:
    result = classify_closure(
        revenue_pulse=None,
        sell_now=None,
        buyer_acquisition=None,
        commercial_exchange=None,
        owned_campaigns=None,
        a2a_authentication_status=None,
        production_dirty_total=None,
        production_failed_units=None,
        getlead_candidate_count=None,
        migration_018_sha256=None,
        migration_025_exists=None,
    )
    by_key = {item["key"]: item for item in result["items"]}
    assert by_key["buyer_conversation"]["state"] == "UNKNOWN"
    assert by_key["sell_now"]["state"] == "UNKNOWN"
    assert by_key["owned_free_traffic"]["state"] == "UNKNOWN"
    assert by_key["migration_018_protection"]["state"] == "BLOCKED"
