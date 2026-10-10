from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Mapping


SCHEMA_VERSION = (
    "empire.lead_smart."
    "effective_pilot_state.v1"
)


def _fresh(when: Any, *, now: datetime, max_age_seconds: int) -> bool:
    if not isinstance(when, str):
        return False
    try:
        value = datetime.fromisoformat(when.replace("Z", "+00:00"))
    except ValueError:
        return False
    if value.tzinfo is None:
        return False
    age = (now - value.astimezone(timezone.utc)).total_seconds()
    return 0 <= age <= max_age_seconds


def build_effective_pilot_state(
    *,
    base_review: Mapping[str, Any],
    tracking_verification: Mapping[str, Any],
    routing_observation: Mapping[str, Any],
    coverage_intelligence: Mapping[str, Any],
    evidence_refs: Mapping[str, str],
    zip_activation: Mapping[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """
    Compose static commercial policy with independently
    observed provider/runtime truth.

    The static buyer policy is not rewritten.

    Provider evidence may promote tracking truth. The separately
    verified, fresh ZIP-activation artifact may promote ZIP coverage
    truth, but neither independently permits routing or traffic.
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

    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        raise ValueError('timezone-aware verification time required')
    current_time = current_time.astimezone(timezone.utc)
    zip_gate = dict(zip_activation or {})

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

    # Buyer route attestation is not independent runtime proof.
    commercial_truth[
        "routing_verified"
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

    zip_verified = (
        zip_gate.get("schema_version")
        == "empire.lead_smart.zip_targeting_gate.v1"
        and zip_gate.get("mode") == "PREACTIVATION"
        and zip_gate.get("zip_targeting_gate_verified") is True
        and zip_gate.get("zip_coverage_activation_verified") is True
        and zip_gate.get("source_fresh_for_targeting") is True
        and zip_gate.get("zip_count") == unique_zips
        and unique_zips > 0
        and isinstance(evidence_refs.get("coverage_intelligence"), str)
        and evidence_refs["coverage_intelligence"].startswith("sha256:")
        and (zip_gate.get("evidence_refs") or {}).get("coverage_intelligence")
        == evidence_refs["coverage_intelligence"]
        and _fresh(
            zip_gate.get("source_observed_at"),
            now=current_time, max_age_seconds=21600,
        )
        and _fresh(
            (zip_gate.get("verified_freshness") or {}).get(
                "source_newest_last_updated"
            ),
            now=current_time, max_age_seconds=108000,
        )
    )

    commercial_truth["zip_coverage_activation_verified"] = zip_verified

    # These are independently outstanding activation gates, even if Ringba
    # binds a valid number to the approved campaign. The static buyer offer
    # and tracking proof must never hide the landing or caller-ID holds.
    landing_review = commercial_truth.get("landing_review_report") or {}
    direct_route = commercial_truth.get("direct_route_requirements") or {}
    landing_approved = (
        isinstance(landing_review, Mapping)
        and landing_review.get("approved") is True
        and str(landing_review.get("source_ref") or "").startswith("gmail:")
    )
    caller_id_verified = (
        isinstance(direct_route, Mapping)
        and direct_route.get("caller_id_pass_through_verified") is True
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
                zip_verified,
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
            *([] if zip_verified else ["zip_coverage_activation_verification"]),
            *([] if landing_approved else ["buyer_landing_page_approval"]),
            *([] if caller_id_verified else ["caller_id_pass_through_verification"]),
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
