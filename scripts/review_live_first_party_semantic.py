#!/usr/bin/env python3
"""Read-only GSC + owned webpage semantic intelligence (no writes/no paid APIs).

Usage, from feature worktree root:
  /srv/empire_os/.venv/bin/python -m scripts.review_live_first_party_semantic \
      --start-date 2026-10-03 --end-date 2026-10-15

Reads only existing loopback GSC endpoint 127.0.0.1:8771 and four explicitly
listed public Empire AI pages; never authenticates to unknown servers, writes
EmpireDB, deploys to production or reports estimates as measured demand.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import sys
from typing import Any, Callable, Mapping
from pathlib import Path

import requests

from empire_os.search_intelligence.first_party_semantic_corpus import (
    PRIORITY_PAGES, PROPERTY, page_record, prepare_first_party_semantic_corpus,
)
from empire_os.search_intelligence.local_embedding_runtime import (
    LocalSemanticEmbedder, LocalEmbeddingUnavailable, IsolatedFastEmbedProcess,
    attach_keyword_embeddings, attach_page_embeddings,
)
from empire_os.search_intelligence.semantic_coverage import (
    review_semantic_page_coverage,
)
from empire_os.semantic_keyword_search import SemanticSearchInputError, cluster_keyword_topics
from empire_os.search_intelligence.semantic_opportunity_review import review_semantic_opportunity
from collections import Counter


GSC_BASE = "http://127.0.0.1:8771/v1/search"
JsonGet = Callable[..., Mapping[str, Any]]
HtmlGet = Callable[..., tuple[int, str]]


def _get_json(path: str, *, params: dict | None = None) -> Mapping[str, Any]:
    if path not in {"/search-console/status", "/search-console/observations"}:
        raise SemanticSearchInputError("unknown GSC endpoint")
    r = requests.get(GSC_BASE + path, params=params, timeout=15,
                     allow_redirects=False)
    r.raise_for_status()
    body = r.json()
    if not isinstance(body, Mapping):
        raise SemanticSearchInputError("invalid GSC response")
    return body


def _get_public_html(url: str) -> tuple[int, str]:
    allowed = {s.url for s in PRIORITY_PAGES}
    if url not in allowed:
        raise SemanticSearchInputError("unapproved website route")
    r = requests.get(url, timeout=12, allow_redirects=False)
    if len(r.content) > 2_000_000:
        raise SemanticSearchInputError("HTML exceeds page size budget")
    return r.status_code, r.text


def build_live_semantic_review(
    *, start_date: str, end_date: str,
    json_get: JsonGet = _get_json,
    html_get: HtmlGet = _get_public_html,
    embedder: LocalSemanticEmbedder | None = None,
) -> dict[str, Any]:
    """Integrate only independently readable first-party sources."""
    try:
        start = date.fromisoformat(start_date)
        end = date.fromisoformat(end_date)
    except (ValueError, TypeError) as e:
        raise SemanticSearchInputError("valid ISO dates required") from e
    if end < start or (end - start).days > 31:
        raise SemanticSearchInputError("GSC time window must be 0..31 days")

    status = json_get("/search-console/status")
    if status.get("available") is not True or status.get("site_url") != PROPERTY:
        raise SemanticSearchInputError("existing first-party GSC adapter not ready")
    response = json_get(
        "/search-console/observations",
        params={
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "limit": 1000,
        },
    )
    pages = []
    failures = []
    for spec in PRIORITY_PAGES:
        try:
            http_status, html = html_get(spec.url)
            page = page_record(spec, html=html, http_status=http_status)
        except (requests.RequestException, OSError, SemanticSearchInputError) as exc:
            failures.append({
                "url": spec.url,
                "reason": type(exc).__name__,
            })
            continue
        pages.append(page)
        if not page["eligible_for_local_topic_review"]:
            failures.append({
                "url": spec.url,
                "reason": page["reason"],
            })
    corpus = prepare_first_party_semantic_corpus(
        response, pages, start_date=start.isoformat(), end_date=end.isoformat(),
    )
    keyword_rows = [
        *corpus["mapped_gsc_keywords"],
        *corpus["unmeasured_page_title_seeds"],
    ]
    # Real GSC observations and title-derived candidates must never be
    # collapsed into the same measured keyword claim.
    unique = {}
    for row in keyword_rows:
        key = row["keyword"].casefold()
        if key not in unique:
            unique[key] = row
        elif unique[key].get("source_evidence_kind") == "PAGE_TITLE_UNMEASURED":
            unique[key] = row if row.get("source_evidence_kind") == "GSC_QUERY_PAGE" else unique[key]
    unique_rows = list(unique.values())
    evidenced_pages = corpus["evidenced_page_inventory"]
    if embedder is not None:
        unique_rows = attach_keyword_embeddings(unique_rows, embedder)
        evidenced_pages = attach_page_embeddings(evidenced_pages, embedder)
    coverage = review_semantic_page_coverage(
        unique_rows, evidenced_pages,
        owned_domain="empire-ai.co.uk",
        inventory_complete=False,
    )
    clusters = cluster_keyword_topics(unique_rows, min_similarity=.72)
    # Source is the verified existing first-party GSC adapter. Distinguish a
    # query actually returned by GSC from an unmeasured page-title seed.
    gsc_opportunities = []
    for row in [*corpus["mapped_gsc_keywords"], *corpus["unmapped_gsc_query_pages"]]:
        query = row.get("keyword") or row.get("query")
        if not query:
            continue
        review = review_semantic_opportunity(
            query, source_kind="GSC_QUERY_PAGE",
            evidence_refs=row["evidence_refs"],
        )
        gsc_opportunities.append({
            "query": query,
            "target_page": row.get("page_url"),
            "evidence_refs": row["evidence_refs"],
            "intent_hypothesis": review["intent_label"],
            "review_action": review["recommended_review_action"],
            "sector_evidence_state": review["sector_review"]["status"],
            "territory_evidence_state": review["territory_review"]["geography_state"],
            "actual_buyer_verified": False,
            "actual_revenue_verified": False,
        })
    gsc_intent_counts = Counter(
        row["intent_hypothesis"] for row in gsc_opportunities
    )
    return {
        "schema_version": "live_first_party_semantic_review.v1",
        "mode": "OBSERVE",
        "window": [start.isoformat(), end.isoformat()],
        "gsc_query_page_observations": corpus["returned_query_page_rows"],
        "gsc_query_page_impressions_returned": corpus["returned_query_page_impressions"],
        "gsc_query_page_mapped_to_priority_pages": len(corpus["mapped_gsc_keywords"]),
        "gsc_query_page_unmapped": len(corpus["unmapped_gsc_query_pages"]),
        "unmeasured_page_title_keywords": len(corpus["unmeasured_page_title_seeds"]),
        "public_priority_pages_with_evidence": len(corpus["evidenced_page_inventory"]),
        "priority_page_failures": failures,
        "gsc_query_intent_reviews": gsc_opportunities,
        "gsc_intent_hypothesis_counts": dict(sorted(gsc_intent_counts.items())),
        "gsc_observed_source_is_buyer_identity": False,
        "unmapped_gsc_paths": sorted({
            row["page_url"] for row in corpus["unmapped_gsc_query_pages"]
            if row.get("page_url")
        }),
        "keyword_topic_groups": clusters["groups"],
        "embedding_status": "LOCAL_MODEL" if embedder is not None else "LEXICAL_ONLY",
        "embedding_model_id": embedder.model_id if embedder is not None else None,
        "embedding_model_sha256": embedder.model_sha256 if embedder is not None else None,
        "page_coverage": coverage["findings"],
        "real_search_volume_verified": False,
        "buyer_intent_verified": False,
        "revenue_verified": False,
        "sitewide_clicks_claimed": None,
        "action_authority": "none",
        "published_content_changed": False,
        "spend_usd": 0,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--start-date", required=True)
    p.add_argument("--end-date", required=True)
    p.add_argument("--local-embed-cache", type=Path,
                   help="Use an already cached verified local ONNX model; never download")
    p.add_argument("--local-embed-python", type=Path,
                   help="Absolute path to isolated FastEmbed venv Python (requires --local-embed-cache)")
    args = p.parse_args(argv)
    try:
        if bool(args.local_embed_cache) != bool(args.local_embed_python):
            raise LocalEmbeddingUnavailable("--local-embed-cache and --local-embed-python required together")
        encoder = (LocalSemanticEmbedder(
            model_cache=args.local_embed_cache,
            model_loader=lambda cache: IsolatedFastEmbedProcess(
                model_cache=cache, python_executable=args.local_embed_python),
        ) if args.local_embed_cache else None)
        print(json.dumps(build_live_semantic_review(
            start_date=args.start_date, end_date=args.end_date, embedder=encoder,
        ), indent=2, sort_keys=True))
        return 0
    except (ValueError, TypeError, requests.RequestException,
            SemanticSearchInputError, LocalEmbeddingUnavailable) as exc:
        print(json.dumps({
            "status": "UNAVAILABLE",
            "reason": type(exc).__name__,
            "detail": str(exc),
        }), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
