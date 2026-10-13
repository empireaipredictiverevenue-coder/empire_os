#!/usr/bin/env python3
"""Read existing buyer evidence; make one safe founder review packet."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.buyer_recovery_action_desk import (
    RecoveryDeskError, plan, save_private,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    try:
        report = plan(Path(args.repo_root))
        if args.write:
            save_private(Path(args.repo_root), report)
    except (OSError, ValueError, TypeError, RecoveryDeskError):
        print(json.dumps({
            "status": "BLOCKED", "reason": "UNSAFE_OR_CHANGING_BUYER_EVIDENCE",
            "outbound_sent": False, "execution_authority": "NONE"
        }))
        return 2
    print(json.dumps({
        "status": "PASS", "mode": "OBSERVE",
        "high_priority_total": report["high_priority_total"],
        "review_packet_count": report["review_packet_count"],
        "parked_records": report["counts"].get("parked", 0),
        "founder_review_required": True,
        "outbound_sent": False, "execution_authority": "NONE",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
