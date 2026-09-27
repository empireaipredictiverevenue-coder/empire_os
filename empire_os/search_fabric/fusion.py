"""Empire Search Fabric multi-engine fusion layer."""

from __future__ import annotations

import importlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Iterable, List, Optional
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from .decoder import canonicalise_url, decode_redirect_url
from .verification import verify_result
from .engines import (
    ENGINES,
    HEALTH,
    SearchResult,
    active_engines,
    record_rejection,
    record_success,
)

_SEARCH = importlib.import_module("empire_os.search_fabric.search")

_TRACKING_KEYS = {
    "gclid",
    "fbclid",
    "msclkid",
    "ref",
    "referrer",
    "source",
}


def _canonical_result_url(value: str) -> str:
    """Normalize URLs for cross-engine dedupe."""
    value = canonicalise_url(
        decode_redirect_url(value or "")
    )

    if not value:
        return ""

    try:
        parsed = urlparse(value)

        query = [
            (key, val)
            for key, val in parse_qsl(
                parsed.query,
                keep_blank_values=False,
            )
            if (
                not key.lower().startswith("utm_")
                and key.lower() not in _TRACKING_KEYS
            )
        ]

        path = parsed.path or "/"

        if path != "/":
            path = path.rstrip("/")

        return urlunparse(
            (
                parsed.scheme.lower(),
                parsed.netloc.lower(),
                path,
                "",
                urlencode(query),
                "",
            )
        )

    except Exception:
        return value


def _run_engine(
    engine_name: str,
    query: str,
    per_engine: int,
) -> List[SearchResult]:
    """Execute one engine through the canonical Search Fabric."""
    try:
        payload = _SEARCH.search(
            query,
            num=per_engine,
            engine=engine_name,
        )
    except Exception as exc:
        record_rejection(
            engine_name,
            f"{type(exc).__name__}: {exc}",
        )
        return []

    organic = payload.get("organic", [])

    if not organic:
        record_rejection(
            engine_name,
            payload.get("error") or "no accepted results",
        )
        return []

    record_success(engine_name)

    out: List[SearchResult] = []

    for row in organic:
        url = _canonical_result_url(
            row.get("link", "")
        )

        if not url:
            continue

        out.append(
            SearchResult(
                title=row.get("title", ""),
                url=url,
                snippet=row.get("snippet", ""),
                position=int(row.get("position") or 0),
                engine=engine_name,
                query=query,
                relevance_score=float(
                    row.get("relevance_score") or 0.0
                ),
                provenance=[engine_name],
                metadata={
                    "original_url": row.get("link", ""),
                    "source_engine": row.get(
                        "source_engine",
                        engine_name,
                    ),
                },
            )
        )

    return out


def _merge_results(
    groups: Iterable[List[SearchResult]],
) -> List[SearchResult]:
    """Merge duplicate URLs and preserve independent provenance."""
    merged: Dict[str, SearchResult] = {}

    for results in groups:
        for result in results:
            key = result.url

            if key not in merged:
                merged[key] = result
                continue

            current = merged[key]

            for source in result.provenance:
                if source not in current.provenance:
                    current.provenance.append(source)

            current.relevance_score = max(
                current.relevance_score,
                result.relevance_score,
            )

            if (
                result.position
                and (
                    not current.position
                    or result.position < current.position
                )
            ):
                current.position = result.position

            if len(result.title) > len(current.title):
                current.title = result.title

            if len(result.snippet) > len(current.snippet):
                current.snippet = result.snippet

    return list(merged.values())


def _score_consensus(result: SearchResult) -> float:
    """
    Independent-source agreement.

    One engine is evidence, not consensus.
    """
    source_count = len(set(result.provenance))

    if source_count <= 1:
        return 0.0

    return min(
        1.0,
        (source_count - 1) / 3.0,
    )


def _score_confidence(result: SearchResult) -> float:
    """
    Initial Search Fabric confidence model.

    Relevance is the primary signal. Independent-source
    corroboration raises confidence. Geo/entity verification
    will be added as separate signals next.
    """
    score = (
        result.relevance_score * 0.45
        + result.geo_score * 0.25
        + result.entity_score * 0.20
        + result.consensus_score * 0.10
    )

    return round(
        max(0.0, min(1.0, score)),
        4,
    )


def fused_search(
    query: str,
    num: int = 10,
    *,
    engines: Optional[List[str]] = None,
    per_engine: int = 15,
) -> dict:
    """
    Search eligible engines in parallel, merge, dedupe and score.

    Does not write to Hub, Supabase, prospects or qualification.
    """
    if engines is None:
        selected = [
            engine.name
            for engine in active_engines()
        ]
    else:
        selected = [
            name
            for name in engines
            if name in ENGINES
        ]

    if not selected:
        return {
            "organic": [],
            "searchParameters": {
                "q": query,
                "engines": [],
                "mode": "fusion_v1",
            },
            "error": "No eligible search engines",
        }

    engine_results: Dict[str, List[SearchResult]] = {}

    with ThreadPoolExecutor(
        max_workers=min(6, len(selected))
    ) as executor:
        futures = {
            executor.submit(
                _run_engine,
                engine_name,
                query,
                per_engine,
            ): engine_name
            for engine_name in selected
        }

        for future in as_completed(futures):
            engine_name = futures[future]

            try:
                engine_results[engine_name] = future.result()
            except Exception as exc:
                record_rejection(
                    engine_name,
                    f"fusion:{type(exc).__name__}:{exc}",
                )
                engine_results[engine_name] = []

    results = _merge_results(
        engine_results.values()
    )

    for result in results:
        verification = verify_result(
            query=query,
            title=result.title,
            snippet=result.snippet,
            url=result.url,
        )

        result.geo_score = verification["geo_score"]
        result.entity_score = verification["entity_score"]
        result.result_type = verification["result_type"]

        result.metadata["verification"] = verification

        result.consensus_score = _score_consensus(
            result
        )
        result.confidence_score = _score_confidence(
            result
        )

    results.sort(
        key=lambda row: (
            -row.confidence_score,
            -row.relevance_score,
            row.position or 9999,
        )
    )

    results = results[:max(1, num)]

    organic = []

    for position, result in enumerate(
        results,
        1,
    ):
        organic.append(
            {
                "title": result.title,
                "link": result.url,
                "snippet": result.snippet,
                "position": position,
                "relevance_score": round(
                    result.relevance_score,
                    4,
                ),
                "geo_score": round(
                    result.geo_score,
                    4,
                ),
                "entity_score": round(
                    result.entity_score,
                    4,
                ),
                "result_type": result.result_type,
                "consensus_score": round(
                    result.consensus_score,
                    4,
                ),
                "confidence_score": round(
                    result.confidence_score,
                    4,
                ),
                "provenance": result.provenance,
                "source_count": len(
                    set(result.provenance)
                ),
            }
        )

    return {
        "organic": organic,
        "searchParameters": {
            "q": query,
            "num": num,
            "engines": selected,
            "mode": "fusion_v1",
        },
        "engineHealth": {
            name: {
                "healthy": HEALTH[name].healthy,
                "queries": HEALTH[name].queries,
                "successes": HEALTH[name].successes,
                "rejected": HEALTH[name].rejected,
                "success_rate": round(
                    HEALTH[name].success_rate,
                    4,
                ),
                "last_error": HEALTH[name].last_error,
            }
            for name in selected
        },
    }
