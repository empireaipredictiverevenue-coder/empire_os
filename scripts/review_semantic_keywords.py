#!/usr/bin/env python3
"""Offline semantic review of authorised Keyword Universe records.

From the EmpireOS worktree root:
  python -m scripts.review_semantic_keywords keywords.json --query "roofing quotes"
  python -m scripts.review_semantic_keywords keywords.json --topics
  python -m scripts.review_semantic_keywords keywords.json --pages pages.json \
      --owned-domain empire-ai.co.uk

Input keyword file is {"keywords": [keyword_universe_rows...]}.
Input page file is {"pages": [owned Search Intelligence page metadata...]}.
No network, APIs, database writes, publishing or embedding downloads.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

from empire_os.search_intelligence.semantic_coverage import review_semantic_page_coverage
from empire_os.semantic_keyword_search import (
    SemanticSearchInputError,
    cluster_keyword_topics,
    search_keyword_universe,
)


def _read_json(path: Path, *, key: str) -> tuple[list, dict, str]:
    file = path.resolve(strict=True)
    if not file.is_file() or file.stat().st_size > 8_000_000:
        raise SemanticSearchInputError("local evidence file must be under 8MB")
    source = file.read_bytes()
    payload = json.loads(source)
    if not isinstance(payload, dict) or not isinstance(payload.get(key), list):
        raise SemanticSearchInputError("expected JSON object with " + key + " array")
    rows = payload[key]
    if len(rows) > 10000:
        raise SemanticSearchInputError("maximum 10000 records per review")
    return rows, payload, sha256(source).hexdigest()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("json_path", type=Path)
    modes = p.add_mutually_exclusive_group(required=True)
    modes.add_argument("--query", help="Search the Keyword Universe")
    modes.add_argument("--topics", action="store_true", help="Group topical keywords")
    modes.add_argument("--pages", type=Path, help="Compare against evidenced owned page inventory")
    p.add_argument("--product-key")
    p.add_argument("--territory-key")
    p.add_argument("--intent-class")
    p.add_argument("--top-k", type=int, default=10)
    p.add_argument("--min-similarity", type=float, default=.72)
    p.add_argument("--owned-domain", help="Required for owned page review")
    p.add_argument("--tenant-id")
    p.add_argument("--inventory-complete", action="store_true",
                   help="Caller asserts supplied local pages comprise the full inventory, not Google indexing")
    args = p.parse_args(argv)

    try:
        rows, payload, keywords_hash = _read_json(args.json_path, key="keywords")
        source_hashes = {"keywords": keywords_hash}
        if args.pages:
            if not args.owned_domain:
                raise SemanticSearchInputError("--owned-domain required for --pages")
            pages, _, page_hash = _read_json(args.pages, key="pages")
            source_hashes["pages"] = page_hash
            result = review_semantic_page_coverage(
                rows, pages, owned_domain=args.owned_domain,
                tenant_id=args.tenant_id,
                inventory_complete=args.inventory_complete,
            )
        elif args.topics:
            result = cluster_keyword_topics(rows, min_similarity=args.min_similarity)
        else:
            result = search_keyword_universe(
                rows, args.query,
                query_embedding=payload.get("query_embedding"),
                embedding_model=payload.get("embedding_model"),
                query_embedding_evidence_ref=payload.get("query_embedding_evidence_ref"),
                product_key=args.product_key,
                territory_key=args.territory_key,
                intent_class=args.intent_class,
                top_k=args.top_k,
            )
        print(json.dumps({
            "input_sha256": source_hashes["keywords"],
            "input_sha256_by_type": source_hashes,
            "source_claim": "user_supplied_unverified",
            "review": result,
        }, sort_keys=True, indent=2))
        return 0
    except (OSError, UnicodeError, ValueError, TypeError, SemanticSearchInputError) as exc:
        print(json.dumps({
            "status": "UNAVAILABLE",
            "reason": type(exc).__name__,
            "detail": str(exc),
        }), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
