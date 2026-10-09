from copy import deepcopy
from datetime import datetime, timezone

from empire_os.lead_smart_effective_pilot_state import (
    build_effective_pilot_state,
)


def base():
    return {
        "source_ref":
            "gmail:test",

        "commercial_truth": {
            "tracking_number_assigned":
                True,

            "tracking_number":
                "+18883579305",

            "tracking_verified":
                False,

            "routing_verified":
                False,
        },

        "execution_authority":
            "none",
    }


def tracking():
    return {
        "schema_version":
            "empire.lead_smart."
            "tracking_verification.v1",

        "state":
            "VERIFIED",

        "tracking_number":
            "+18883579305",

        "tracking_verified":
            True,

        "verification_scope":
            "NUMBER_TO_CAMPAIGN_BINDING",

        "verification_path":
            "DIRECT_CAMPAIGN_OBJECT",

        "evidence_class":
            "AUTHENTICATED_PROVIDER_OBJECT",
    }


def routing():
    return {
        "schema_version":
            "empire.lead_smart."
            "ringba_routing_observation.v1",

        "mode":
            "OBSERVE",

        "routing_configuration_observed":
            True,

        "campaign_route_object_count":
            1,

        "campaign_enabled_route_candidate_count":
            1,

        "routing_runtime_verified":
            False,
    }


def coverage():
    return {
        "schema_version":
            "empire.lead_smart."
            "coverage_intelligence.v1",

        "mode":
            "OBSERVE",

        "coverage": {
            "row_count":
                28040,

            "unique_zip_count":
                28040,
        },

        "freshness": {
            "fresh_for_targeting_analysis":
                True,
        },
    }


def test_effective_state_overlays_tracking_without_mutating_base_policy():
    source = base()

    before = deepcopy(
        source
    )

    result = (
        build_effective_pilot_state(
            base_review=source,
            tracking_verification=
                tracking(),
            routing_observation=
                routing(),
            coverage_intelligence=
                coverage(),
            evidence_refs={
                "tracking":
                    "sha256:a",

                "routing":
                    "sha256:b",

                "coverage":
                    "sha256:c",
            },
        )
    )

    assert source == before

    assert (
        before[
            "commercial_truth"
        ][
            "tracking_verified"
        ]
        is False
    )

    assert (
        result[
            "effective_commercial_truth"
        ][
            "tracking_verified"
        ]
        is True
    )

    assert (
        result["tracking_bound"]
        is True
    )


def test_effective_state_keeps_independent_activation_gates_closed():
    result = (
        build_effective_pilot_state(
            base_review=base(),
            tracking_verification=
                tracking(),
            routing_observation=
                routing(),
            coverage_intelligence=
                coverage(),
            evidence_refs={
                "tracking":
                    "sha256:a",

                "routing":
                    "sha256:b",

                "coverage":
                    "sha256:c",
            },
        )
    )

    assert (
        result["routing"][
            "configuration_observed"
        ]
        is True
    )

    assert (
        result["routing"][
            "runtime_verified"
        ]
        is False
    )

    assert (
        result["coverage"][
            "observed"
        ]
        is True
    )

    assert (
        result["coverage"][
            "activation_verified"
        ]
        is False
    )

    assert (
        result["call_cta_enabled"]
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
            "commercial_activation_authorized"
        ]
        is False
    )

    assert (
        result[
            "execution_authority"
        ]
        == "NONE"
    )

def _zip_gate():
    return {
        "schema_version": "empire.lead_smart.zip_targeting_gate.v1",
        "mode": "PREACTIVATION",
        "zip_targeting_gate_verified": True,
        "zip_coverage_activation_verified": True,
        "source_fresh_for_targeting": True,
        "source_observed_at": "2026-10-09T16:02:40+00:00",
        "verified_freshness": {
            "source_newest_last_updated": "2026-10-09T14:00:42+00:00",
        },
        "zip_count": 28040,
        "evidence_refs": {"coverage_intelligence": "sha256:c"},
    }


def _effective_with_zip(zip_gate, *, now=None):
    return build_effective_pilot_state(
        base_review=base(),
        tracking_verification=tracking(),
        routing_observation=routing(),
        coverage_intelligence=coverage(),
        zip_activation=zip_gate,
        now=now or datetime(2026, 10, 9, 17, 45, tzinfo=timezone.utc),
        evidence_refs={
            "tracking": "sha256:a",
            "routing": "sha256:b",
            "coverage_intelligence": "sha256:c",
        },
    )


def test_independently_verified_zip_gate_promoted_without_traffic_authority():
    result = _effective_with_zip(_zip_gate())
    assert result["coverage"]["activation_verified"] is True
    assert result["effective_commercial_truth"]["zip_coverage_activation_verified"] is True
    assert "zip_coverage_activation_verification" not in result["remaining_activation_gates"]
    assert "routing_runtime_verification" in result["remaining_activation_gates"]
    assert result["call_cta_enabled"] is False
    assert result["traffic_enabled"] is False


def test_stale_or_wrong_evidence_does_not_promote_zip_coverage():
    for modification in (
        {"source_observed_at": "2026-10-08T16:02:40+00:00"},
        {"zip_count": 1},
        {"evidence_refs": {"coverage_intelligence": "sha256:wrong"}},
        {"evidence_refs": {}},
        {"zip_targeting_gate_verified": "true"},
    ):
        candidate = _zip_gate()
        candidate.update(modification)
        result = _effective_with_zip(candidate)
        assert result["coverage"]["activation_verified"] is False
        assert "zip_coverage_activation_verification" in result["remaining_activation_gates"]
        assert result["traffic_enabled"] is False
