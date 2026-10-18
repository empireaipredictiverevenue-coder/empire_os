"""Hybrid/semantic keyword retrieval is evidence-bound and read-only."""
from copy import deepcopy

import pytest

from empire_os.semantic_keyword_search import (
    SemanticSearchInputError,
    cluster_keyword_topics,
    search_keyword_universe,
)


def kw(keyword, *, product="roofing", intent="commercial", stage="conversion",
       territory="US-CHI", cluster="roofing-demand", embedding=None,
       model="local-test-model-v1", ref="vector:synthetic"):
    data = {
        "keyword": keyword,
        "product_key": product,
        "cluster_key": cluster,
        "icp_key": "business-owner",
        "intent_class": intent,
        "funnel_stage": stage,
        "territory_key": territory,
        "cta_key": "commercial-enquiry",
        "evidence_refs": ["fixture:keyword:" + keyword],
    }
    if embedding is not None:
        data["embedding"] = embedding
        data["embedding_model"] = model
        data["embedding_evidence_ref"] = ref
    return data


def test_lexical_fallback_is_honest_and_preserves_metadata():
    rows = [kw("roofing leads chicago"), kw("solar leads texas", product="solar", territory="US-TX")]
    report = search_keyword_universe(rows, "roofing leads in chicago")
    assert report["mode"] == "OBSERVE"
    assert report["search_mode"] == "LEXICAL_ONLY"
    assert report["results"][0]["keyword"] == "roofing leads chicago"
    assert report["results"][0]["retrieval_method"] == "lexical_tfidf"
    assert report["results"][0]["embedding_score"] is None
    assert report["results"][0]["evidence_refs"] == ["fixture:keyword:roofing leads chicago"]
    assert report["results"][0]["verified_search_volume"] is None
    assert report["results"][0]["verified_revenue"] is None
    assert report["results"][0]["publication_authorized"] is False
    assert report["publishing_enabled"] is False


def test_dense_search_finds_semantically_equivalent_phrase_without_overlap():
    rows = [
        kw("solar photovoltaic installation quotation", product="solar", territory="GB",
           embedding=[1.0, 0.0]),
        kw("roofing inspection", embedding=[0.0, 1.0]),
    ]
    result = search_keyword_universe(
        rows, "how much are PV fitment estimates",
        query_embedding=[1.0, 0.0],
        embedding_model="local-test-model-v1",
        query_embedding_evidence_ref="query:synth-1",
        product_key="solar",
        territory_key="GB",
    )
    assert result["search_mode"] == "HYBRID"
    assert result["results"][0]["keyword"] == "solar photovoltaic installation quotation"
    assert result["results"][0]["embedding_score"] == 1
    assert result["results"][0]["retrieval_method"] == "hybrid_semantic_lexical"
    assert result["results"][0]["embedding_evidence_ref"] == "vector:synthetic"


def test_embedding_mismatch_falls_back_to_lexical_not_fake_similarity():
    rows = [kw("roofing leads chicago", embedding=[1.0, 0.0])]
    report = search_keyword_universe(
        rows, "roofing leads",
        query_embedding=[1.0, 0.0],
        embedding_model="other-model",
        query_embedding_evidence_ref="query:other-model",
    )
    assert report["search_mode"] == "LEXICAL_ONLY"
    assert report["results"][0]["embedding_score"] is None


def test_query_vectors_require_model_and_provenance():
    with pytest.raises(SemanticSearchInputError, match="requires model"):
        search_keyword_universe([kw("roofing leads")], "roofing",
                                query_embedding=[1.0, 0.0])
    with pytest.raises(SemanticSearchInputError, match="requires model"):
        search_keyword_universe([kw("roofing leads")], "roofing",
                                query_embedding=[1.0, 0.0], embedding_model="M")


@pytest.mark.parametrize("vector", [
    [], [0.0, 0.0], [1.0, float("nan")], [1.0, float("inf")],
    [1.0, True], ["1", 0], [1], [1] * 4097,
])
def test_invalid_embedding_fails_closed(vector):
    with pytest.raises(SemanticSearchInputError):
        search_keyword_universe(
            [kw("roofing lead", embedding=vector)], "roofing"
        )


def test_vector_length_mismatch_rejected_not_reinterpreted():
    with pytest.raises(SemanticSearchInputError, match="dimensions"):
        search_keyword_universe(
            [kw("roofing leads", embedding=[1.0, 0.0, 0.0])], "roofing",
            query_embedding=[1.0, 0.0],
            embedding_model="local-test-model-v1",
            query_embedding_evidence_ref="q:1",
        )


def test_unknown_evidence_and_duplicate_keyword_rejected():
    invalid = kw("roofing leads")
    invalid["evidence_refs"] = []
    with pytest.raises(ValueError, match="evidence_refs"):
        search_keyword_universe([invalid], "roofing")
    with pytest.raises(SemanticSearchInputError, match="duplicate"):
        search_keyword_universe([kw("roofing leads"), kw("ROOFING LEADS")], "roofing")


def test_no_cross_industry_or_territory_implicit_expansion():
    rows = [kw("roofing leads chicago"), kw("solar leads chicago", product="solar"),
            kw("roofing leads london", territory="GB-LDN")]
    report = search_keyword_universe(
        rows, "leads", product_key="roofing", territory_key="US-CHI",
    )
    assert report["eligible_records"] == 1
    assert [r["keyword"] for r in report["results"]] == ["roofing leads chicago"]


