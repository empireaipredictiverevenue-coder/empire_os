from datetime import datetime, timezone

import pytest

from empire_os.lead_smart_ringba_evidence import (
    EXPECTED_CAMPAIGN_ID,
    EXPECTED_TRACKING_NUMBER,
    build_payable_calibration_candidate,
    evidence_contract,
    normalize_verified_ringba_event,
)


def event(**overrides):
    raw = {
        "tenant_id":
            "tenant-test",

        "ringba_call_id":
            "ringba-call-001",

        "campaign_id":
            EXPECTED_CAMPAIGN_ID,

        "tracking_number":
            EXPECTED_TRACKING_NUMBER,

        "zip":
            "07006",

        "intent_class":
            "roofing",

        "route_class":
            "DURATION",

        "started_at":
            "2026-10-06T15:00:00+00:00",

        "connected_seconds":
            127,

        "appointment_event":
            False,

        "duplicate_within_30d":
            False,

        "provider_event_finalized":
            True,

        "payout_amount":
            42.63,

        "payout_currency":
            "USD",

        "payout_observed_at":
            "2026-10-06T15:05:00+00:00",

        "verification": {
            "verified": True,
            "method":
                "ringba_authenticated_api",
            "evidence_ref":
                "ringba:call:001:details",
        },
    }

    raw.update(overrides)

    return raw


def prediction(**overrides):
    row = {
        "tenant_id":
            "tenant-test",

        "opportunity_key":
            "lead-smart:roofing:07006",

        "prediction_ref":
            "prediction:ringba:001",

        "prediction_type":
            "ringba_payable_probability",

        "predicted_probability":
            0.7,

        "predicted_at":
            "2026-10-06T14:55:00+00:00",

        "horizon_until":
            "2026-10-06T16:00:00+00:00",

        "zip":
            "07006",

        "campaign_id":
            EXPECTED_CAMPAIGN_ID,

        "evidence_refs": [
            "coverage:"
            "9b06f6af6be2",
        ],
    }

    row.update(overrides)

    return row


def test_contract_separates_provider_payout_from_revenue():
    contract = evidence_contract()

    assert (
        contract[
            "payout_value_authority"
        ]
        == "RINGBA_REALISED_EVENT"
    )

    assert (
        contract[
            "provider_payout_is_"
            "recognized_revenue"
        ]
        is False
    )

    assert (
        contract[
            "provider_payout_is_"
            "cash_settlement"
        ]
        is False
    )

    assert (
        contract[
            "prediction_promotion_allowed"
        ]
        is False
    )


def test_positive_final_provider_payout_creates_payable_label_only():
    result = (
        normalize_verified_ringba_event(
            event()
        )
    )

    assert (
        result["payout"][
            "final_payable_label"
        ]
        == 1
    )

    assert (
        result[
            "provider_credit_observed"
        ]
        is True
    )

    assert result["calibration_ready"] is True

    assert (
        result[
            "duration_threshold_inferred"
        ]
        is False
    )

    assert (
        result["revenue_recognized"]
        is False
    )

    assert (
        result["actual_revenue"]
        is False
    )

    assert (
        result[
            "economic_memory_eligible"
        ]
        is False
    )


def test_final_zero_payout_can_be_negative_payability_label():
    result = (
        normalize_verified_ringba_event(
            event(
                payout_amount=0.0
            )
        )
    )

    assert (
        result["payout"][
            "final_payable_label"
        ]
        == 0
    )

    assert (
        result[
            "provider_nonpayable_observed"
        ]
        is True
    )

    assert result["calibration_ready"] is True
    assert result["actual_revenue"] is False


def test_nonfinal_event_never_becomes_negative_training_label():
    result = (
        normalize_verified_ringba_event(
            event(
                provider_event_finalized=False,
                payout_amount=0.0,
            )
        )
    )

    assert (
        result["payout"][
            "final_payable_label"
        ]
        is None
    )

    assert result["calibration_ready"] is False

    assert (
        "final_payable_label_unavailable"
        in result["calibration_blockers"]
    )


def test_missing_route_does_not_get_inferred_from_duration():
    result = (
        normalize_verified_ringba_event(
            event(
                route_class=None,
                connected_seconds=400,
            )
        )
    )

    assert result["route_class"] is None

    assert (
        result[
            "route_inferred_from_duration"
        ]
        is False
    )

    assert result["calibration_ready"] is False

    assert (
        "route_class_unknown"
        in result["calibration_blockers"]
    )


def test_unverified_provider_claim_is_rejected():
    raw = event()

    raw["verification"] = {
        "verified": False,
        "method":
            "ringba_authenticated_api",
        "evidence_ref":
            "ringba:call:001",
    }

    with pytest.raises(
        ValueError,
        match="independently verified",
    ):
        normalize_verified_ringba_event(
            raw
        )


def test_wrong_campaign_or_tracking_number_is_rejected():
    with pytest.raises(
        ValueError,
        match="campaign mismatch",
    ):
        normalize_verified_ringba_event(
            event(
                campaign_id="wrong"
            )
        )

    with pytest.raises(
        ValueError,
        match="tracking number mismatch",
    ):
        normalize_verified_ringba_event(
            event(
                tracking_number="+10000000000"
            )
        )


def test_shadow_calibration_reuses_quant_brier_without_promoting_learning():
    evidence = (
        normalize_verified_ringba_event(
            event()
        )
    )

    result = (
        build_payable_calibration_candidate(
            prediction=prediction(),
            evidence=evidence,
            as_of=datetime(
                2026,
                10,
                6,
                15,
                10,
                tzinfo=timezone.utc,
            ),
        )
    )

    assert result["actual_value"] == 1
    assert result["predicted_value"] == 0.7

    # (1 - 0.7)^2 = 0.09
    assert result["brier_score"] == pytest.approx(
        0.09
    )

    assert result["shadow_only"] is True

    assert (
        result[
            "model_weight_mutation"
        ]
        is False
    )

    assert (
        result[
            "promoted_learning"
        ]
        is False
    )

    assert (
        result[
            "economic_memory_eligible"
        ]
        is False
    )

    assert (
        result[
            "recognized_revenue"
        ]
        is False
    )

    assert (
        result[
            "execution_authority"
        ]
        == "NONE"
    )


def test_prediction_must_precede_call_and_match_zip():
    evidence = (
        normalize_verified_ringba_event(
            event()
        )
    )

    with pytest.raises(
        ValueError,
        match="prediction window",
    ):
        build_payable_calibration_candidate(
            prediction=prediction(
                predicted_at=
                    "2026-10-06T15:01:00+00:00"
            ),
            evidence=evidence,
            as_of=
                "2026-10-06T15:10:00+00:00",
        )

    with pytest.raises(
        ValueError,
        match="ZIP mismatch",
    ):
        build_payable_calibration_candidate(
            prediction=prediction(
                zip="10001"
            ),
            evidence=evidence,
            as_of=
                "2026-10-06T15:10:00+00:00",
        )
