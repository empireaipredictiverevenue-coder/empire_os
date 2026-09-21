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


def test_competitor_audience_evidence_requires_provenance():
    from empire_os.competitive_intelligence import (
        review_competitor_audience_evidence,
    )

    result = review_competitor_audience_evidence({
        "competitor_key": "competitor-a",
        "competitor_domain": "competitor.example",
        "company_name": "Acme Roofing",
        "company_domain": "acme.example",
        "evidence_type": "customer_case_study",
        "summary": "Named in a public competitor case study.",
        "observed_at": "2026-09-21T20:00:00Z",
    })

    assert result["review_ready"] is False
    assert "source_ref_required" in result["blockers"]
    assert result["buyer_intent"] is False
    assert result["execution_authority"] == "none"


def test_competitor_audience_graph_stacks_company_evidence_without_intent():
    from empire_os.competitive_intelligence import (
        build_competitor_audience_graph,
    )

    evidence = [
        {
            "competitor_key": "competitor-a",
            "competitor_domain": "competitor.example",
            "company_name": "Acme Roofing",
            "company_domain": "https://www.acme.example/",
            "evidence_type": "customer_case_study",
            "summary": "Named in a public case study.",
            "source_ref": "web:competitor-a:case-study:acme",
            "observed_at": "2026-09-21T20:00:00Z",
            "confidence": 0.95,
        },
        {
            "competitor_key": "competitor-b",
            "competitor_domain": "competitor-b.example",
            "company_name": "Acme Roofing",
            "company_domain": "acme.example",
            "evidence_type": "search_overlap",
            "summary": "Observed in the same public commercial search set.",
            "source_ref": "search:commercial-roofing:acme",
            "observed_at": "2026-09-21T20:05:00Z",
            "confidence": 0.8,
        },
    ]

    result = build_competitor_audience_graph(evidence)

    assert result["company_count"] == 1
    assert result["evidence_count"] == 2
    assert result["companies"][0]["evidence_count"] == 2
    assert result["companies"][0]["competitors"] == [
        "competitor-a",
        "competitor-b",
    ]
    assert result["companies"][0]["research_candidate"] is True
    assert result["companies"][0]["buyer_intent"] is False
    assert result["companies"][0]["commercial_intent"] is False
    assert result["companies"][0]["prospect_created"] is False
    assert result["outreach_enabled"] is False
    assert result["execution_authority"] == "none"


def test_competitor_audience_graph_rejects_unsupported_relationship_claim():
    from empire_os.competitive_intelligence import (
        build_competitor_audience_graph,
    )

    result = build_competitor_audience_graph([{
        "competitor_key": "competitor-a",
        "competitor_domain": "competitor.example",
        "company_name": "Acme Roofing",
        "company_domain": "acme.example",
        "evidence_type": "definitely_ready_to_buy",
        "summary": "Unsupported intent claim.",
        "source_ref": "web:example",
        "observed_at": "2026-09-21T20:00:00Z",
    }])

    assert result["company_count"] == 0
    assert result["rejected_evidence_count"] == 1
    assert result["buyer_intent_inferred"] is False
    assert result["commercial_intent_inferred"] is False
