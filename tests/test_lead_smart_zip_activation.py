from copy import deepcopy

import pytest

from empire_os.lead_smart_zip_activation import (
    build_zip_targeting_gate,
)


def snapshot():
    rows = []

    # Unit fixture keeps the production-count
    # invariant by constructing exactly 28,040
    # distinct five-digit ZIP-like values.
    #
    # These are TEST identifiers only.
    for value in range(
        10000,
        38040,
    ):
        rows.append({
            "zip":
                f"{value:05d}",

            "offer_key":
                "roofing",
        })

    return {
        "schema_version":
            "empire.lead_smart."
            "coverage_snapshot.v1",

        "mode":
            "OBSERVE",

        "observed_at":
            "2026-10-06T23:45:15+00:00",

        "source_hash":
            "a" * 64,

        "source": {
            "semantics":
                "TARGETING_GUIDANCE_ONLY",

            "payout_guaranteed":
                False,
        },

        "rows":
            rows,

        "authority": {
            "zip_coverage_observed":
                True,

            "execution_authority":
                "NONE",
        },
    }


def intelligence():
    return {
        "schema_version":
            "empire.lead_smart."
            "coverage_intelligence.v1",

        "mode":
            "OBSERVE",

        "freshness": {
            "fresh_for_targeting_analysis":
                True,
        },
    }


def test_current_targeting_gate_can_activate_without_claiming_payout():
    result = (
        build_zip_targeting_gate(
            snapshot=snapshot(),
            intelligence=
                intelligence(),
        )
    )

    assert result["zip_count"] == 28040

    assert (
        result[
            "zip_targeting_gate_verified"
        ]
        is True
    )

    assert (
        result[
            "zip_coverage_activation_verified"
        ]
        is True
    )

    assert (
        result[
            "activation_scope"
        ]
        == "EMPIRE_PRECALL_ZIP_GATE"
    )

    assert (
        result[
            "provider_payout_guaranteed"
        ]
        is False
    )

    assert (
        result[
            "provider_runtime_route_verified"
        ]
        is False
    )

    assert (
        result[
            "routing_enabled"
        ]
        is False
    )

    assert (
        result[
            "traffic_enabled"
        ]
        is False
    )


def test_stale_coverage_cannot_activate_zip_gate():
    intel = intelligence()

    intel["freshness"][
        "fresh_for_targeting_analysis"
    ] = False

    with pytest.raises(
        ValueError,
        match="stale",
    ):
        build_zip_targeting_gate(
            snapshot=snapshot(),
            intelligence=intel,
        )


def test_duplicate_zip_fails_closed():
    data = snapshot()

    data["rows"][-1]["zip"] = (
        data["rows"][0]["zip"]
    )

    with pytest.raises(
        ValueError,
        match="duplicate",
    ):
        build_zip_targeting_gate(
            snapshot=data,
            intelligence=
                intelligence(),
        )


def test_invalid_zip_fails_closed():
    data = snapshot()

    data["rows"][0]["zip"] = "1234"

    with pytest.raises(
        ValueError,
        match="invalid ZIP",
    ):
        build_zip_targeting_gate(
            snapshot=data,
            intelligence=
                intelligence(),
        )


def test_source_policy_is_not_mutated():
    data = snapshot()
    before = deepcopy(data)

    build_zip_targeting_gate(
        snapshot=data,
        intelligence=
            intelligence(),
    )

    assert data == before
