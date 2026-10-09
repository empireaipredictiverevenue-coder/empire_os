from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


SCHEMA_VERSION = (
    "empire.lead_smart."
    "effective_pilot_state.v1"
)


def build_effective_pilot_state(
    *,
    base_review: Mapping[str, Any],
    tracking_verification: Mapping[str, Any],
    routing_observation: Mapping[str, Any],
    coverage_intelligence: Mapping[str, Any],
    evidence_refs: Mapping[str, str],
) -> dict[str, Any]:
    """
    Compose static commercial policy with independently
    observed provider/runtime truth.

    The static buyer policy is not rewritten.

    Provider verification may promote tracking truth only.
    Routing, ZIP activation and traffic remain independent
    gates.
    """

    base = deepcopy(
        dict(base_review)
    )

    tracking = dict(
        tracking_verification
    )

    routing = dict(
        routing_observation
    )

    coverage = dict(
        coverage_intelligence
    )

    if (
        tracking.get(
            "schema_version"
        )
        !=
        "empire.lead_smart."
        "tracking_verification.v1"
    ):
        raise ValueError(
            "unexpected tracking "
            "verification schema"
        )

    if (
        tracking.get("state")
        != "VERIFIED"
        or tracking.get(
            "tracking_verified"
        )
        is not True
    ):
        raise ValueError(
            "verified tracking "
            "evidence required"
        )

    if (
        routing.get(
            "schema_version"
        )
        !=
        "empire.lead_smart."
        "ringba_routing_observation.v1"
    ):
        raise ValueError(
            "unexpected routing "
            "observation schema"
        )

    if (
        routing.get("mode")
        != "OBSERVE"
    ):
        raise ValueError(
            "routing must remain "
            "OBSERVE"
        )

    if (
        routing.get(
            "routing_runtime_verified"
        )
        is not False
    ):
        raise ValueError(
            "018 may not promote "
            "runtime routing"
        )

    if (
        coverage.get(
            "schema_version"
        )
        !=
        "empire.lead_smart."
        "coverage_intelligence.v1"
    ):
        raise ValueError(
            "unexpected coverage "
            "intelligence schema"
        )

    if (
        coverage.get("mode")
        != "OBSERVE"
    ):
        raise ValueError(
            "coverage must remain "
            "OBSERVE"
        )

    commercial_truth = deepcopy(
        dict(
            base.get(
                "commercial_truth"
            )
            or {}
        )
    )

    # Runtime provider evidence supersedes the
    # older policy's tracking verification field.
    commercial_truth[
        "tracking_number_assigned"
    ] = True

    commercial_truth[
        "tracking_number"
    ] = tracking[
        "tracking_number"
    ]

    commercial_truth[
        "tracking_verified"
    ] = True

    # Independent gates remain false.
    commercial_truth[
        "routing_verified"
    ] = False

    commercial_truth[
        "zip_coverage_activation_verified"
    ] = False

    coverage_rows = int(
        (
            coverage.get(
                "coverage"
            )
            or {}
        ).get(
            "row_count"
        )
        or 0
    )

    unique_zips = int(
        (
            coverage.get(
                "coverage"
            )
            or {}
        ).get(
            "unique_zip_count"
        )
        or 0
    )

    fresh_for_targeting = (
        (
            coverage.get(
                "freshness"
            )
            or {}
        ).get(
            "fresh_for_targeting_analysis"
        )
        is True
    )

    route_configuration_observed = (
        routing.get(
            "routing_configuration_observed"
        )
        is True
    )

    return {
        "schema_version":
            SCHEMA_VERSION,

        "mode":
            "PREACTIVATION",

        "buyer":
            "Lead Smart",

        "vertical":
            "Roofing",

        "pilot":
            "roofing_pay_per_call",

        "base_policy_source_ref":
            base.get(
                "source_ref"
            ),

        "effective_commercial_truth":
            commercial_truth,

        "evidence_refs":
            dict(
                evidence_refs
            ),

        "tracking": {
            "number_assigned":
                True,

            "verified":
                True,

            "verification_scope":
                tracking[
                    "verification_scope"
                ],

            "verification_path":
                tracking[
                    "verification_path"
                ],

            "evidence_class":
                tracking[
                    "evidence_class"
                ],
        },

        "coverage": {
            "observed":
                coverage_rows > 0,

            "row_count":
                coverage_rows,

            "unique_zip_count":
                unique_zips,

            "fresh_for_targeting_analysis":
                fresh_for_targeting,

            "activation_verified":
                False,
        },

        "routing": {
            "configuration_observed":
                route_configuration_observed,

            "campaign_route_object_count":
                routing.get(
                    "campaign_route_object_count"
                ),

            "enabled_route_candidate_count":
                routing.get(
                    "campaign_enabled_route_candidate_count"
                ),

            "runtime_verified":
                False,

            "enabled":
                False,
        },

        "remaining_activation_gates": [
            "routing_runtime_verification",
            "zip_coverage_activation_verification",
            "landing_publication_authority",
            "founder_live_traffic_authority",
        ],

        "tracking_bound":
            True,

        "call_cta_enabled":
            False,

        "routing_enabled":
            False,

        "traffic_enabled":
            False,

        "commercial_activation_authorized":
            False,

        "revenue_recognized":
            False,

        "execution_authority":
            "NONE",
    }
