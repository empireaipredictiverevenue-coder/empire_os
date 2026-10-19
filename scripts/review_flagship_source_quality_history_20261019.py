#!/usr/bin/env python3
"""One explicit feature-branch baseline from four existing public-only adapters.

No paid API, CRM/EmpireDB write, source polling, customer contact,
upstream model or third-party data export. Writes ONLY to the owner
feature worktree's private, hash-linked aggregate JSONL when requested.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.flagship_source_quality_history import (
    PATH, append_quality_observation, from_canonical_stream_review,
    review_quality_history,
)
from empire_os.revenue_stream_mining import build_revenue_stream_mining

WORKTREE_NAME = "predictive_decision_control_20261018"


def main() -> int:
    parser = argparse.ArgumentParser(description="Scientific longitudinal source quality")
    parser.add_argument(
        "--capture-feature-baseline", action="store_true",
        help="Record one real aggregate observation only in this feature worktree",
    )
    options = parser.parse_args()
    worktree = Path(__file__).resolve().parents[1]
    now = datetime.now(timezone.utc)
    if worktree.name != WORKTREE_NAME:
        parser.error("refusing to capture outside the isolated feature worktree")
    target = worktree / PATH
    report = build_revenue_stream_mining(Path("/srv/empire_os"), as_of=now)
    observation = from_canonical_stream_review(report, as_of=now)
    outcome = {
        "schema_version": "empire.flagship_scientific_observation_operator.v1",
        "mode": "OBSERVE",
        "real_canonical_source_review_status": report["status"],
        "record_source_universe": observation["source_universe"],
        "source_adapter_count": observation["source_count"],
        "status_counts": observation["source_quality_categories"],
        "source_data_origin": "EXISTING_CANONICAL_READ_ONLY_RUNTIME",
        "baseline_destination": "ISOLATED_FEATURE_WORKTREE_PRIVATE_JOURNAL",
        "production_database_writes": False,
        "remote_analytics_exported": False,
        "evidently_statistical_test_performed": False,
        "execution_authority": "none",
    }
    if options.capture_feature_baseline:
        outcome["observation_receipt"] = append_quality_observation(
            target, observation, apply=True,
        )
    else:
        outcome["observation_receipt"] = append_quality_observation(
            target, observation, apply=False,
        )
    outcome["history_review"] = review_quality_history(target, as_of=now)
    print(json.dumps(outcome, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
