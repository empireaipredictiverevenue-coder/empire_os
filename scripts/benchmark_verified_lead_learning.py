"""Explicit, read-only scientific comparison using canonical Economic Memory."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from empire_os.lead_shadow_calibration_benchmark import refresh_shadow_calibration_snapshot


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--tenant-id", default=None)
    args = parser.parse_args()
    report = refresh_shadow_calibration_snapshot(
        args.repo_root,
        tenant_id=args.tenant_id,
        as_of=datetime.now(timezone.utc),
    )
    print(json.dumps({
        "status": "PASS" if report["evaluation_ready"] else "INSUFFICIENT_EVIDENCE",
        "verified_review_count": report["verified_review_count"],
        "temporal_holdout_count": report["temporal_holdout_count"],
        "blockers": report["blockers"],
        "model_weight_mutation": False,
        "outbound_authorized": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
