"""Semantic keywords map to page evidence only, never indexing/revenue proof."""
import pytest

from empire_os.search_intelligence.semantic_coverage import review_semantic_page_coverage
from empire_os.semantic_keyword_search import SemanticSearchInputError


def keyword(word="commercial roofing quote chicago", **kwargs):
    return {
        "keyword": word,
        "cluster_key": "chicago-roofing",
        "product_key": "roofing",
        "icp_key": "roofer",
        "intent_class": "commercial",
        "funnel_stage": "conversion",
        "territory_key": "US-CHI",
        "cta_key": "roofing-assessment",
        "evidence_refs": ["gsc:source:synthetic"],
        **kwargs,
    }


def page(url="https://empire-ai.co.uk/industries/roofing", **kwargs):
    return {
        "canonical_url": url,
        "title": "Commercial roofing quote chicago",
        "target_query": "roofing quote",
        "topic": "chicago roofing demand",
        "product_key": "roofing",
        "territory_key": "US-CHI",
        "search_intent": "commercial",
        "funnel_stage": "conversion",
        "evidence_refs": ["crawl:synthetic"],
        **kwargs,
    }


def test_matching_page_is_only_potential_metadata_coverage():
    data = review_semantic_page_coverage(
        [keyword()], [page()], owned_domain="empire-ai.co.uk"
    )
    assert data["mode"] == "OBSERVE"
    assert data["evidenced_page_count"] == 1
    finding = data["findings"][0]
    assert finding["status"] == "POTENTIAL_METADATA_COVERAGE"
    assert finding["candidate_pages"][0]["canonical_url"].endswith("/industries/roofing")
    assert finding["candidate_pages"][0]["page_evidence_refs"] == ["crawl:synthetic"]
    assert finding["candidate_pages"][0]["google_indexation_proven"] is False
    assert finding["real_search_demand_verified"] is False
    assert data["publishing_enabled"] is False


def test_missing_page_never_claims_index_gap_with_incomplete_inventory():
    data = review_semantic_page_coverage(
        [keyword()], [], owned_domain="empire-ai.co.uk",
    )
    assert data["findings"][0]["status"] == "UNKNOWN_INCOMPLETE_PAGE_INVENTORY"
    assert data["indexed_page_count_claimed"] is None


def test_completeness_is_local_metadata_review_not_google_claim():
    data = review_semantic_page_coverage(
        [keyword()], [], owned_domain="empire-ai.co.uk", inventory_complete=True,
    )
    assert data["findings"][0]["status"] == "REVIEW_LOCAL_METADATA_GAP"
    assert data["findings"][0]["google_indexation_verified"] is False


def test_cross_product_territory_intent_and_stage_do_not_match():
    pages = [
        page(product_key="solar"),
        page(territory_key="GB-LDN", canonical_url="https://empire-ai.co.uk/solar"),
        page(search_intent="education", canonical_url="https://empire-ai.co.uk/learn"),
        page(funnel_stage="awareness", canonical_url="https://empire-ai.co.uk/faq"),
    ]
    data = review_semantic_page_coverage(
        [keyword()], pages, owned_domain="empire-ai.co.uk",
    )
    assert data["findings"][0]["eligible_page_count"] == 0
    assert data["findings"][0]["candidate_pages"] == []


def test_duplicate_pages_are_not_cannibalisation():
    p = page()
    data = review_semantic_page_coverage(
        [keyword()], [p, p], owned_domain="empire-ai.co.uk",
    )
    assert data["evidenced_page_count"] == 1
    assert data["findings"][0]["possible_cannibalisation"] == []


def test_two_matching_pages_reuse_existing_cannibalisation_detector():
    pages = [
        page(),
        page("https://empire-ai.co.uk/roofing/quotes"),
    ]
    data = review_semantic_page_coverage(
        [keyword()], pages, owned_domain="empire-ai.co.uk",
    )
    finding = data["findings"][0]
    assert len(finding["candidate_pages"]) == 2
    assert len(finding["possible_cannibalisation"]) == 1
    overlap = finding["possible_cannibalisation"][0]
    assert overlap["execution_allowed"] is False
    assert overlap["evidence"]["candidate_primary_url"] is None


