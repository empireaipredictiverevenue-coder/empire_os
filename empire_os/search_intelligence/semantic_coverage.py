"""Review keyword-to-owned-page topical coverage without claiming Google indexation.

Uses the existing Keyword Universe contract, hybrid similarity primitives and
Search Intelligence cannibalisation review. All inputs are pre-observed;
no crawling, publishing, database writes or network access.
"""
from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import urlsplit

from empire_os.semantic_keyword_search import (
    SemanticSearchInputError,
    _cosine, _dense, _prepare, _sparse_cosine, _terms, _tfidf, _weights,
)
from .cannibalisation import detect_cannibalisation


def _site_host(url: str, owned_domain: str) -> bool:
    try:
        parsed = urlsplit(url)
    except ValueError:
        return False
    domain = owned_domain.strip().casefold().removeprefix("www.")
    host = (parsed.hostname or "").casefold().removeprefix("www.")
    return bool(domain and host == domain and parsed.scheme in {"http", "https"})


def _page_rows(
    pages: Iterable[Mapping[str, Any]], *,
    domain: str, tenant_id: str | None = None,
) -> tuple[list[dict[str, Any]], int]:
    accepted: list[dict[str, Any]] = []
    rejected = 0
    seen: set[str] = set()
    for raw in pages:
        if not isinstance(raw, Mapping):
            raise SemanticSearchInputError("page must be a mapping")
        url = str(raw.get("canonical_url") or raw.get("url") or "").strip()
        if not _site_host(url, domain):
            raise SemanticSearchInputError("page domain outside explicitly owned site")
        if tenant_id is not None and str(raw.get("tenant_id") or "") != tenant_id:
            raise SemanticSearchInputError("page tenant does not match explicit tenant scope")
        if url in seen:
            # A duplicate inventory row must not be mistaken for two pages.
            continue
        seen.add(url)
        evidence = raw.get("evidence_refs")
        if not isinstance(evidence, (tuple, list)) or not evidence or any(
            not isinstance(ref, str) or not ref.strip() for ref in evidence
        ):
            rejected += 1
            continue
        title = str(raw.get("title") or "").strip()
        target = str(raw.get("target_query") or "").strip()
        topic = str(raw.get("topic") or "").strip()
        if not any((title, target, topic)):
            rejected += 1
            continue
        embedding = raw.get("embedding")
        if embedding is not None:
            embedding = _dense(embedding)
            model = str(raw.get("embedding_model") or "").strip()
            vector_ref = str(raw.get("embedding_evidence_ref") or "").strip()
            if not model or not vector_ref:
                raise SemanticSearchInputError("page embedding requires model and provenance")
        else:
            model = None
            vector_ref = None
        accepted.append({
            "url": url,
            "title": title,
            "text": " ".join(v for v in (title, target, topic) if v),
            "product_key": str(raw.get("product_key") or "").strip(),
            "territory_key": str(raw.get("territory_key") or "").strip() or None,
            "intent_class": str(raw.get("search_intent") or "").strip(),
            "funnel_stage": str(raw.get("funnel_stage") or "").strip(),
            "evidence_refs": list(evidence),
            "embedding": embedding,
            "embedding_model": model,
            "embedding_evidence_ref": vector_ref,
        })
    return accepted, rejected