def test_intent_filter_protects_commercial_from_educational():
    rows = [kw("roofing price quote", intent="commercial"),
            kw("how roofing is installed", intent="education", stage="awareness")]
    report = search_keyword_universe(rows, "roofing", intent_class="commercial")
    assert len(report["results"]) == 1
    assert report["results"][0]["intent_class"] == "commercial"


def test_empty_corpus_returns_explicit_empty_not_estimated_demand():
    report = search_keyword_universe([], "roofing")
    assert report["eligible_records"] == 0
    assert report["results"] == []
    assert report["search_mode"] == "LEXICAL_ONLY"


@pytest.mark.parametrize("query,topk", [("", 2), ("roofing", 0), ("roofing", 101),
                                         ("roofing", True)])
def test_invalid_query_or_limits_rejected(query, topk):
    with pytest.raises(SemanticSearchInputError):
        search_keyword_universe([kw("roofing leads")], query, top_k=topk)


def test_semantic_cluster_groups_same_intent_different_wording():
    rows = [
        kw("roofing price quotation", embedding=[1.0, 0.01], cluster="roof-pricing"),
        kw("roof replacement estimate", embedding=[1.0, 0.0], cluster="replacement-quotes"),
        kw("solar photovoltaic installation quote", embedding=[1.0, 0.0],
           product="solar", cluster="solar-quotes"),
        kw("roofing beginner safety guide", intent="education", stage="awareness",
           embedding=[1.0, 0.0], cluster="roofing-guides"),
    ]
    result = cluster_keyword_topics(rows)
    multi = [g for g in result["groups"] if len(g["keywords"]) > 1]
    assert len(multi) == 1
    assert multi[0]["method"] == "semantic_embedding"
    assert multi[0]["possible_content_overlap"] is True
    assert len(multi[0]["evidence_refs"]) == 2
    assert multi[0]["verified_demand"] is None
    assert result["publishing_enabled"] is False


def test_lexical_cluster_does_not_pretend_to_be_semantic():
    rows = [kw("chicago roofing leads"), kw("roofing leads chicago"),
            kw("roofing leads london", territory="GB")]
    grouped = cluster_keyword_topics(rows, min_similarity=.8)
    multi = [g for g in grouped["groups"] if len(g["keywords"]) > 1]
    assert len(multi) == 1
    assert multi[0]["method"] == "lexical_tfidf"
    assert multi[0]["territory_key"] == "US-CHI"
    assert not any("roofing leads london" in g["keywords"] and len(g["keywords"]) > 1
                   for g in grouped["groups"])


def test_pairwise_complete_link_avoids_topic_chaining():
    # A~B and B~C but A!~C should NOT collapse all three into one topic.
    rows = [kw("a", embedding=[1.0, 0.0]),
            kw("b", embedding=[.71, .71]),
            kw("c", embedding=[0.0, 1.0])]
    groups = cluster_keyword_topics(rows, min_similarity=.7)["groups"]
    assert sorted(len(g["keywords"]) for g in groups) == [1, 2]


def test_input_not_mutated_and_results_deterministic():
    rows = [kw("roofing estimate chicago"), kw("roofing quote chicago")]
    old = deepcopy(rows)
    a = search_keyword_universe(rows, "roofing chicago")
    b = search_keyword_universe(rows, "roofing chicago")
    assert rows == old
    assert a == b


def test_offline_cli_returns_evidence_grounded_search_and_topics(tmp_path, capsys):
    import json
    from scripts.review_semantic_keywords import main

    source = tmp_path / "keywords.json"
    source.write_text(json.dumps({
        "keywords": [kw("roofing quote chicago"), kw("roofing quote chicago prices")]
    }))
    assert main([str(source), "--query", "chicago roofing quote"]) == 0
    search_report = json.loads(capsys.readouterr().out)
    assert search_report["input_sha256"]
    assert search_report["source_claim"] == "user_supplied_unverified"
    assert search_report["review"]["search_mode"] == "LEXICAL_ONLY"
    assert search_report["review"]["results"][0]["evidence_refs"]
    assert main([str(source), "--topics"]) == 0
    topic_report = json.loads(capsys.readouterr().out)
    assert topic_report["review"]["mode"] == "OBSERVE"
    assert topic_report["review"]["publishing_enabled"] is False


def test_cli_invalid_or_misleading_input_fails_closed(tmp_path, capsys):
    import json
    from scripts.review_semantic_keywords import main

    source = tmp_path / "keyword_input.json"
    source.write_text(json.dumps({"keywords": [kw("roofing leads")],
                                  "query_embedding": [1, 0]}))
    assert main([str(source), "--query", "roofing"]) == 2
    error = json.loads(capsys.readouterr().err)
    assert error["status"] == "UNAVAILABLE"
    assert "requires model" in error["detail"]


def test_topic_cluster_rejects_excessively_large_inputs():
    with pytest.raises(SemanticSearchInputError, match="500"):
        cluster_keyword_topics(
            [kw("roof keyword %d" % i) for i in range(501)]
        )