def test_unevidenced_pages_are_excluded_not_assumed_true():
    page_no_evidence = page()
    page_no_evidence["evidence_refs"] = []
    data = review_semantic_page_coverage(
        [keyword()], [page_no_evidence], owned_domain="empire-ai.co.uk",
    )
    assert data["rejected_unevidenced_page_rows"] == 1
    assert data["evidenced_page_count"] == 0
    assert data["findings"][0]["status"] == "UNKNOWN_INCOMPLETE_PAGE_INVENTORY"


def test_semantic_page_relevance_requires_matched_model_and_provenance():
    k = keyword(embedding=[1.0, 0.0], embedding_model="shared-local-model",
                embedding_evidence_ref="keyword-embedding:proof")
    p = page(
        "https://empire-ai.co.uk/roofing/pricing",
        title="contractor expenditure",
        target_query="construction vendor spending",
        topic="project budgets",
        embedding=[1.0, 0.0],
        embedding_model="shared-local-model",
        embedding_evidence_ref="page-embedding:proof",
    )
    data = review_semantic_page_coverage([k], [p], owned_domain="empire-ai.co.uk")
    match = data["findings"][0]["candidate_pages"][0]
    assert match["retrieval_method"] == "hybrid_semantic_lexical"
    assert match["embedding_evidence_refs"] == [
        "keyword-embedding:proof", "page-embedding:proof"
    ]
    assert match["page_content_verified"] is False


def test_no_access_to_other_tenant_or_domain():
    with pytest.raises(SemanticSearchInputError, match="domain"):
        review_semantic_page_coverage(
            [keyword()], [page("https://someone-else.example/")],
            owned_domain="empire-ai.co.uk",
        )
    with pytest.raises(SemanticSearchInputError, match="tenant"):
        review_semantic_page_coverage(
            [keyword()], [page(tenant_id="other-tenant")],
            owned_domain="empire-ai.co.uk", tenant_id="empire",
        )


def test_invalid_threshold_or_missing_domain_rejected():
    with pytest.raises(SemanticSearchInputError, match="threshold"):
        review_semantic_page_coverage(
            [keyword()], [page()], owned_domain="empire-ai.co.uk",
            threshold=0,
        )
    with pytest.raises(SemanticSearchInputError, match="owned_domain"):
        review_semantic_page_coverage([keyword()], [page()], owned_domain="")


def test_semantic_review_cli_pages_end_to_end(tmp_path, capsys):
    import json
    from scripts.review_semantic_keywords import main

    keywords_file = tmp_path / "k.json"
    pages_file = tmp_path / "p.json"
    keywords_file.write_text(json.dumps({"keywords": [keyword()]}))
    pages_file.write_text(json.dumps({"pages": [page()]}))
    assert main([
        str(keywords_file), "--pages", str(pages_file),
        "--owned-domain", "empire-ai.co.uk",
    ]) == 0
    report = json.loads(capsys.readouterr().out)
    assert set(report["input_sha256_by_type"]) == {"keywords", "pages"}
    assert report["review"]["findings"][0]["status"] == "POTENTIAL_METADATA_COVERAGE"
    assert report["review"]["publishing_enabled"] is False


def test_semantic_review_cli_pages_requires_site_scope(tmp_path, capsys):
    import json
    from scripts.review_semantic_keywords import main

    keywords_file = tmp_path / "k.json"
    pages_file = tmp_path / "p.json"
    keywords_file.write_text(json.dumps({"keywords": [keyword()]}))
    pages_file.write_text(json.dumps({"pages": [page()]}))
    assert main([str(keywords_file), "--pages", str(pages_file)]) == 2
    assert "owned-domain" in json.loads(capsys.readouterr().err)["detail"]
