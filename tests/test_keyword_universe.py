from empire_os.keyword_universe import (
    build_asset_backlog,
    build_keyword_universe,
    keyword_coverage_matrix,
    review_keyword_record,
)


def keyword(name="predictive revenue", stage="awareness", intent="category"):
    return {
        "keyword": name,
        "cluster_key": "predictive-revenue",
        "intent_class": intent,
        "product_key": "predictive-revenue-os",
        "icp_key": "revenue-leader",
        "funnel_stage": stage,
        "cta_key": "review-opportunity",
        "free_tool_key": "revenue-leak-scanner",
        "evidence_refs": [f"kw:{name}"],
        "observed_demand": .8,
        "commercial_intent": .7,
        "product_fit": .95,
        "buyer_fit": .9,
        "coverage_gap": .8,
        "competitor_gap": .7,
        "ai_citation_gap": .8,
        "conversion_evidence": .5,
        "strategic_category_value": 1.0,
        "confidence": .8,
    }


def test_keyword_record_maps_to_product_funnel_asset_and_cta():
    result = review_keyword_record(keyword())
    assert result["review_ready"] is True
    assert result["record"]["product_key"] == "predictive-revenue-os"
    assert result["record"]["asset_type"] == "pillar_page"
    assert result["record"]["cta_key"] == "review-opportunity"
    assert result["publishing_enabled"] is False
    assert result["indexation_enabled"] is False


def test_keyword_unknown_metrics_remain_unscored():
    row = keyword()
    row["observed_demand"] = None
    result = review_keyword_record(row)
    assert result["review_ready"] is True
    assert result["opportunity"]["available"] is False
    assert "observed_demand" in result["opportunity"]["missing"]


def test_universe_ranks_evidence_backed_terms():
    strong = keyword("predictive revenue")
    weak = keyword("generic ai business tool")
    for field in (
        "observed_demand",
        "commercial_intent",
        "product_fit",
        "buyer_fit",
        "coverage_gap",
        "competitor_gap",
        "ai_citation_gap",
        "conversion_evidence",
        "strategic_category_value",
        "confidence",
    ):
        weak[field] = .3

    result = build_keyword_universe([weak, strong])
    assert result["keywords"][0]["record"]["keyword"] == "predictive revenue"
    assert result["keywords"][0]["universe_rank"] == 1
    assert result["publishing_enabled"] is False


def test_coverage_matrix_exposes_missing_funnel_stages():
    result = keyword_coverage_matrix([
        keyword("predictive revenue", "awareness"),
        keyword("predictive revenue software pricing", "conversion", "commercial"),
    ])
    assert result["by_product"]["predictive-revenue-os"]["awareness"] == 1
    assert result["by_product"]["predictive-revenue-os"]["conversion"] == 1
    missing = {
        row["funnel_stage"]
        for row in result["coverage_gaps"]
        if row["product_key"] == "predictive-revenue-os"
    }
    assert "consideration" in missing
    assert "evaluation" in missing


def test_asset_backlog_is_draft_only():
    result = build_asset_backlog([
        keyword("predictive revenue"),
        keyword("predictive revenue software pricing", "conversion", "commercial"),
    ])
    assert len(result["assets"]) == 2
    assert all(item["draft_only"] for item in result["assets"])
    assert result["publishing_enabled"] is False
    assert result["indexation_enabled"] is False
