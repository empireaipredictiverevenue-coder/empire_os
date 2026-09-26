from uuid import uuid4

import pytest

from empire_os.intelligence_materializer import (
    IntelligenceMaterializerError,
    build_materialization_plan,
)


def inputs():
    prospect_id = str(uuid4())
    entity_id = str(uuid4())
    qualification_id = str(uuid4())
    prospect = {
        "id": prospect_id,
        "created_at": "2026-09-19T09:00:00+00:00",
        "business_name": "Acme Ltd",
        "niche": "roofing",
        "metro": "London",
        "phone": "+44 20 7946 0958",
        "address": "1 Test Street",
        "rating": 0,
        "review_count": 0,
        "runs_ads": False,
    }
    link = {
        "prospect_id": prospect_id,
        "entity_id": entity_id,
        "match_score": 0.82,
        "active": True,
    }
    qualification = {
        "id": qualification_id,
        "prospect_id": prospect_id,
        "score": 76.4,
        "tier": "hot",
        "data_completeness_score": 60.0,
        "business_presence_score": 80.0,
        "market_fit_score": 70.0,
        "engagement_potential_score": 0.0,
        "enrichment_quality_score": 20.0,
        "recommended_action": "Contact immediately",
        "scoring_engine": "empire_os.lead_scoring",
        "scoring_version": "v1",
        "scored_at": "2026-09-19T09:05:00+00:00",
    }
    return prospect, link, qualification


def test_builds_evidence_preserving_plan():
    prospect, link, qualification = inputs()
    plan = build_materialization_plan(
        prospect=prospect,
        identity_link=link,
        qualification=qualification,
    )

    assert plan.prospect_id == prospect["id"]
    assert plan.entity_id == link["entity_id"]
    assert len(plan.fact_rows) == 8
    assert len(plan.score_rows) == 1
    assert plan.skipped_fields == ()

    facts = {row.fact_key: row for row in plan.fact_rows}
    assert facts["runs_ads"].fact_value["value"] is False
    assert facts["rating"].fact_value["value"] == 0
    assert facts["review_count"].fact_value["value"] == 0
    assert facts["business_name"].confidence == 0.82
    assert facts["phone"].fact_value["value"] == "+44 20 7946 0958"
    assert len(facts["business_name"].evidence_hash) == 64

    score = plan.score_rows[0]
    assert score.score == 76.4
    assert score.confidence == 0.60
    assert score.model_key == "empire_os.lead_scoring:v1"
    assert (
        score.explanation["confidence_basis"]
        == "data_completeness_score/100; legacy v1 "
        "completeness proxy, not outcome-calibrated "
        "predictive confidence"
    )


def test_v2_uses_evidence_confidence_not_completeness():
    prospect, link, qualification = inputs()
    qualification.update({
        "scoring_version": "v2",
        "data_completeness_score": 80.0,
        "evidence_confidence": 0.35,
        "observed_dimensions": ["market_fit"],
        "unknown_dimensions": [
            "business_presence",
            "engagement_potential",
            "enrichment_quality",
        ],
    })

    plan = build_materialization_plan(
        prospect=prospect,
        identity_link=link,
        qualification=qualification,
    )

    score = plan.score_rows[0]
    assert score.confidence == 0.35
    assert score.model_key == "empire_os.lead_scoring:v2"
    assert score.features["source_key"] == (
        "empire.qualification.lead_scoring.v2"
    )
    assert score.features["observed_dimensions"] == ["market_fit"]
    assert score.features["unknown_dimensions"] == [
        "business_presence",
        "engagement_potential",
        "enrichment_quality",
    ]
    assert score.explanation["confidence_basis"].startswith(
        "qualification.evidence_confidence"
    )


def test_v2_missing_evidence_confidence_fails_closed():
    prospect, link, qualification = inputs()
    qualification["scoring_version"] = "v2"
    qualification["evidence_confidence"] = None

    with pytest.raises(
        IntelligenceMaterializerError,
        match="v2 evidence confidence is required",
    ):
        build_materialization_plan(
            prospect=prospect,
            identity_link=link,
            qualification=qualification,
        )


def test_missing_fields_are_skipped_not_invented():
    prospect, link, qualification = inputs()
    prospect["address"] = ""
    prospect["rating"] = None
    qualification["score"] = None

    plan = build_materialization_plan(
        prospect=prospect,
        identity_link=link,
        qualification=qualification,
    )

    keys = {row.fact_key for row in plan.fact_rows}
    assert "address" not in keys
    assert "rating" not in keys
    assert "address" in plan.skipped_fields
    assert "rating" in plan.skipped_fields
    assert "qualification_score" in plan.skipped_fields
    assert plan.score_rows == ()


def test_inactive_identity_link_fails_closed():
    prospect, link, qualification = inputs()
    link["active"] = False

    with pytest.raises(
        IntelligenceMaterializerError,
        match="not active",
    ):
        build_materialization_plan(
            prospect=prospect,
            identity_link=link,
            qualification=qualification,
        )


def test_invalid_identity_confidence_fails_closed():
    prospect, link, qualification = inputs()
    link["match_score"] = 1.2

    with pytest.raises(
        IntelligenceMaterializerError,
        match="between 0 and 1",
    ):
        build_materialization_plan(
            prospect=prospect,
            identity_link=link,
            qualification=qualification,
        )


def test_data_completeness_is_bounded():
    prospect, link, qualification = inputs()
    qualification["data_completeness_score"] = 110

    with pytest.raises(
        IntelligenceMaterializerError,
        match="data completeness",
    ):
        build_materialization_plan(
            prospect=prospect,
            identity_link=link,
            qualification=qualification,
        )


def test_evidence_hash_is_deterministic():
    prospect, link, qualification = inputs()

    first = build_materialization_plan(
        prospect=prospect,
        identity_link=link,
        qualification=qualification,
    )
    second = build_materialization_plan(
        prospect=prospect,
        identity_link=link,
        qualification=qualification,
    )

    assert [
        row.evidence_hash for row in first.fact_rows
    ] == [
        row.evidence_hash for row in second.fact_rows
    ]


def test_identity_link_must_belong_to_prospect():
    prospect, link, qualification = inputs()
    link["prospect_id"] = str(uuid4())

    with pytest.raises(
        IntelligenceMaterializerError,
        match="identity link prospect mismatch",
    ):
        build_materialization_plan(
            prospect=prospect,
            identity_link=link,
            qualification=qualification,
        )


def test_qualification_must_belong_to_prospect():
    prospect, link, qualification = inputs()
    qualification["prospect_id"] = str(uuid4())

    with pytest.raises(
        IntelligenceMaterializerError,
        match="qualification prospect mismatch",
    ):
        build_materialization_plan(
            prospect=prospect,
            identity_link=link,
            qualification=qualification,
        )
