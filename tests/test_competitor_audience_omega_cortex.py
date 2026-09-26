from empire_os.competitor_audience_omega_cortex import (
    build_competitor_omega_cortex_context,
)


def _priority(
    name,
    entity_id,
    score,
    stack_state,
    evidence_count,
    source_count,
):
    return {
        "entity_id": entity_id,
        "company_name": name,
        "research_priority_score": score,
        "stack_state": stack_state,
        "evidence_count": evidence_count,
        "source_count": source_count,
        "competitor_count": 1,
        "confidence": 0.9,
        "dimensions": {
            "evidence_depth": min(evidence_count / 3, 1),
            "source_diversity": min(source_count / 3, 1),
            "competitor_diversity": 0.5,
            "evidence_type_diversity": 1 / 3,
        },
    }


def test_stacked_evidence_becomes_deep_research_context_only():
    rows = build_competitor_omega_cortex_context([
        _priority(
            "Golden Spike Roofing Inc",
            "entity-golden",
            84.33,
            "STACKED",
            3,
            3,
        )
    ])

    row = rows[0]
    assert row["next_best_research_action"] == "deep_account_research"
    assert row["omega"]["context_available"] is True
    assert row["omega"]["lead_qualification_mutation"] is False
    assert row["omega"]["score_persistence_authorized"] is False
    assert row["cortex"]["learning_context_available"] is True
    assert row["cortex"]["verified_outcome"] is False
    assert row["cortex"]["training_label"] is None
    assert row["buyer_intent"] is False
    assert row["commercial_intent"] is False
    assert row["outreach_enabled"] is False
    assert row["execution_authority"] == "none"


def test_single_evidence_requests_more_public_evidence():
    rows = build_competitor_omega_cortex_context([
        _priority(
            "Colorado's Best Roofing",
            "entity-colorado",
            44.33,
            "SINGLE_EVIDENCE",
            1,
            1,
        )
    ])

    assert rows[0]["next_best_research_action"] == (
        "collect_additional_public_evidence"
    )


def test_context_ranking_preserves_research_priority_order():
    rows = build_competitor_omega_cortex_context([
        _priority(
            "Colorado's Best Roofing",
            "entity-colorado",
            44.33,
            "SINGLE_EVIDENCE",
            1,
            1,
        ),
        _priority(
            "Golden Spike Roofing Inc",
            "entity-golden",
            84.33,
            "STACKED",
            3,
            3,
        ),
    ])

    assert rows[0]["company_name"] == "Golden Spike Roofing Inc"
    assert rows[0]["research_rank"] == 1
    assert rows[1]["research_rank"] == 2


def test_priority_score_is_normalized_not_promoted_to_buyer_score():
    rows = build_competitor_omega_cortex_context([
        _priority(
            "Golden Spike Roofing Inc",
            "entity-golden",
            84.33,
            "STACKED",
            3,
            3,
        )
    ])

    row = rows[0]
    assert row["features"]["research_priority"] == 0.8433
    assert "buyer_score" not in row["features"]
    assert "commercial_score" not in row["features"]
