#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.buyer_acquisition_scout import refresh_buyer_scout
from empire_os.supabase_egress_guard import supabase_egress_contained
from scripts.run_buyer_acquisition_scout import (
    _local_opportunity_seed_records,
)


def run_local_recovery(repo_root: str | Path) -> dict:
    root = Path(repo_root).resolve()
    guard_path = root / "runtime/control/supabase_egress_guard.json"

    if not supabase_egress_contained(guard_path):
        return {
            "ok": True,
            "state": "IDLE_GUARD_HEALTHY",
            "contained": False,
            "candidate_count": 0,
            "database_write_performed": False,
            "outbound_sent": False,
            "execution_authority": "none",
        }

    seeds = _local_opportunity_seed_records(root)
    if not seeds:
        return {
            "ok": True,
            "state": "CONTAINED_NO_RECOVERY_SEEDS",
            "contained": True,
            "candidate_count": 0,
            "database_write_performed": False,
            "outbound_sent": False,
            "execution_authority": "none",
        }

    payload = refresh_buyer_scout(
        root,
        max_queries=4,
        results_per_query=1,
        max_domains=20,
        max_probes=12,
        canonical_seed_records=seeds,
        search_enabled=False,
    )

    if payload.get("database_write_performed") is not False:
        raise RuntimeError("local recovery attempted database write")
    if payload.get("outbound_sent") is not False:
        raise RuntimeError("local recovery attempted outbound")
    if payload.get("execution_authority") != "none":
        raise RuntimeError("local recovery expanded execution authority")

    return {
        "ok": True,
        "state": "LOCAL_RECOVERY_EXECUTED",
        "contained": True,
        "seed_count": len(seeds),
        "candidate_count": int(payload.get("candidate_count") or 0),
        "opportunity_seed_domain_count": int(
            payload.get("opportunity_seed_domain_count") or 0
        ),
        "probe_failure_counts": dict(
            payload.get("probe_failure_counts") or {}
        ),
        "database_write_performed": False,
        "outbound_sent": False,
        "execution_authority": "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    payload = run_local_recovery(args.repo_root)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
