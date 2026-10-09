# EMPIRE_WAVE_089
from empire_os.detection_fabric import (
    CONTROL_NAMES,
    LANES,
    DetectionEnvelope,
    coverage_status,
    lane_risk,
    stable_id,
)


def test_shared_control_contract_is_complete():

    required = {
        "entity_classification",
        "canonical_identity",
        "duplicate_detection",
        "input_quality",
        "output_quality",
        "evidence_lineage",
        "conflict_detection",
        "freshness",
        "quarantine",
        "action_authority",
        "outcome_linkage",
    }

    assert set(
        CONTROL_NAMES
    ) == required


def test_expected_business_lanes_present():

    names = {
        lane.lane
        for lane in LANES
    }

    expected = {
        "buyer_network",
        "leads",
        "people_contacts",
        "opportunities",
        "conversations_replies",
        "campaigns",
        "agent_tasks",
        "products_offers",
        "consent_suppression",
        "orders_payments_revenue",
        "economic_memory",
        "predictive_revenue",
    }

    assert expected <= names


def test_source_presence_is_not_runtime_truth():

    assert coverage_status(
        runtime_verified=False,
        source_evidence=True,
    ) == "SOURCE_EVIDENCE_ONLY"


def test_runtime_truth_wins():

    assert coverage_status(
        runtime_verified=True,
        source_evidence=True,
    ) == "VERIFIED_RUNTIME"


def test_missing_controls_raise_lane_risk():

    assert lane_risk(
        "ACTIVE_RUNTIME",
        (
            "MISSING_OR_UNVERIFIED",
        )
        * 8,
    ) == "HIGH"


def test_detection_envelope_fails_closed():

    event = DetectionEnvelope(
        lane=
            "payments",

        entity_type=
            "economic_event",

        canonical_id=
            "evt-1",

        generation_id=
            "gen-1",

        source_id=
            "source-1",

        detector=
            "test",

        code=
            "UNSUPPORTED_EVENT",

        severity=
            "HIGH",

        confidence=
            0.99,

        reason=
            "test",

        action_allowed=
            False,
    )

    assert not event.action_allowed


def test_stable_id_is_deterministic():

    assert stable_id(
        "lead",
        "abc"
    ) == stable_id(
        "lead",
        "abc"
    )
