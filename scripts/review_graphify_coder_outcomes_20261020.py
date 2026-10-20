"""Read-only, real Coder job outcome evidence for Graphify rollout review.

Aggregates the canonical existing local Coder queue by status and kind,
and separately counts Graphify pre-patch observations from journal metadata.
DOES NOT join unrelated events, infer revenue, touch tasks, or create data.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from empire_os.graphify_outcome_evidence import summarize_canonical_coder_jobs

PREFIX = "GRAPHIFY_PREPATCH_USAGE "
PREPATCH_FIELDS = (
    "prepatch_attempts", "attested_prepatch_reviews", "unavailable_reviews",
    "not_indexed_target_reviews", "dependent_source_candidates",
    "zero_dependency_reviews",
)


def summarize_prepatch_journal(lines: list[str]) -> dict:
    totals = Counter()
    verdicts = Counter()
    job_kinds = Counter()
    classified = 0
    rejected = 0
    for line in lines:
        index = line.find(PREFIX)
        if index < 0:
            continue
        try:
            value = json.loads(line[index + len(PREFIX):])
        except (ValueError, TypeError):
            rejected += 1
            continue
        if (not isinstance(value, dict)
                or value.get("schema_version") != "empire.graphify.prepatch_observer.v1"
                or value.get("job_kind") not in ("PLAN", "IMPLEMENT", "VERIFY", "NEXT_COMMAND")
                or value.get("job_status") not in ("COMPLETED", "FAILED", "PENDING", "RUNNING", "DELEGATED")):
            rejected += 1
            continue
        if any(type(value.get(field)) is not int or not 0 <= value[field] <= 1_000_000
               for field in PREPATCH_FIELDS):
            rejected += 1
            continue
        # A single existing Coder worker processes one claimed job per run.
        classified += 1
        job_kinds[value["job_kind"]] += 1
        for field in PREPATCH_FIELDS:
            totals[field] += value[field]
        if (value["job_kind"] == "IMPLEMENT"
                and value["job_status"] == "COMPLETED"
                and value.get("prepatch_attempts", 0) > 0
                and value.get("same_job_result_observed") is True):
            verdict = value.get("coder_verification_verdict")
            if verdict not in ("PASS", "PASS_WITH_WARNINGS", "FAIL"):
                verdict = "UNKNOWN"
            verdicts[verdict] += 1
            if value.get("coder_reported_patch_applied") is True:
                totals["same_job_applied_reported"] += 1
    return {
        "schema_version": "empire.graphify.prepatch_real_job_evidence.v1",
        "classified_observation_receipts": classified,
        "discarded_unclassified_records": rejected,
        "job_types_with_receipts": dict(sorted(job_kinds.items())),
        "observed_prepatch_counts": {
            field: totals[field] for field in PREPATCH_FIELDS
        },
        "same_job_implementation_verdicts": dict(sorted(verdicts.items())),
        "same_job_patch_applied_reports": totals["same_job_applied_reported"],
        "original_private_job_identifiers_emitted": False,
        "causal_engineering_uplift_proven": False,
        "commercial_outcome_claimed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs-dir", type=Path, default=Path(
        "/srv/empire_os/runtime/coder/jobs"))
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--read-only", action="store_true", required=True)
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    jobs = summarize_canonical_coder_jobs(
        args.jobs_dir, as_of=now, lookback_hours=args.lookback_hours,
    )
    since = (now.timestamp() - args.lookback_hours * 3600)
    # Journal query is read only. No raw log text or private fields are
    # included in output; unclassified historic records remain unknown.
    journal = subprocess.check_output([
        "journalctl", "-u", "empire-coder-worker.service",
        "--since", f"@{int(since)}", "--no-pager", "-o", "cat",
    ], text=True, stderr=subprocess.DEVNULL, timeout=30)
    telemetry = summarize_prepatch_journal(journal.splitlines())
    print(json.dumps({
        "schema_version": "empire.graphify.coder_real_outcomes_rollup.v1",
        "mode": "OBSERVE",
        "as_of_utc": now.isoformat(),
        "canonical_job_outcomes": jobs,
        "separately_grounded_graphify_observations": telemetry,
        "cross_job_id_join_attempted": False,
        "verified_graphify_engineering_uplift": None,
        "verified_graphify_commercial_uplift": None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
