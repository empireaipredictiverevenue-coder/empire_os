#!/usr/bin/env python3
"""Human-labelled relevance probe against current owned commercial page titles.

This is a curated retrieval benchmark, NOT historical user searches,
search-volume measurement, conversion evidence, or an independent evaluation.
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Callable

from empire_os.search_intelligence.first_party_semantic_corpus import (
    PRIORITY_PAGES, page_record,
)
from empire_os.search_intelligence.local_embedding_runtime import (
    LocalSemanticEmbedder, IsolatedFastEmbedProcess,
    attach_keyword_embeddings, LocalEmbeddingUnavailable,
)
from empire_os.semantic_keyword_search import search_keyword_universe
from empire_os.search_intelligence.semantic_sector_review import review_query_sector
from scripts.review_live_first_party_semantic import _get_public_html


# Explicit developer-authored evaluation cases, 5 per topic.
# Labels are editorial hypotheses, not observed audience search queries.
CASES: tuple[tuple[str, str], ...] = (
    ("How do commercial roof contractors find qualified projects", "roofing"),
    ("Industrial roof repairs buyers and estimates", "roofing"),
    ("Winning flat roof replacement enquiries", "roofing"),
    ("Which businesses need commercial roof restoration", "roofing"),
    ("Roofing lead qualification for a business", "roofing"),
    ("How to find companies that install photovoltaic panels", "solar"),
    ("Solar panel contractor coverage and territory", "solar"),
    ("Qualify home PV installation enquiries", "solar"),
    ("Photovoltaic install opportunities UK", "solar"),
    ("Who accepts rooftop solar referrals", "solar"),
    ("Heat pump installers looking for customers", "hvac"),
    ("Air conditioning maintenance demand", "hvac"),
    ("Heating ventilation and climate service enquiries", "hvac"),
    ("Qualified leads for HVAC contractors", "hvac"),
    ("Local cooling and heating repair businesses", "hvac"),
    ("Predict sales pipeline outcome using AI", "predictive-revenue-os"),
    ("How to prove which forecast deals became income", "predictive-revenue-os"),
    ("Revenue projections compared with settled payments", "predictive-revenue-os"),
    ("B2B forecasting and verified commercial performance", "predictive-revenue-os"),
    ("Turn qualified opportunities into realised revenue", "predictive-revenue-os"),
)


# Additional hand-authored unrelated queries test abstention. They are not
# held out from threshold selection in this first exploratory study.
NEGATIVE_CASES: tuple[str, ...] = (
    "What is the weather forecast for London tomorrow?",
    "Best recipe for chocolate brownies",
    "Who won the tennis match yesterday?",
    "Book a restaurant table this evening",
    "Trademarking an energy drink brand in the UK",
    "Repairing a bicycle chain",
    "Museum of classical art admissions",
    "How to open a business bank account",
)


def collect_known_page_keywords(
    html_get: Callable[[str], tuple[int, str]] = _get_public_html,
) -> list[dict[str, Any]]:
    rows = []
    for spec in PRIORITY_PAGES:
        status, html = html_get(spec.url)
        page = page_record(spec, html=html, http_status=status)
        if not page["eligible_for_local_topic_review"]:
            raise ValueError("live page did not pass metadata evidence gate")
        title = str(page["title"]).split("| Empire AI")[0].strip()
        rows.append({
            "keyword": title,
            "cluster_key": spec.cluster_key,
            "intent_class": spec.intent_class,
            "product_key": spec.product_key,
            "icp_key": spec.icp_key,
            "funnel_stage": spec.funnel_stage,
            "territory_key": spec.territory_key,
            "cta_key": spec.cta_key,
            "evidence_refs": page["evidence_refs"],
            "origin": "verified_owned_page_title_not_search_demand",
        })
    return rows


def run_semantic_benchmark(
    corpus: list[dict[str, Any]],
    embedder: LocalSemanticEmbedder,
    *,
    cases: tuple[tuple[str, str], ...] = CASES,
    negative_cases: tuple[str, ...] = NEGATIVE_CASES,
    exploratory_relevance_floor: float = .42,
) -> dict[str, Any]:
    if len(cases) < 4 or len(cases) > 100:
        raise ValueError("benchmark case count out of bounds")
    if len({row["product_key"] for row in corpus}) < 2:
        raise ValueError("benchmark requires at least two product classes")
    enriched = attach_keyword_embeddings(corpus, embedder)
    query_vectors = embedder.embed([case[0] for case in cases] + list(negative_cases))
    outputs = []
    for (query, expected), vector in zip(cases, query_vectors):
        baseline = search_keyword_universe(
            corpus, query, min_score=0, top_k=len(corpus)
        )["results"]
        hybrid = search_keyword_universe(
            enriched, query, min_score=0, top_k=len(corpus),
            query_embedding=vector.values,
            embedding_model=vector.model_id,
            query_embedding_evidence_ref=vector.source_receipt,
        )["results"]
        def rank(rows):
            return next(
                (idx for idx, item in enumerate(rows, start=1)
                 if item["product_key"] == expected),
                None
            )
        sector_check = review_query_sector(query, hybrid)
        outputs.append({
            "sector_review_status": sector_check["status"],
            "sector_review_hypothesis": sector_check["suggested_sector_for_review"],
            "query": query,
            "expected_product_key": expected,
            "lexical_top_product": baseline[0]["product_key"] if baseline else None,
            "hybrid_top_product": hybrid[0]["product_key"] if hybrid else None,
            "lexical_rank": rank(baseline),
            "hybrid_rank": rank(hybrid),
            "query_vector_receipt": vector.source_receipt,
        })
    n = len(outputs)
    def metrics(name):
        positions = [row[name + "_rank"] for row in outputs]
        return {
            "top1_accuracy": round(
                sum(pos == 1 for pos in positions) / n, 4
            ),
            "mean_reciprocal_rank": round(
                sum(1 / pos if pos else 0 for pos in positions) / n, 4
            ),
        }
    # A post-hoc exploratory floor is NOT a calibrated, out-of-sample decision
    # rule. Report the mistake rather than silently forcing every input into
    # the only four available commercial sectors.
    negative_scores = []
    for query, vector in zip(negative_cases, query_vectors[len(cases):]):
        ranked = search_keyword_universe(
            enriched, query, min_score=0, top_k=1,
            query_embedding=vector.values, embedding_model=vector.model_id,
            query_embedding_evidence_ref=vector.source_receipt,
        )["results"]
        negative_scores.append({
            "query": query,
            "highest_retrieval_score": ranked[0]["retrieval_score"] if ranked else None,
            "nearest_product_key": ranked[0]["product_key"] if ranked else None,
        })
    baseline = metrics("lexical")
    hybrid = metrics("hybrid")
    return {
        "schema_version": "empire.semantic_retrieval_curated_benchmark.v1",
        "model_id": embedder.model_id,
        "model_artifact_sha256": embedder.model_sha256,
        "source": "current_owned_page_title_metadata_plus_developer_authored_query_labels",
        "evaluation_sample_count": n,
        "evaluation_labels_are_real_user_queries": False,
        "data_provenance": "owned_public_page_metadata;curated_nonproduction_probes",
        "lexical": baseline,
        "hybrid": hybrid,
        "explicit_sector_conflicts_held_for_review": sum(
            result["sector_review_status"] == "SEMANTIC_SECTOR_CONFLICT_REVIEW"
            for result in outputs
        ),
        "ambiguous_sector_queries_abstained": sum(
            result["sector_review_status"] == "ABSTAIN_MULTI_SECTOR_QUERY"
            for result in outputs
        ),
        "sector_review_reassigned_rankings": False,
        "hybrid_top1_gain": round(
            hybrid["top1_accuracy"] - baseline["top1_accuracy"], 4
        ),
        "sample_cases": outputs,
        "exploratory_abstention": {
            "relevance_floor": exploratory_relevance_floor,
            "positive_queries_at_or_above_floor": sum(
                search_keyword_universe(
                    enriched, query, min_score=0, top_k=1,
                    query_embedding=vector.values,
                    embedding_model=vector.model_id,
                    query_embedding_evidence_ref=vector.source_receipt,
                )["results"][0]["retrieval_score"] >= exploratory_relevance_floor
                for (query, _), vector in zip(cases, query_vectors[:len(cases)])
            ),
            "total_positive_queries": n,
            "negative_queries_below_floor": sum(
                score["highest_retrieval_score"] is not None and
                score["highest_retrieval_score"] < exploratory_relevance_floor
                for score in negative_scores
            ),
            "negative_query_count": len(negative_cases),
            "negative_cases": negative_scores,
            "out_of_sample_validated": False,
            "deployment_gate_passed": False,
        },
        "automatic_publication_authorized": False,
        "verified_google_ranking": False,
        "revenue_verified": False,
        "execution_authority": "none",
        "external_paid_api_calls": 0,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--local-embed-cache", required=True)
    p.add_argument("--local-embed-python", required=True)
    args = p.parse_args()
    try:
        embedder = LocalSemanticEmbedder(
            model_cache=args.local_embed_cache,
            model_loader=lambda path: IsolatedFastEmbedProcess(
                model_cache=path,
                python_executable=args.local_embed_python,
            ),
        )
        corpus = collect_known_page_keywords()
        print(json.dumps(run_semantic_benchmark(corpus, embedder),
                         indent=2, sort_keys=True))
        return 0
    except (LocalEmbeddingUnavailable, ValueError, OSError) as exc:
        print(json.dumps({
            "status": "UNAVAILABLE",
            "reason": type(exc).__name__,
        }), file=__import__("sys").stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
