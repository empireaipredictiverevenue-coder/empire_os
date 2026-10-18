#!/usr/bin/env python3
"""Redacted read-only pgBackRest backup readiness diagnostic for REV051.

Expected local use: sudo python3 -B -m scripts.review_rev051_pgbackrest_backup_readonly --read-only
Prints NO repo paths, database rows, credentials, backup labels, or raw logs.
Never runs pgBackRest backup, restore, expire, stanza-create or WAL switch.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
from empire_os.rev051_pgbackrest_readiness import review_pgbackrest_info


def diagnostic(*, run=subprocess.run) -> dict:
    if os.geteuid() != 0:
        return {"status": "HOLD_ROOT_LOCAL_READ_REQUIRED"}
    try:
        result = run(
            ["runuser", "-u", "postgres", "--",
             "pgbackrest", "info", "--output=json"],
            capture_output=True, check=False, timeout=20,
        )
        if result.returncode != 0:
            return {"status": "HOLD_PGBACKREST_INFO_NOT_READABLE"}
        if len(result.stdout) > 2_000_000:
            return {"status": "HOLD_OVERSIZED_BACKUP_METADATA"}
        raw = json.loads(result.stdout)
        return review_pgbackrest_info(raw)
    except (OSError, subprocess.TimeoutExpired, ValueError, TypeError):
        return {"status": "HOLD_BACKUP_METADATA_UNAVAILABLE"}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args(argv)
    if not args.read_only:
        print(json.dumps({"status": "HOLD_EXPLICIT_READ_ONLY_REQUIRED"}))
        return 2
    outcome = diagnostic()
    print(json.dumps(outcome, sort_keys=True))
    return 0 if outcome.get("status") == (
        "PG_BACKREST_RECENT_BACKUP_METADATA_VALIDATED"
    ) else 2


if __name__ == "__main__":
    raise SystemExit(main())
