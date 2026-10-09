from __future__ import annotations

from typing import Any, Mapping


SCHEMA_VERSION = (
    "empire.lead_smart."
    "launch_readiness.v1"
)


def build_launch_readiness(
    *,
    tracking: Mapping[str, Any],
    zip_gate: Mapping[str, Any],
    routing: Mapping[str, Any],
    landing_publication_authorized: bool = False,
    founder_live_traffic_authorized: bool = False,
) -> dict[str, Any]:

    tracking_verified = (
        tracking.get("state") == "VERIFIED"
        and tracking.get(
            "tracking_verified"
        )
        is True
    )

    zip_verified = (
        zip_gate.get(
            "zip_targeting_gate_verified"
        )
        is True
        and zip_gate.get(
            "zip_coverage_activation_verified"
        )
        is True
    )

    routing_verified = (
        routing.get(
            "routing_runtime_verified"
        )
        is True
    )

    gates = {
        "tracking_verified":
            tracking_verified,

        "zip_targeting_verified":
            zip_verified,

        "routing_runtime_verified":
            routing_verified,

        "landing_publication_authorized":
            bool(
                landing_publication_authorized
            ),

        "founder_live_traffic_authorized":
            bool(
                founder_live_traffic_authorized
            ),
    }

    blockers = [
        name
        for name, passed
        in gates.items()
        if passed is not True
    ]

    ready = not blockers

    return {
        "schema_version":
            SCHEMA_VERSION,

        "mode":
            (
                "READY"
                if ready
                else "PREACTIVATION"
            ),

        "buyer":
            "Lead Smart",

        "vertical":
            "Roofing",

        "gates":
            gates,

        "blockers":
            blockers,

        "launch_ready":
            ready,

        "call_cta_enabled":
            ready,

        "organic_traffic_authorized":
            ready,

        # No provider configuration mutation is
        # performed by this readiness object.
        "provider_route_mutation":
            False,

        "deployment_performed":
            False,

        "execution_authority":
            (
                "LIVE_TRAFFIC"
                if ready
                else "NONE"
            ),
    }
