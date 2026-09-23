import pytest

from empire_os.control_fabric import default_registry, route_event
from empire_os.departments import default_departments
from empire_os.media_os_foundation import (
    CanonicalContentObject,
    MediaClaim,
    build_media_opportunity_feature_packet,
    evaluate_channel_launch_candidate,
    media_os_architecture_contract,
)


def test_media_os_reuses_canonical_empire_systems_and_has_no_publish_authority():
    contract = media_os_architecture_contract()

    assert contract["phase"] == "A"
    assert contract["mode"] == "OBSERVE"
    assert contract["department"] == "marketing_growth"
    assert contract["shared_system_rules"]["evidence_store"] == (
        "intelligence_fabric"
    )
    assert contract["shared_system_rules"]["ranking_and_economics"] == (
        "quant_brain"
    )
    assert contract["shared_system_rules"]["revenue_truth"] == "revenue_pulse"
    assert contract["authority"]["public_publish_authorized"] is False
    assert contract["authority"]["new_channel_launch_authorized"] is False
    assert (
        contract["authority"]["material_gpu_cloud_commitment_authorized"]
        is False
    )
    assert contract["actual_revenue"] is False
    assert contract["execution_authority"] == "none"


def test_subscriber_objectives_are_targets_not_guarantees():
    strategy = media_os_architecture_contract()["subscriber_strategy"]

    assert strategy["first_major_scale_milestone"] == 100_000
    assert strategy["long_term_network_objective"] == 1_000_000
    assert strategy["guaranteed"] is False
    assert strategy["fixed_date_forecast"] is False


def test_factual_media_claim_requires_evidence():
    with pytest.raises(ValueError, match="evidence_refs"):
        MediaClaim(
            claim="Empire increased revenue by 40 percent",
            claim_type="factual",
        ).as_dict()

    row = MediaClaim(
        claim="The live build passed its verification suite",
        claim_type="factual",
        evidence_refs=("build:verification:123",),
    ).as_dict()

    assert row["evidence_refs"] == ("build:verification:123",)


def test_canonical_content_object_preserves_claim_lineage():
    content = CanonicalContentObject(
        content_id="media:empire-ai:001",
        topic="Building governed AI systems",
        thesis="Governance can coexist with fast internal automation.",
        audience="founders",
        evidence_refs=("blueprint:v6",),
        claims=(
            MediaClaim(
                claim="EmpireOS keeps external authority governed.",
                claim_type="factual",
                evidence_refs=("blueprint:v6:authority",),
            ),
        ),
        uncertainty=("Audience response is not yet observed.",),
    ).as_dict()

    assert content["schema_version"] == "empire.media.canonical_content.v1"
    assert content["public_publish_authorized"] is False
    assert content["actual_revenue"] is False
    assert content["execution_authority"] == "none"


def test_media_opportunity_packet_does_not_invent_score_intent_or_revenue():
    packet = build_media_opportunity_feature_packet(
        topic="AI lead generation",
        evidence_refs=("search:123", "community:456"),
        source_systems=("search_intelligence", "community_intent"),
        features={
            "audience_demand": 0.8,
            "trend_velocity": 0.7,
            "product_alignment": 1.0,
        },
    )

    assert packet["known_feature_count"] == 3
    assert packet["ranking_owner"] == "quant_brain_and_opportunity_factory"
    assert packet["media_opportunity_score"] is None
    assert packet["score_created"] is False
    assert packet["buyer_intent_inferred"] is False
    assert packet["revenue_inferred"] is False
    assert packet["subscriber_forecast_created"] is False


def test_channel_launch_requires_depth_evidence_ideas_and_founder_gate():
    hold = evaluate_channel_launch_candidate(
        channel_concept="AI for Roofing",
        credible_idea_count=12,
        evidence_refs=("search:roofing",),
        content_depth_confirmed=True,
        market_evidence_confirmed=True,
    )
    assert hold["decision"] == "HOLD"
    assert hold["channel_launch_authorized"] is False
    assert hold["founder_gate_required"] is False

    candidate = evaluate_channel_launch_candidate(
        channel_concept="AI for Roofing",
        credible_idea_count=35,
        evidence_refs=("search:roofing", "youtube:roofing"),
        content_depth_confirmed=True,
        market_evidence_confirmed=True,
    )
    assert candidate["decision"] == "FOUNDER_REVIEW_CANDIDATE"
    assert candidate["channel_created"] is False
    assert candidate["channel_launch_authorized"] is False
    assert candidate["founder_gate_required"] is True
    assert candidate["execution_authority"] == "founder_gate"


def test_media_os_is_control_fabric_component_owned_by_marketing_growth():
    by_name = {row.name: row for row in default_registry()}
    assert "media_os" in by_name
    media = by_name["media_os"]
    assert media.authority == "internal_write"
    assert "intelligence_fabric" in media.dependencies
    assert "quant_brain" in media.dependencies
    assert "revenue_pulse" in media.dependencies
    assert "conversion_intelligence" in media.dependencies
    assert "revenue_crm" in media.dependencies
    assert all("publish" not in event for event in media.outputs)
    assert "quant_review_requested" in media.outputs
    assert "experiment_review_requested" in media.outputs

    routes = route_event({
        "event_type": "media_opportunity_scan_requested",
        "commercial_priority": 82,
    })
    assert routes
    assert routes[0]["component"] == "media_os"
    assert routes[0]["authority"] == "internal_write"

    departments = {row.key: row for row in default_departments()}
    assert "media_os" in departments["marketing_growth"].components
    assert "media_os" not in departments


def test_media_review_events_route_to_existing_quant_and_experiment_systems():
    quant = route_event({
        "event_type": "quant_review_requested",
        "commercial_priority": 80,
    })
    assert quant
    assert quant[0]["component"] == "quant_brain"
    assert quant[0]["authority"] == "observe"

    experiment = route_event({
        "event_type": "experiment_review_requested",
        "commercial_priority": 80,
    })
    assert experiment
    assert experiment[0]["component"] == "experiment_intelligence"
    assert experiment[0]["authority"] == "observe"