def review_semantic_page_coverage(
    keyword_rows: Iterable[Mapping[str, Any]],
    page_rows: Iterable[Mapping[str, Any]],
    *,
    owned_domain: str,
    tenant_id: str | None = None,
    inventory_complete: bool = False,
    threshold: float = .42,
) -> dict[str, Any]:
    """Evidence-labelled candidate mapping; does NOT prove actual page content.

    A 'complete' inventory is asserted by its caller for local comparison only,
    and never means that Google has indexed all those pages.
    """
    if not isinstance(threshold, (int, float)) or isinstance(threshold, bool) or not 0 < threshold <= 1:
        raise SemanticSearchInputError("threshold must be in (0,1]")
    if not isinstance(owned_domain, str) or not owned_domain.strip():
        raise SemanticSearchInputError("explicit owned_domain required")

    keywords = _prepare(keyword_rows)
    pages, rejected_count = _page_rows(
        page_rows, domain=owned_domain, tenant_id=tenant_id,
    )
    if len(keywords) > 500 or len(pages) > 500:
        raise SemanticSearchInputError("review batches limited to 500 keywords and pages")
    terms = [_terms(item.record.keyword) for item in keywords] + [
        _terms(page["text"]) for page in pages
    ]
    idf = _weights(terms)
    keyword_sparse = [_tfidf(_terms(item.record.keyword), idf) for item in keywords]
    page_sparse = [_tfidf(_terms(page["text"]), idf) for page in pages]

    findings = []
    for i, item in enumerate(keywords):
        record = item.record
        candidate_scoped = []
        matches = []
        for j, page in enumerate(pages):
            if not (
                page["product_key"] == record.product_key
                and page["territory_key"] == record.territory_key
                and page["intent_class"] == record.intent_class
                and page["funnel_stage"] == record.funnel_stage
            ):
                continue
            candidate_scoped.append(page)
            lexical = _sparse_cosine(keyword_sparse[i], page_sparse[j])
            semantic = None
            if (item.embedding is not None and page["embedding"] is not None
                    and item.embedding_model == page["embedding_model"]):
                semantic = max(0.0, _cosine(item.embedding, page["embedding"]))
            score = lexical if semantic is None else (.65 * semantic + .35 * lexical)
            if score < threshold:
                continue
            matches.append({
                "canonical_url": page["url"],
                "title": page["title"],
                "relevance_score": round(score, 6),
                "retrieval_method": "hybrid_semantic_lexical" if semantic is not None else "lexical_tfidf",
                "keyword_evidence_refs": list(record.evidence_refs),
                "page_evidence_refs": page["evidence_refs"],
                "embedding_evidence_refs": [
                    item.embedding_evidence_ref, page["embedding_evidence_ref"]
                ] if semantic is not None else [],
                "page_content_verified": False,
                "google_indexation_proven": False,
            })
        matches.sort(key=lambda row: (-row["relevance_score"], row["canonical_url"]))
        possible_overlaps = []
        if len(matches) >= 2:
            # Reuse the canonical Search Intelligence detector.
            possible_overlaps = [
                finding.as_dict() for finding in detect_cannibalisation([
                    {
                        "canonical_url": hit["canonical_url"],
                        "target_query": record.keyword,
                        "search_intent": record.intent_class,
                        "topic": record.cluster_key,
                    }
                    for hit in matches
                ])
            ]
        status = (
            "POTENTIAL_METADATA_COVERAGE" if matches
            else "REVIEW_LOCAL_METADATA_GAP" if inventory_complete
            else "UNKNOWN_INCOMPLETE_PAGE_INVENTORY"
        )
        findings.append({
            "keyword": record.keyword,
            "keyword_evidence_refs": list(record.evidence_refs),
            "product_key": record.product_key,
            "territory_key": record.territory_key,
            "intent_class": record.intent_class,
            "eligible_page_count": len(candidate_scoped),
            "status": status,
            "candidate_pages": matches[:5],
            "possible_cannibalisation": possible_overlaps,
            "real_search_demand_verified": False,
            "actual_page_content_verified": False,
            "google_indexation_verified": False,
            "publication_authorized": False,
        })
    return {
        "schema_version": "semantic_page_coverage_review.v1",
        "mode": "OBSERVE",
        "site_domain": owned_domain,
        "tenant_scope": tenant_id,
        "local_inventory_claimed_complete": inventory_complete,
        "indexed_page_count_claimed": None,
        "evaluated_keyword_count": len(keywords),
        "evidenced_page_count": len(pages),
        "rejected_unevidenced_page_rows": rejected_count,
        "findings": findings,
        "execution_authority": "none",
        "publishing_enabled": False,
        "indexation_enabled": False,
    }
