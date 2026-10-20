"""Real Graphify Coder usage from journal count-only receipts. READ ONLY.

No customer data, private prompts, source paths or job IDs are inspected
or emitted. Unknown schema/older records stay separate from real jobs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import subprocess
from typing import Iterable

SCHEMA = "empire.graphify.live_effectiveness_review.v1"
PREFIX = "GRAPHIFY_CONTEXT_USAGE "
COUNT_FIELDS = (
    "query_attempts", "attested_queries", "stale_or_invalid_queries",
    "graph_candidate_files", "new_context_files",
    "already_in_base_context", "new_context_characters",
    "objective_code_hint_queries",
)


def summarize_graphify_usage(lines: Iterable[str]) -> dict:
    totals = {field: 0 for field in COUNT_FIELDS}
    kinds = Counter()
    statuses = Counter()
    no_context_polling_excluded = 0
    records = 0
    real_jobs = 0
    unknown_prior_schema = 0
    for original in lines:
        start = original.find(PREFIX)
        if start < 0:
            continue
        try:
            row = json.loads(original[start + len(PREFIX):])
        except (ValueError, TypeError):
            continue
        if (not isinstance(row, dict) or
                row.get("schema_version") != "empire.graphify.context_usage.v1"):
            continue
        values = {}
        for field in COUNT_FIELDS:
            n = row.get(field, 0)
            if type(n) is not int or not 0 <= n <= 1000000:
                values = {}
                break
            values[field] = n
        if not values:
            continue
        records += 1
        kind = row.get("job_kind")
        if kind not in ("plan", "implement", "verify", "PLAN", "IMPLEMENT", "VERIFY"):
            unknown_prior_schema += 1
            continue
        real_jobs += 1
        normalized = kind.lower()
        kinds[normalized] += 1
        status = row.get("status")
        if status in (
            "NOT_QUERIED", "ATTESTED_CODE_CONTEXT_READ",
            "UNAVAILABLE_ValueError", "UNAVAILABLE_OSError",
            "UNAVAILABLE_UnicodeError",
        ):
            statuses[status] += 1
        for field in COUNT_FIELDS:
            totals[field] += values[field]
    return {
        "schema_version": SCHEMA,
        "mode": "OBSERVE",
        "execution_authority": "none",
        "journal_usage_records": records,
        "real_job_records": real_jobs,
        "older_unclassified_records": unknown_prior_schema,
        "job_kinds": dict(sorted(kinds.items())),
        "graph_statuses": dict(sorted(statuses.items())),
        "graph_counts_from_real_jobs_only": totals,
        "context_use_rate": (
            round(totals["attested_queries"] / totals["query_attempts"], 4)
            if totals["query_attempts"] else None
        ),
        "context_injected_in_observed_jobs": totals["new_context_files"] > 0,
        "verified_engineering_uplift": None,
        "verified_commercial_uplift": None,
        "business_records_accessed": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--since", default="2026-10-20 10:40:00")
    args = p.parse_args()
    # The only journal values consumed are our count-only GRAPHIFY_CONTEXT_USAGE
    # records. Nothing is written to disk or sent externally.
    output = subprocess.check_output(
        ["journalctl", "-u", "empire-coder-worker.service",
         "--since", args.since, "--no-pager", "-o", "cat"],
        text=True, stderr=subprocess.DEVNULL,
        timeout=15,
    )
    print(json.dumps(summarize_graphify_usage(output.splitlines()), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
