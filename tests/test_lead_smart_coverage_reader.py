from datetime import datetime, timezone

import pytest

from empire_os.lead_smart_coverage_reader import (
    freshness,
    lookup_zip,
    payout_contract_drift,
    rank_observed_zips,
)


def snapshot():
    return {
        "schema_version":
            "empire.lead_smart.coverage_snapshot.v1",
        "mode": "OBSERVE",
        "observed_at":
            "2026-10-06T15:00:00+00:00",
        "source": {
            "table": "offer_bids",
            "semantics":
                "TARGETING_GUIDANCE_ONLY",
            "payout_guaranteed": False,
        },
        "coverage": {
            "source_newest_last_updated":
                "2026-10-06T14:00:00+00:00",
        },
        "rows": [
            {
                "zip": "00501",
                "city": "Holtsville",
                "state": "NY",
                "offer_key": "roofing",
                "offer_name": "Roofing",
                "duration_payout": 4.54,
                "cpl_payout": None,
                "top_payout": 4.54,
                "last_updated":
                    "2026-10-06T14:00:00+00:00",
            },
            {
                "zip": "01001",
                "city": "Agawam",
                "state": "MA",
                "offer_key": "roofing",
                "offer_name": "Roofing",
                "duration_payout": 170.10,
                "cpl_payout": None,
                "top_payout": 170.10,
                "last_updated":
                    "2026-10-06T14:00:00+00:00",
            },
        ],
        "authority": {
            "zip_coverage_observed": True,
            "zip_coverage_activation_verified":
                False,
            "tracking_verified": False,
            "routing_verified": False,
            "routing_enabled": False,
            "traffic_enabled": False,
            "execution_authority": "NONE",
        },
        "source_hash": "abc",
        "delta": {
            "baseline": True,
            "source_changed": None,
            "zip_added_count": None,
            "zip_removed_count": None,
            "top_payout_changed_zip_count":
                None,
        },
    }


def test_freshness_is_analysis_only():
    state = freshness(
        snapshot(),
        now=datetime(
            2026,
            10,
            6,
            16,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert (
        state[
            "fresh_for_targeting_analysis"
        ]
        is True
    )

    assert (
        state[
            "freshness_grants_execution_authority"
        ]
        is False
    )


def test_stale_source_fails_targeting_freshness():
    state = freshness(
        snapshot(),
        now=datetime(
            2026,
            10,
            8,
            0,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert (
        state[
            "fresh_for_targeting_analysis"
        ]
        is False
    )


def test_zip_lookup_preserves_leading_zero_and_blocks_live_route():
    result = lookup_zip(
        snapshot(),
        "00501",
        now=datetime(
            2026,
            10,
            6,
            16,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert result["zip"] == "00501"
    assert result["coverage_observed"] is True
    assert result["targeting_candidate"] is True
    assert result["live_route_eligible"] is False
    assert result["execution_authority"] == "NONE"


def test_invalid_zip_rejected():
    with pytest.raises(ValueError):
        lookup_zip(
            snapshot(),
            "501",
        )


def test_observed_contract_drift_does_not_rewrite_offer_terms():
    drift = payout_contract_drift(
        snapshot(),
        canonical_min=5,
        canonical_max=150,
    )

    assert drift["drift_observed"] is True
    assert drift["below_canonical_min_count"] == 1
    assert drift["above_canonical_max_count"] == 1
    assert (
        drift["canonical_contract_overwritten"]
        is False
    )


def test_rank_uses_observed_prior_only_when_fresh():
    ranked = rank_observed_zips(
        snapshot(),
        limit=2,
        now=datetime(
            2026,
            10,
            6,
            16,
            0,
            tzinfo=timezone.utc,
        ),
    )

    assert ranked[0]["zip"] == "01001"
    assert ranked[0]["observed_top_payout"] == 170.10
