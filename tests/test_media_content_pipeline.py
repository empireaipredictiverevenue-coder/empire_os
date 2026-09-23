import json

import pytest

from empire_os.media_content_pipeline import (
    build_content_pipeline,
    canonical_content_from_verified_pack,
    refresh_media_content_pipeline,
)


def verified_pack():
    return {
        "schema_version": "empire.media.verified_research_pack.v1",
        "research_id": "research:1",
        "topic": "Automation Ops",
        "thesis": "Evidence-backed automation can reduce repeated work.",
        "audience": "founders and operators",
        "opportunity_class": "community_pain",
        "opportunity_key": "community_pain:automation_ops",
        "sources": [
            {
                "source_ref": "source:1",
                "source_type": "public_source",
                "observed_at": "2026-09-23T14:00:00+00:00",
                "lineage_ref": "https://example.test/article",
                "rights_state": "RESEARCH_REFERENCE_ONLY",
            }
        ],
        "claims": [
            {
                "claim_id": "claim:1",
                "text": (
                    "Automation can reduce repetitive manual work "
                    "when the workflow is well defined."
                ),
                "evidence_refs": ["source:1"],
                "freshness_class": "CURRENT",
                "source_timestamp": "2026-09-23T14:00:00+00:00",
                "uncertainty": None,
                "verification": {
                    "verdict": "SUPPORTED",
                    "confidence": 0.95,
                    "support_source_ref": "source:1",
                    "support_quote": (
                        "Automation can reduce repetitive manual work "
                        "when the workflow is well defined."
                    ),
                },
            }
        ],
        "examples": [],
        "product_evidence_refs": [],
        "uncertainty": [
            "Audience response is not yet observed.",
        ],
        "contested_claims": [],
        "unsupported_claims": [],
        "unknown_claims": [],
        "claim_verification_complete": True,
        "script_ready": True,
        "public_publish_authorized": False,
        "execution_authority": "none",
    }


def test_verified_pack_becomes_canonical_content_with_lineage():
    result = canonical_content_from_verified_pack(verified_pack())

    assert result["schema_version"] == "empire.media.canonical_content.v1"
    assert result["source_claim_count"] == 1
    assert result["claims"][0]["claim"] == (
        "Automation can reduce repetitive manual work "
        "when the workflow is well defined."
    )
    assert result["claims"][0]["evidence_refs"] == ("source:1",)
    assert result["opportunity_refs"] == (
        "community_pain:automation_ops",
    )
    assert result["script_generation_candidate"] is True
    assert result["script_generated"] is False
    assert result["public_publish_authorized"] is False


def test_unverified_pack_cannot_become_canonical_content():
    bad = verified_pack()
    bad["script_ready"] = False

    with pytest.raises(ValueError, match="not script_ready"):
        canonical_content_from_verified_pack(bad)


def test_pipeline_creates_script_brief_not_script_prose():
    result = build_content_pipeline({
        "candidates": [verified_pack()]
    })

    assert result["canonical_content_candidate_count"] == 1
    assert result["script_brief_candidate_count"] == 1
    assert result["script_prose_generated"] is False
    assert result["unverified_claims_excluded"] is True

    brief = result["script_brief_candidates"][0]
    assert brief["script_format"] == "tutorial"
    assert brief["claim_verification_complete"] is True
    assert brief["script_generation_candidate"] is True
    assert brief["script_generation_authorized"] is True
    assert brief["claim_catalog"]["claim-1"]["evidence_refs"] == [
        "source:1"
    ]
    assert (
        brief["instructions"]["invented_statistics_allowed"]
        is False
    )
    assert brief["public_publish_authorized"] is False
    assert brief["execution_authority"] == "none"


def test_pipeline_ignores_non_script_ready_pack():
    bad = verified_pack()
    bad["script_ready"] = False

    result = build_content_pipeline({
        "candidates": [bad]
    })

    assert result["canonical_content_candidate_count"] == 0
    assert result["script_brief_candidate_count"] == 0
    assert result["rejected_count"] == 0


def test_refresh_writes_canonical_and_script_brief_artifacts(tmp_path):
    source = (
        tmp_path
        / "runtime/media_os/input/verified_research_packs.json"
    )
    source.parent.mkdir(parents=True)
    source.write_text(json.dumps({
        "candidates": [verified_pack()]
    }))

    result = refresh_media_content_pipeline(tmp_path)

    assert result["canonical_content_candidate_count"] == 1
    assert result["script_brief_candidate_count"] == 1

    canonical_path = (
        tmp_path
        / "runtime/media_os/input/canonical_content_candidates.json"
    )
    script_path = (
        tmp_path
        / "runtime/media_os/input/script_brief_candidates.json"
    )
    status_path = (
        tmp_path
        / "runtime/media_os/content_pipeline_latest.json"
    )

    assert canonical_path.exists()
    assert script_path.exists()
    assert status_path.exists()

    scripts = json.loads(script_path.read_text())
    assert scripts["candidate_count"] == 1
    assert scripts["script_prose_generated"] is False
    assert scripts["public_publish_authorized"] is False
