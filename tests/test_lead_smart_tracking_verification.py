from datetime import datetime, timezone

import pytest

from empire_os.lead_smart_tracking_verification import (
    EXPECTED_CAMPAIGN_ID,
    EXPECTED_TRACKING_NUMBER,
    build_tracking_verification,
)


SOURCE_HASH = "a" * 64


def observation(
    **overrides,
):
    row = {
        "schema_version":
            "empire.lead_smart."
            "ringba_tracking_object_observation.v1",

        "mode":
            "OBSERVE",

        "observed_at":
            "2026-10-06T22:50:00+00:00",

        "provider":
            "Ringba",

        "buyer":
            "Lead Smart",

        "vertical":
            "Roofing",

        "campaign_id":
            EXPECTED_CAMPAIGN_ID,

        "tracking_number":
            EXPECTED_TRACKING_NUMBER,

        "direct_campaign_binding":
            True,

        "inbound_reference_binding":
            False,

        "provider_binding_verified":
            True,

        "tracking_verification_candidate":
            True,

        "tracking_verified_change":
            False,

        "routing_verified_change":
            False,

        "routing_enabled":
            False,

        "traffic_enabled":
            False,

        "execution_authority":
            "NONE",
    }

    row.update(
        overrides
    )

    return row


def now():
    return datetime(
        2026,
        10,
        6,
        23,
        0,
        tzinfo=timezone.utc,
    )


def test_direct_provider_binding_promotes_tracking_only():
    result = (
        build_tracking_verification(
            observation(),
            source_sha256=
                SOURCE_HASH,
            now=now(),
        )
    )

    assert (
        result["state"]
        == "VERIFIED"
    )

    assert (
        result[
            "tracking_number_assigned"
        ]
        is True
    )

    assert (
        result[
            "tracking_verified"
        ]
        is True
    )

    assert (
        result[
            "verification_path"
        ]
        == "DIRECT_CAMPAIGN_OBJECT"
    )

    assert (
        result["routing_verified"]
        is False
    )

    assert (
        result["routing_enabled"]
        is False
    )

    assert (
        result["traffic_enabled"]
        is False
    )

    assert (
        result[
            "execution_authority"
        ]
        == "NONE"
    )


def test_inbound_reference_binding_is_also_valid_provider_proof():
    result = (
        build_tracking_verification(
            observation(
                direct_campaign_binding=
                    False,

                inbound_reference_binding=
                    True,
            ),
            source_sha256=
                SOURCE_HASH,
            now=now(),
        )
    )

    assert (
        result[
            "verification_path"
        ]
        == "NUMBER_INBOUND_REFERENCE"
    )

    assert (
        result["tracking_verified"]
        is True
    )


def test_stale_provider_evidence_is_rejected():
    with pytest.raises(
        ValueError,
        match="stale",
    ):
        build_tracking_verification(
            observation(
                observed_at=
                    "2026-10-06T20:00:00+00:00"
            ),
            source_sha256=
                SOURCE_HASH,
            now=now(),
        )


def test_campaign_or_number_mismatch_is_rejected():
    with pytest.raises(
        ValueError,
        match="campaign mismatch",
    ):
        build_tracking_verification(
            observation(
                campaign_id="wrong"
            ),
            source_sha256=
                SOURCE_HASH,
            now=now(),
        )

    with pytest.raises(
        ValueError,
        match="tracking number mismatch",
    ):
        build_tracking_verification(
            observation(
                tracking_number=
                    "+10000000000"
            ),
            source_sha256=
                SOURCE_HASH,
            now=now(),
        )


def test_candidate_without_provider_binding_is_rejected():
    with pytest.raises(
        ValueError,
        match="no provider binding path",
    ):
        build_tracking_verification(
            observation(
                direct_campaign_binding=
                    False,

                inbound_reference_binding=
                    False,
            ),
            source_sha256=
                SOURCE_HASH,
            now=now(),
        )


def test_source_must_have_zero_execution_authority():
    with pytest.raises(
        ValueError,
        match="execution authority",
    ):
        build_tracking_verification(
            observation(
                execution_authority=
                    "EXECUTE"
            ),
            source_sha256=
                SOURCE_HASH,
            now=now(),
        )
