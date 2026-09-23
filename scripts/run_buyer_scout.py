#!/usr/bin/env python3
"""Run bounded Phase 4 Buyer Scout research."""
from __future__ import annotations

import argparse
import json

from empire_os.buyer_scout import refresh_buyer_scout
from empire_os.search_fabric.search import search


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--max-queries", type=int, default=12)
    parser.add_argument("--results-per-query", type=int, default=5)
    args = parser.parse_args()

    payload = refresh_buyer_scout(
        args.repo_root,
        search_fn=search,
        max_queries=max(1, min(args.max_queries, 25)),
        results_per_query=max(1, min(args.results_per_query, 10)),
    )
    print(json.dumps({
        "ok": True,
        "query_count": payload["query_count"],
        "observation_count": payload["observation_count"],
        "error_count": payload["error_count"],
        "outbound_sent": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
