"""Bounded manual Quora question discovery using canonical Search Fabric.

No scheduled search, Quora scraping, paid engine, automatic posting or DB writes.
A Search Fabric result is a candidate for human verification, never a lead.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json

from empire_os.search_fabric.search import search as fabric_search
from empire_os.search_intelligence.quora_intelligence import (
    QuoraEvidenceError, permitted_discovery_queries, read_topic_queue,
    review_quora_serp_snapshot,
)
from empire_os.search_intelligence.serp import (
    SearchFabricSerpAdapter, SerpSnapshotError,
)


def review_one_shot(
    seed_id: str,
    *,
    live: bool,
    query_mode: str = "precise",
    search_fn=fabric_search,
    clock=None,
) -> dict:
    current = clock or (lambda: datetime.now(timezone.utc))
    seeds = {row["item_id"]: row for row in read_topic_queue()}
    if seed_id not in seeds:
        raise QuoraEvidenceError("UNKNOWN_CURATED_TOPIC_ID")
    if query_mode not in ("precise", "broad"):
        raise QuoraEvidenceError("UNSUPPORTED_QUORA_DISCOVERY_MODE")
    queries = permitted_discovery_queries(seeds[seed_id])
    query = queries[0] if query_mode == "precise" else queries[1]
    if not live:
        return {
            "schema_version": "empire.search.quora_one_shot.v1",
            "mode": "PLAN_ONLY",
            "seed_id": seed_id,
            "source_query": query,
            "discovery_mode": query_mode,
            "search_request_performed": False,
            "verified_question_count": 0,
            "posting_authorized": False,
            "execution_authority": "NONE",
        }

    # One deliberate free/public provider query. No automatic fallback and
    # no cache write: do not mistake historical results for current demand.
    def one_provider(q: str, *, num: int, engine: str | None = None):
        if q != query or num > 3 or engine != "bing_html":
            raise QuoraEvidenceError("SEARCH_BUDGET_OR_SOURCE_SCOPE_VIOLATION")
        return search_fn(q, num=num, engine="bing_html", use_cache=False)

    adapter = SearchFabricSerpAdapter(search_fn=one_provider, clock=current)
    try:
        snapshot = adapter.snapshot(query, num=3, engine="bing_html")
        review = review_quora_serp_snapshot(
            seed_id, snapshot, now=current()
        )
        status = review["search_fabric_snapshot_state"]
        candidates = [
            {
                "question_url_candidate": row["question_url_candidate"],
                "question_title_candidate": row["question_title_candidate"],
                "source_ref": row["source_ref"],
                "intent_hypothesis": row["intent_hypothesis"],
                "quora_origin_page_verified": False,
            } for row in review["candidate_questions"]
        ]
    except (OSError, RuntimeError, ValueError, TypeError, SerpSnapshotError, QuoraEvidenceError):
        status, candidates = "SEARCH_SOURCE_HELD", []
    return {
        "schema_version": "empire.search.quora_one_shot.v1",
        "mode": "OBSERVE",
        "seed_id": seed_id,
        "source_query": query,
        "discovery_mode": query_mode,
        "search_request_performed": True,
        "source_status": status,
        "question_candidates": candidates,
        "verified_question_count": 0,
        "published_answers_verified": 0,
        "buyer_enquiries_verified": False,
        "revenue_verified": False,
        "posting_authorized": False,
        "execution_authority": "NONE",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-id", required=True)
    parser.add_argument("--one-shot-live", action="store_true")
    parser.add_argument("--broad", action="store_true",
                        help="Use a bounded industry question search instead of the exact theme")
    args = parser.parse_args()
    try:
        result = review_one_shot(
            args.seed_id, live=args.one_shot_live,
            query_mode="broad" if args.broad else "precise",
        )
    except QuoraEvidenceError:
        result = {
            "schema_version": "empire.search.quora_one_shot.v1",
            "mode": "HELD", "source_status": "UNTRUSTED_SEED",
            "search_request_performed": False,
            "posting_authorized": False, "execution_authority": "NONE",
        }
    print(json.dumps(result, sort_keys=True))
    return 0 if result["mode"] != "HELD" else 2


if __name__ == "__main__":
    raise SystemExit(main())
