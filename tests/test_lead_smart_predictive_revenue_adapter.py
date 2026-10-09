from datetime import datetime, timezone

from empire_os.lead_smart_predictive_revenue_adapter import (
    predictive_revenue_signal,
    realised_outcome_feature_contract,
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
        "rows": [{
            "zip": "00501",
            "city": "Holtsville",
            "state": "NY",
            "offer_key": "roofing",
            "offer_name": "Roofing",
            "duration_payout": 42.63,
            "cpl_payout": None,
            "top_payout": 42.63,
            "last_updated":
                "2026-10-06T14:00:00+00:00",
        }],
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
    }


def test_predictive_signal_never_invents_expected_revenue():
    result = predictive_revenue_signal(
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

    assert (
        result[
            "observed_top_payout_prior"
        ]
        == 42.63
    )

    assert (
        result[
            "predicted_payable_probability"
        ]
        is None
    )

    assert result["expected_revenue"] is None
    assert result["expected_margin"] is None

    assert (
        result[
            "can_claim_expected_revenue"
        ]
        is False
    )

    assert result["live_route_eligible"] is False
    assert result["execution_authority"] == "NONE"


def test_calibration_contract_requires_realised_ringba_evidence():
    contract = realised_outcome_feature_contract()

    required = set(
        contract["required_realised_features"]
    )

    assert "ringba_call_id" in required
    assert "connected_seconds" in required
    assert "appointment_event" in required
    assert "duplicate_within_30d" in required
    assert "realised_payout" in required

    assert (
        contract[
            "prediction_allowed_before_calibration"
        ]
        is False
    )
