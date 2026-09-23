#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.buyer_acquisition_scout import refresh_buyer_scout


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--max-queries", type=int, default=20)
    parser.add_argument("--results-per-query", type=int, default=8)
    parser.add_argument("--max-domains", type=int, default=40)
    parser.add_argument("--max-probes", type=int, default=20)
    args = parser.parse_args()

    payload = refresh_buyer_scout(
        args.repo_root,
        max_queries=args.max_queries,
        results_per_query=args.results_per_query,
        max_domains=args.max_domains,
        max_probes=args.max_probes,
    )
    print(json.dumps({
        "ok": True,
        "query_count": payload["query_count"],
        "domain_count": payload["domain_count"],
        "candidate_count": payload["candidate_count"],
        "explicit_direct_buyer_candidate_count": payload[
            "explicit_direct_buyer_candidate_count"
        ],
        "database_write_performed": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
