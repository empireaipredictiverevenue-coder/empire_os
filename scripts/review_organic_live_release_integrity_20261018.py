#!/usr/bin/env python3
"""Verify the already-running organic release without changing any file."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess

from empire_os.organic_live_release_integrity import CODE, audit_live_release

REPO = Path("/srv/empire_os")
BACKUP = Path("/home/ubuntu/empire_release_backups/organic_sector_20261018_v2")
STAGED = Path("/home/ubuntu/empire_worktrees/organic_sector_surgical_stage_20261018")
SOURCE = Path("/home/ubuntu/empire_worktrees/organic_actual_release_20261018")
OLD_SITE = Path("/srv/empire_os/apps/empire-public-site/out.organic-rollback-20261018-v2")


def review() -> dict:
    result = audit_live_release(
        repository=REPO, backup=BACKUP,
        staged_manifest=STAGED / "manifest.json",
        site=REPO / "apps/empire-public-site/out",
        rollback_site=OLD_SITE,
        released_source=SOURCE,
    )
    # Exact file verification does not imply committed source ownership or
    # verified revenue. Read Git state without mutating it.
    try:
        process = subprocess.run(
            ["git", "-C", str(REPO), "status", "--porcelain", "--", *sorted(CODE)],
            check=True, capture_output=True, text=True, timeout=10,
        )
        source_committed = process.stdout.strip() == ""
    except (OSError, subprocess.SubprocessError):
        source_committed = False
    sidecar = REPO / "runtime/astra/owned_industry_campaign_measurement_release.v1.json"
    if not sidecar.exists() and not sidecar.is_symlink():
        registration = "NO_INDUSTRY_RELEASE_FILE"
        validated = False
    else:
        registration = "RELEASE_PRESENT_REQUIRES_INDEPENDENT_VALIDATION"
        validated = None
    return result | {
        "canonical_source_commit_verified": source_committed,
        "industry_campaign_release_file_status": registration,
        "live_campaign_release_verified": validated,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--read-only", action="store_true")
    args = parser.parse_args()
    if not args.read_only:
        print(json.dumps({"status": "HOLD_READ_ONLY_FLAG_REQUIRED"}))
        return 2
    result = review()
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "LIVE_BYTES_VERIFIED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
