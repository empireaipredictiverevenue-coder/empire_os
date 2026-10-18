"""External source-title benchmark: provenance and no invented buyer evidence."""
from empire_os.search_intelligence.local_embedding_runtime import LocalSemanticEmbedder
from scripts.benchmark_semantic_source_titles import (
    SOURCE_TITLES, run_source_title_review,
)


class FakeEmbeddingModel:
    def embed(self, texts, *, batch_size, parallel):
        output = []
        for query in texts:
            terms = query.lower()
            if any(t in terms for t in ("solar", "photovoltaic")):
                index = 0
            elif any(t in terms for t in ("heat", "cooling", "pump", "geothermal")):
                index = 1
            elif any(t in terms for t in ("roof", "asphalt")):
                index = 2
            else:
                index = 3
            vec = [0.] * 384
            vec[index] = 1.
            output.append(vec)
        return output


def test_titles_have_real_source_url_and_sector_labels():
    assert len(SOURCE_TITLES) == 12
    sectors = {sector for _, sector, _ in SOURCE_TITLES}
    assert sectors == {"roofing", "hvac", "solar", "predictive-revenue-os"}
    assert all(url.startswith("https://") for _, _, url in SOURCE_TITLES)
    assert all(len(title) > 8 for title, _, _ in SOURCE_TITLES)
    assert len({title for title, _, _ in SOURCE_TITLES}) == 12


def test_external_titles_stay_document_titles_not_search_demand(tmp_path):
    cache = tmp_path / "model"
    cache.mkdir()
    (cache / "model_optimized.onnx").write_bytes(b"test" * 300_000)
    encoder = LocalSemanticEmbedder(
        model_cache=cache, model_loader=lambda _: FakeEmbeddingModel(),
    )
    products = ("roofing", "solar", "hvac", "predictive-revenue-os")
    corpus = [
        {
            "keyword": title,
            "product_key": product,
            "cluster_key": product,
            "intent_class": "commercial",
            "icp_key": "operator",
            "funnel_stage": "conversion",
            "cta_key": "commercial",
            "evidence_refs": ["fixture:page-meta"],
        }
        for title, product in zip(
            ("Roofing commercial buyers", "Solar installer demand",
             "HVAC heating and cooling", "Forecast revenue pipeline"),
            products,
        )
    ]
    result = run_source_title_review(corpus, encoder)
    assert result["source_document_title_count"] == 12
    assert len(result["sample_cases"]) == 12
    assert all(item["source_url"].startswith("https://")
               for item in result["sample_cases"])
    assert result["source_titles_are_buyer_queries"] is False
    assert result["independently_human_annotated"] is False
    assert result["random_sample"] is False
    assert result["automatic_decision_authorized"] is False
    assert result["result_implies_search_visibility"] is False
    assert result["revenue_verified"] is False
    assert result["external_paid_api_calls"] == 0
    assert result["sector_review_reassigned_rankings"] is False
