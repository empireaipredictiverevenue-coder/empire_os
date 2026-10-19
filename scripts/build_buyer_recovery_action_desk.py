#!/usr/bin/env python3
"""Read existing buyer evidence; make one safe founder review packet."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.materialize_scout_network_review_20261019 import (
    make_review, persist, EvidenceHeld, QualityHold, HandoffHold,
)

from empire_os.buyer_recovery_action_desk import (
    RecoveryDeskError, plan, save_private,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    root = Path(args.repo_root)
    scout_refresh = "READ_ONLY_PREVIEW"
    if args.write:
        try:
            source_review, hashes = make_review(root, now=datetime.now(timezone.utc))
            persist(root, source_review, hashes)
            scout_refresh = "SOURCE_LINKED_SCOUT_REVIEW_REFRESHED"
        except (EvidenceHeld, QualityHold, HandoffHold, OSError, ValueError,
                TypeError, KeyError, UnicodeError):
            # The extra Scout source is optional. Preserve canonical Desk work
            # even during concurrent Scout/Buyer Network snapshot changes.
            scout_refresh = "SCOUT_REVIEW_REFRESH_HELD"
    try:
        report = plan(root)
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
        "scout_source_refresh": scout_refresh,
        "scout_research_review_status": report["scout_network_research_review"]["status"],
        "scout_research_task_count": report["scout_network_research_review"]["review_task_count"],
        "founder_review_required": True,
        "outbound_sent": False, "execution_authority": "NONE",
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
