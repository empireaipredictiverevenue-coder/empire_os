"""Evidence-aware hybrid keyword search and topical grouping for EmpireOS.

No model download, network traffic, new database, or scheduled jobs. Keyword
records retain their existing Keyword Universe provenance and intent schema.
Real semantic similarity requires caller-provided, same-model dense embeddings;
the offline fallback is explicitly labelled lexical, never passed off as AI.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from math import isfinite, log, sqrt
import re
from typing import Any, Iterable, Mapping, Sequence

from empire_os.keyword_universe import KeywordRecord, keyword_record_from_mapping


class SemanticSearchInputError(ValueError):
    """Invalid evidence, embeddings, or search parameters."""


def _terms(text: str) -> tuple[str, ...]:
    words = re.findall(r"[a-z0-9]+", text.casefold())
    result: list[str] = []
    for word in words:
        if len(word) > 5 and word.endswith("ies"):
            word = word[:-3] + "y"
        elif len(word) > 4 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
            word = word[:-1]
        result.append(word)
    return tuple(result)


def _dense(value: Any) -> tuple[float, ...]:
    if not isinstance(value, (tuple, list)) or not 2 <= len(value) <= 4096:
        raise SemanticSearchInputError("embedding must contain 2..4096 numeric dimensions")
    numbers: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (float, int)):
            raise SemanticSearchInputError("embedding contains nonnumeric or boolean value")
        number = float(item)
        if not isfinite(number):
            raise SemanticSearchInputError("embedding contains nonfinite value")
        numbers.append(number)
    if not any(numbers):
        raise SemanticSearchInputError("embedding must not be zero vector")
    return tuple(numbers)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise SemanticSearchInputError("embedding dimensions do not match")
    denom = sqrt(sum(x * x for x in a) * sum(x * x for x in b))
    if denom <= 0:
        raise SemanticSearchInputError("zero-norm embedding")
    # [-1, 1]; do not map negative similarity into positive relevance.
    return max(-1.0, min(1.0, sum(x * y for x, y in zip(a, b)) / denom))


@dataclass(frozen=True)
class _Item:
    record: KeywordRecord
    embedding: tuple[float, ...] | None
    embedding_model: str | None
    embedding_evidence_ref: str | None
    raw: Mapping[str, Any]


def _prepare(rows: Iterable[Mapping[str, Any]]) -> list[_Item]:
    result = []
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise SemanticSearchInputError("each keyword row must be a mapping")
        record = keyword_record_from_mapping(row)
        record.validate()  # existing Keyword Universe schema is canonical
        key = record.keyword.casefold()
        if key in seen:
            raise SemanticSearchInputError("duplicate keyword")
        seen.add(key)
        vector = None
        model = None
        evidence = None
        if "embedding" in row and row["embedding"] is not None:
            vector = _dense(row["embedding"])
            model = str(row.get("embedding_model") or "").strip()
            evidence = str(row.get("embedding_evidence_ref") or "").strip()
            if not model or not evidence:
                raise SemanticSearchInputError("embedding requires model and evidence reference")
        result.append(_Item(record, vector, model, evidence, row))
    return result


def _weights(
    item_terms: Sequence[tuple[str, ...]], extra_terms: tuple[str, ...] = ()
) -> dict[str, float]:
    document_count = len(item_terms)
    df = Counter(token for terms in item_terms for token in set(terms))
    # Stable, corpus-scoped IDF. Query is not a fabricated search-volume measurement.
    return {term: log((document_count + 1) / (count + 1)) + 1.0
            for term, count in df.items()} | {
        term: log((document_count + 1) / 1) + 1.0
        for term in extra_terms if term not in df
    }


def _tfidf(terms: tuple[str, ...], idf: Mapping[str, float]) -> dict[str, float]:
    counts = Counter(terms)
    return {term: float(count) * idf.get(term, 1.0)
            for term, count in counts.items()}


def _sparse_cosine(left: Mapping[str, float], right: Mapping[str, float]) -> float:
    denominator = sqrt(sum(n * n for n in left.values()) * sum(n * n for n in right.values()))
    if not denominator:
        return 0.0
    return sum(weight * right.get(term, 0.0) for term, weight in left.items()) / denominator


def _similarity(a: _Item, b: _Item, tfidf_a: Mapping[str, float],
                tfidf_b: Mapping[str, float]) -> tuple[float, str]:
    if (a.embedding is not None and b.embedding is not None
            and a.embedding_model == b.embedding_model):
        return max(0.0, _cosine(a.embedding, b.embedding)), "semantic_embedding"
    return _sparse_cosine(tfidf_a, tfidf_b), "lexical_tfidf"


def search_keyword_universe(
    rows: Iterable[Mapping[str, Any]],
    query: str,
    *,
    query_embedding: Sequence[float] | None = None,
    embedding_model: str | None = None,
    query_embedding_evidence_ref: str | None = None,
    product_key: str | None = None,
    territory_key: str | None = None,
    intent_class: str | None = None,
    top_k: int = 10,
    min_score: float = 0.05,
) -> dict[str, Any]:
    """Search only evidence-bearing Keyword Universe rows.

    A provided embedding must come with a source receipt/model identifier.
    Results without a matching embedding use lexical TF-IDF, and say so.
    Territory and commercial intent are never inferred by similarity scores.
    """
    if not isinstance(query, str) or not query.strip():
        raise SemanticSearchInputError("nonempty search query required")
    if type(top_k) is not int or not 1 <= top_k <= 100:
        raise SemanticSearchInputError("top_k must be between 1 and 100")
    if not isinstance(min_score, (int, float)) or not isfinite(float(min_score)) or not 0 <= min_score <= 1:
        raise SemanticSearchInputError("min_score must be within 0..1")

    query_vector = None
    if query_embedding is not None:
        query_vector = _dense(query_embedding)
        if not str(embedding_model or "").strip() or not str(query_embedding_evidence_ref or "").strip():
            raise SemanticSearchInputError(
                "query embedding requires model and evidence reference"
            )

    items = [
        item for item in _prepare(rows)
        if (product_key is None or item.record.product_key == product_key)
        and (territory_key is None or item.record.territory_key == territory_key)
        and (intent_class is None or item.record.intent_class == intent_class)
    ]
    document_terms = [_terms(item.record.keyword) for item in items]
    query_terms = _terms(query)
    idf = _weights(document_terms, query_terms)
    query_weights = _tfidf(query_terms, idf)
    matches = []
    for item, terms in zip(items, document_terms):
        lexical = _sparse_cosine(query_weights, _tfidf(terms, idf))
        vector_score = None
        if query_vector is not None and item.embedding is not None and item.embedding_model == embedding_model:
            vector_score = max(0.0, _cosine(query_vector, item.embedding))
        if vector_score is None:
            score = lexical
            method = "lexical_tfidf"
        else:
            score = 0.65 * vector_score + 0.35 * lexical
            method = "hybrid_semantic_lexical"
        if score < min_score:
            continue
        matches.append({
            "keyword": item.record.keyword,
            "cluster_key": item.record.cluster_key,
            "intent_class": item.record.intent_class,
            "product_key": item.record.product_key,
            "icp_key": item.record.icp_key,
            "funnel_stage": item.record.funnel_stage,
            "territory_key": item.record.territory_key,
            "asset_type": item.record.asset_type,
            "cta_key": item.record.cta_key,
            "evidence_refs": list(item.record.evidence_refs),
            "embedding_evidence_ref": item.embedding_evidence_ref if vector_score is not None else None,
            "retrieval_method": method,
            "lexical_score": round(lexical, 6),
            "embedding_score": round(vector_score, 6) if vector_score is not None else None,
            "retrieval_score": round(score, 6),
            "verified_search_volume": None,
            "verified_revenue": None,
            "publication_authorized": False,
        })
    matches.sort(key=lambda r: (-r["retrieval_score"], r["keyword"].casefold()))
    matches = matches[:top_k]
    return {
        "schema_version": "semantic_keyword_retrieval.v1",
        "mode": "OBSERVE",
        "query": query,
        "eligible_records": len(items),
        "search_mode": "HYBRID" if any(m["embedding_score"] is not None for m in matches) else "LEXICAL_ONLY",
        "model_name": embedding_model if query_vector is not None else None,
        "query_embedding_evidence_ref": query_embedding_evidence_ref if query_vector is not None else None,
        "results": matches,
        "execution_authority": "none",
        "publishing_enabled": False,
        "indexation_enabled": False,
    }


def cluster_keyword_topics(
    rows: Iterable[Mapping[str, Any]], *, min_similarity: float = 0.72
) -> dict[str, Any]:
    """Draft-only semantic topical groups with protected industry/location/intent.

    Complete-link clustering avoids transitive merges (A~B~C but A!~C).
    If embeddings are absent, grouping is lexical and explicitly labelled.
    """
    if not isinstance(min_similarity, (float, int)) or not isfinite(float(min_similarity)) or not 0 < min_similarity <= 1:
        raise SemanticSearchInputError("min_similarity must be within (0,1]")
    items = sorted(_prepare(rows), key=lambda item: item.record.keyword.casefold())
    if len(items) > 500:
        raise SemanticSearchInputError("topic grouping limited to 500 records per batch")
    terms = [_terms(item.record.keyword) for item in items]
    idf = _weights(terms)
    sparse = [_tfidf(t, idf) for t in terms]
    groups: list[list[int]] = []
    for i, item in enumerate(items):
        placed = False
        for group in groups:
            if not all((
                item.record.product_key == items[j].record.product_key
                and item.record.territory_key == items[j].record.territory_key
                and item.record.intent_class == items[j].record.intent_class
                and item.record.funnel_stage == items[j].record.funnel_stage
                and _similarity(item, items[j], sparse[i], sparse[j])[0] >= min_similarity
            ) for j in group):
                continue
            group.append(i)
            placed = True
            break
        if not placed:
            groups.append([i])
    outputs = []
    for group in groups:
        members = [items[i] for i in group]
        methods = {
            _similarity(items[i], items[j], sparse[i], sparse[j])[1]
            for pos, i in enumerate(group) for j in group[pos + 1:]
        }
        method = "semantic_embedding" if methods == {"semantic_embedding"} else "lexical_tfidf"
        outputs.append({
            "representative_keyword": members[0].record.keyword,
            "keywords": [m.record.keyword for m in members],
            "declared_cluster_keys": sorted({m.record.cluster_key for m in members}),
            "possible_content_overlap": len({m.record.cluster_key for m in members}) > 1,
            "product_key": members[0].record.product_key,
            "territory_key": members[0].record.territory_key,
            "intent_class": members[0].record.intent_class,
            "funnel_stage": members[0].record.funnel_stage,
            "method": method,
            "evidence_refs": sorted({ref for m in members for ref in m.record.evidence_refs}),
            "draft_only": True,
            "publication_authorized": False,
            "verified_demand": None,
        })
    return {
        "schema_version": "semantic_topic_groups.v1",
        "mode": "OBSERVE",
        "groups": outputs,
        "keyword_count": len(items),
        "publishing_enabled": False,
        "indexation_enabled": False,
        "execution_authority": "none",
    }
