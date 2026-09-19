from empire_os.competitive_intelligence import (
    build_competitive_landscape,
    observed_ai_citation_share,
    observed_search_presence_share,
    review_competitor_profile,
)


def profile():
    return {
        "competitor_key": "competitor-a",
        "domain": "competitor.example",
        "observed_facts": [{
            "fact_type": "product",
            "summary": "Observed market intelligence product page.",
            "source_ref": "web:competitor-a:product",
            "observed_at": "2026-09-20T00:00:00Z",
            "confidence": .95,
        }],
        "hypotheses": [{
            "summary": "May be targeting agencies.",
            "evidence_refs": ["web:competitor-a:partners"],
        }],
    }


def test_profile_separates_facts_from_hypotheses():
    result = review_competitor_profile(profile())
    assert result["review_ready"] is True
    assert result["observed_facts"][0]["fact_type"] == "product"
    assert result["hypotheses"][0]["verified_fact"] is False
    assert result["market_share_inferred"] is False


def test_market_share_requires_explicit_source():
    row = profile()
    row["observed_market_share"] = .2
    result = review_competitor_profile(row)
    assert result["review_ready"] is False
    assert "market_share_source_ref_required" in result["blockers"]
    assert result["market_share_inferred"] is False

    row["market_share_source_ref"] = "report:market-share:1"
    ready = review_competitor_profile(row)
    assert ready["review_ready"] is True
    assert ready["observed_market_share"] == .2


def test_search_presence_share_is_not_market_share():
    observations = [
        {
            "query": "predictive revenue",
            "domain": "empire-ai.co.uk",
            "position": 1,
            "observed_at": "2026-09-20T00:00:00Z",
            "provenance": ["search_fabric"],
        },
        {
            "query": "predictive revenue",
            "domain": "competitor.example",
            "position": 2,
            "observed_at": "2026-09-20T00:00:00Z",
            "provenance": ["search_fabric"],
        },
    ]
    result = observed_search_presence_share(
        observations,
        empire_domains=["empire-ai.co.uk"],
        competitor_domains=["competitor.example"],
    )
    assert result["available"] is True
    assert result["empire_search_presence_share"] > result["competitor_search_presence_share"]
    assert result["market_share"] is None
    assert result["market_share_inferred"] is False


def test_ai_citation_share_is_not_market_share():
    observations = [
        {
            "query": "best predictive revenue software",
            "engine": "answer-engine-a",
            "cited_domain": "competitor.example",
            "citation_position": 1,
            "observed_at": "2026-09-20T00:00:00Z",
            "provenance": ["ai_visibility"],
        },
        {
            "query": "best predictive revenue software",
            "engine": "answer-engine-a",
            "cited_domain": "empire-ai.co.uk",
            "citation_position": 3,
            "observed_at": "2026-09-20T00:00:00Z",
            "provenance": ["ai_visibility"],
        },
    ]
    result = observed_ai_citation_share(
        observations,
        empire_domains=["empire-ai.co.uk"],
        competitor_domains=["competitor.example"],
    )
    assert result["available"] is True
    assert result["competitor_ai_citation_share"] > result["empire_ai_citation_share"]
    assert result["market_share"] is None
    assert result["market_share_inferred"] is False


def test_landscape_combines_profiles_and_visibility_without_execution():
    result = build_competitive_landscape(
        competitor_profiles=[profile()],
        search_observations=[{
            "query": "market intelligence software",
            "domain": "competitor.example",
            "position": 1,
            "observed_at": "2026-09-20T00:00:00Z",
            "provenance": ["search_fabric"],
        }],
        ai_citation_observations=[{
            "query": "market intelligence software",
            "engine": "answer-engine-a",
            "cited_domain": "competitor.example",
            "citation_position": 1,
            "observed_at": "2026-09-20T00:00:00Z",
            "provenance": ["ai_visibility"],
        }],
        empire_domains=["empire-ai.co.uk"],
    )
    assert result["profiles"][0]["competitor_key"] == "competitor-a"
    assert result["market_share_inferred"] is False
    assert result["market_entry_execution"] is False
    assert result["publishing_enabled"] is False
