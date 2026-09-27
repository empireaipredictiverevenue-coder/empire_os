from datetime import datetime, timezone

import pytest

from empire_os.media_idea_factory import (
    MediaIdeaCandidate,
    apply_quant_review,
)
from empire_os.media_os_foundation import (
    CanonicalContentObject,
    MediaClaim,
)
from empire_os.media_research_pack import (
    MediaResearchClaim,
    MediaResearchPack,
    MediaResearchSource,
    fact_refresh_actions,
)
from empire_os.media_script_engine import (
    build_script_brief,
    validate_script_draft,
)


def research_pack():
    return MediaResearchPack(
        research_id="research:001",
        topic="AI automation",
        thesis="Evidence-backed automation can reduce repeated manual work.",
        audience="founders",
        sources=(
            MediaResearchSource(
                source_ref="source:build",
                source_type="empire_build_evidence",
                observed_at="2026-09-20T10:00:00+00:00",
                rights_state="OWNED",
            ),
        ),
        claims=(
            MediaResearchClaim(
                claim_id="claim:1",
                text="The build completed its internal verification.",
                evidence_refs=("source:build",),
                freshness_class="CURRENT",
                source_timestamp="2026-09-20T10:00:00+00:00",
            ),
        ),
        uncertainty=("Audience response is not yet observed.",),
    )


def canonical_content():
    return CanonicalContentObject(
        content_id="content:001",
        topic="Building governed AI automation",
        thesis="Move fast internally while keeping external action governed.",
        audience="founders",
        evidence_refs=("source:build",),
        claims=(
            MediaClaim(
                claim="The build completed internal verification.",
                claim_type="factual",
                evidence_refs=("source:build",),
                freshness_class="CURRENT",
            ),
        ),
        stories=("What failed before the final verification",),
        examples=("Buyer Scout permission regression fix",),
        visual_ideas=("Show the real Founder Console read-only status",),
        cta="Follow the Empire AI build series.",
        uncertainty=("Subscriber response is unknown.",),
    )


def test_research_pack_preserves_sources_and_freshness():
    row = research_pack().as_dict(
        now=datetime(2026, 9, 23, tzinfo=timezone.utc)
    )

    assert row["sources"][0]["rights_state"] == "OWNED"
    assert row["claims"][0]["stale"] is False
    assert row["refresh_required"] is False
    assert row["unknown_is_unknown"] is True
    assert row["public_publish_authorized"] is False
    assert row["execution_authority"] == "none"


def test_stale_fast_moving_claim_creates_refresh_candidates_not_mutation():
    pack = MediaResearchPack(
        research_id="research:stale",
        topic="Model pricing",
        thesis="Model economics change quickly.",
        audience="AI builders",
        sources=(
            MediaResearchSource(
                source_ref="source:pricing",
                source_type="provider_pricing",
                observed_at="2026-08-01T00:00:00+00:00",
            ),
        ),
        claims=(
            MediaResearchClaim(
                claim_id="claim:pricing",
                text="Provider pricing is X.",
                evidence_refs=("source:pricing",),
                freshness_class="FAST_MOVING",
                source_timestamp="2026-08-01T00:00:00+00:00",
            ),
        ),
    )

    actions = fact_refresh_actions(
        pack,
        now=datetime(2026, 9, 23, tzinfo=timezone.utc),
    )

    assert actions["stale_claim_ids"] == ["claim:pricing"]
    assert "new_edition_candidate" in actions["candidate_actions"]
    assert actions["automatic_public_mutation"] is False


def test_research_pack_rejects_dangling_evidence_refs():
    pack = MediaResearchPack(
        research_id="research:bad",
        topic="Bad lineage",
        thesis="This should fail.",
        audience="founders",
        sources=(
            MediaResearchSource(
                source_ref="source:known",
                source_type="web",
                observed_at=None,
            ),
        ),
        claims=(
            MediaResearchClaim(
                claim_id="claim:bad",
                text="Unsupported reference.",
                evidence_refs=("source:missing",),
            ),
        ),
    )

    with pytest.raises(ValueError, match="missing from research sources"):
        pack.as_dict()


def test_idea_factory_delegates_decision_to_quant():
    idea = MediaIdeaCandidate(
        idea_id="idea:001",
        topic="AI lead generation",
        angle="What actually survives production evidence gates",
        audience="founders",
        evidence_refs=("search:1", "build:1"),
        source_systems=("search_intelligence", "empire_coder"),
        format_candidates=("build_in_public", "tutorial"),
        product_refs=("product:search-growth",),
    ).as_dict(
        opportunity_features={
            "audience_demand": 0.8,
            "empire_expertise": 1.0,
            "product_alignment": 0.9,
        }
    )

    assert idea["decision"] == "PENDING_QUANT_REVIEW"
    assert idea["opportunity_features"]["score_created"] is False
    assert idea["public_publish_authorized"] is False

    reviewed = apply_quant_review(
        idea,
        {
            "decision_id": "quant:001",
            "recommendation": "BUILD",
        },
    )
    assert reviewed["decision"] == "BUILD_CANDIDATE"
    assert reviewed["automatic_build_authorized"] is False
    assert reviewed["public_publish_authorized"] is False


def test_script_brief_uses_existing_model_router_and_claim_catalog():
    brief = build_script_brief(
        canonical_content(),
        script_format="build_in_public",
        target_duration_seconds=600,
    )

    assert brief["provider_owner"] == (
        "model_registry_and_intelligence_router"
    )
    assert brief["claim_catalog"]["claim-1"]["evidence_refs"] == [
        "source:build"
    ]
    assert brief["instructions"]["invented_statistics_allowed"] is False
    assert brief["instructions"]["unknown_remains_unknown"] is True
    assert brief["public_publish_authorized"] is False


def test_script_validation_blocks_unknown_or_unsupported_claims():
    brief = build_script_brief(
        canonical_content(),
        script_format="rapid_intelligence",
    )
    sections = {
        section: f"Draft for {section}"
        for section in brief["required_sections"]
    }

    good = validate_script_draft(
        brief,
        {
            "sections": sections,
            "claim_ids": ["claim-1"],
            "unsupported_factual_claims": [],
        },
    )
    assert good["ready_for_storyboard_candidate"] is True

    bad = validate_script_draft(
        brief,
        {
            "sections": sections,
            "claim_ids": ["claim-999"],
            "unsupported_factual_claims": ["Made-up statistic"],
        },
    )
    assert bad["ready_for_storyboard_candidate"] is False
    assert bad["claim_lineage_valid"] is False
    assert bad["public_publish_authorized"] is False
