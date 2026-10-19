"""Fallback Scout's economics observation remains private and fail-closed."""
from datetime import datetime, timezone
from unittest.mock import patch

from scripts.run_resilient_buyer_scout_20261019 import economics_only_summary

NOW = datetime(2026, 10, 19, 20, 0, tzinfo=timezone.utc)


def test_economic_summary_reuses_validated_board_only():
    fake_board = {
        "partner_pilots_reviewed": 4,
        "partner_pilots_without_verified_buybox": 4,
        "partner_pilots_without_verified_payable_terms": 4,
        "scout_domains_triaged": 3,
    }
    with patch(
        "scripts.run_resilient_buyer_scout_20261019.review_buyer_scout_awareness",
        return_value={"validated": True}
    ) as awareness:
        with patch(
            "scripts.run_resilient_buyer_scout_20261019.build_buyer_economic_gap_review",
            return_value=fake_board
        ) as economics:
            d = economics_only_summary({}, {}, {}, now=NOW)
    assert d["state"] == "READ_ONLY_ECONOMIC_GAP_BOARD"
    assert d["existing_partner_pilots_reviewed"] == 4
    assert d["partner_buyboxes_missing"] == 4
    assert d["partner_payment_terms_missing"] == 4
    assert d["verified_paying_buyer_capacity"] == 0
    assert d["outbound_authorized"] is False
    assert awareness.call_count == economics.call_count == 1


def test_corrupt_snapshots_do_not_break_scout_or_infer_buyers():
    d = economics_only_summary({}, {}, {}, now=NOW)
    assert d == {
        "state": "HOLD_ECONOMIC_REVIEW_SOURCE",
        "verified_paying_buyer_capacity": 0,
        "outbound_authorized": False,
    }


def test_invalid_economics_result_keeps_research_only():
    with patch(
        "scripts.run_resilient_buyer_scout_20261019.review_buyer_scout_awareness",
        return_value={}
    ):
        with patch(
            "scripts.run_resilient_buyer_scout_20261019.build_buyer_economic_gap_review",
            return_value={}
        ):
            d = economics_only_summary({}, {}, {}, now=NOW)
    assert d["state"] == "HOLD_ECONOMIC_REVIEW_SOURCE"
    assert d["verified_paying_buyer_capacity"] == 0
