from empire_os.lead_smart_launch_readiness import (
    build_launch_readiness,
)


def tracking():
    return {
        "state":
            "VERIFIED",

        "tracking_verified":
            True,
    }


def zip_gate():
    return {
        "zip_targeting_gate_verified":
            True,

        "zip_coverage_activation_verified":
            True,
    }


def routing(value=False):
    return {
        "routing_runtime_verified":
            value,
    }


def test_present_state_is_not_launch_ready():
    result = build_launch_readiness(
        tracking=tracking(),
        zip_gate=zip_gate(),
        routing=routing(False),
    )

    assert (
        result["gates"][
            "tracking_verified"
        ]
        is True
    )

    assert (
        result["gates"][
            "zip_targeting_verified"
        ]
        is True
    )

    assert (
        result["gates"][
            "routing_runtime_verified"
        ]
        is False
    )

    assert (
        result["launch_ready"]
        is False
    )

    assert (
        result["call_cta_enabled"]
        is False
    )

    assert (
        result[
            "organic_traffic_authorized"
        ]
        is False
    )

    assert (
        result[
            "execution_authority"
        ]
        == "NONE"
    )


def test_routing_alone_cannot_activate_campaign():
    result = build_launch_readiness(
        tracking=tracking(),
        zip_gate=zip_gate(),
        routing=routing(True),
        landing_publication_authorized=
            False,
        founder_live_traffic_authorized=
            False,
    )

    assert result["launch_ready"] is False

    assert (
        "landing_publication_authorized"
        in result["blockers"]
    )

    assert (
        "founder_live_traffic_authorized"
        in result["blockers"]
    )


def test_founder_authority_alone_cannot_bypass_routing():
    result = build_launch_readiness(
        tracking=tracking(),
        zip_gate=zip_gate(),
        routing=routing(False),
        landing_publication_authorized=
            True,
        founder_live_traffic_authorized=
            True,
    )

    assert result["launch_ready"] is False

    assert (
        "routing_runtime_verified"
        in result["blockers"]
    )


def test_all_independent_gates_required():
    result = build_launch_readiness(
        tracking=tracking(),
        zip_gate=zip_gate(),
        routing=routing(True),
        landing_publication_authorized=
            True,
        founder_live_traffic_authorized=
            True,
    )

    assert result["blockers"] == []
    assert result["launch_ready"] is True
    assert result["call_cta_enabled"] is True

    assert (
        result[
            "organic_traffic_authorized"
        ]
        is True
    )

    assert (
        result[
            "provider_route_mutation"
        ]
        is False
    )

    assert (
        result[
            "execution_authority"
        ]
        == "LIVE_TRAFFIC"
    )
