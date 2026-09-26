from empire_os.competitor_audience_priority import (
    rank_competitor_audience_companies,
    score_competitor_audience_company,
)


def _company(name, entity_id, refs, competitors=None):
    competitors = competitors or ["elite-roofing-solar"]
    evidence = []
    for index, ref in enumerate(refs):
        evidence.append({
            "competitor_key": competitors[index % len(competitors)],
            "evidence_type": "comparison_mention",
            "source_ref": ref,
            "confidence": 0.9,
        })
    return {
        "entity_id": entity_id,
        "company_name": name,
        "evidence": evidence,
    }


def test_single_evidence_is_research_only():
    result = score_competitor_audience_company(
        _company(
            "Colorado's Best Roofing",
            "entity-colorado",
            ["https://example.test/a"],
        )
    )

    assert result["stack_state"] == "SINGLE_EVIDENCE"
    assert result["research_candidate"] is True
    assert result["recommendation_only"] is True
    assert result["buyer_intent"] is False
    assert result["commercial_intent"] is False
    assert result["outreach_enabled"] is False
    assert result["execution_authority"] == "none"


def test_three_independent_sources_create_stacked_research_signal():
    result = score_competitor_audience_company(
        _company(
            "Golden Spike Roofing Inc",
            "entity-golden",
            [
                "https://example.test/a",
                "https://example.test/b",
                "https://example.test/c",
            ],
        )
    )

    assert result["stack_state"] == "STACKED"
    assert result["evidence_count"] == 3
    assert result["source_count"] == 3
    assert result["research_priority_score"] > 70


def test_ranking_prefers_deeper_evidence_stack():
    rows = rank_competitor_audience_companies([
        _company(
            "Colorado's Best Roofing",
            "entity-colorado",
            ["https://example.test/a"],
        ),
        _company(
            "Golden Spike Roofing Inc",
            "entity-golden",
            [
                "https://example.test/a",
                "https://example.test/b",
                "https://example.test/c",
            ],
        ),
    ])

    assert rows[0]["company_name"] == "Golden Spike Roofing Inc"
    assert rows[0]["research_priority_rank"] == 1
    assert rows[1]["research_priority_rank"] == 2


def test_competitor_diversity_can_raise_research_priority_without_intent():
    one = score_competitor_audience_company(
        _company(
            "Company A",
            "entity-a",
            [
                "https://example.test/a",
                "https://example.test/b",
            ],
            competitors=["competitor-a"],
        )
    )
    two = score_competitor_audience_company(
        _company(
            "Company A",
            "entity-a",
            [
                "https://example.test/a",
                "https://example.test/b",
            ],
            competitors=["competitor-a", "competitor-b"],
        )
    )

    assert two["research_priority_score"] > one["research_priority_score"]
    assert two["buyer_intent"] is False
    assert two["commercial_intent"] is False
    assert two["outreach_enabled"] is False
