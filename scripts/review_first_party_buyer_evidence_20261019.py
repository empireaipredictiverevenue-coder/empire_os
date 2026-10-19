#!/usr/bin/env python3
"""Review one real Opportunity Factory buyer-evidence gap in OBSERVE mode.

Default is read-only; the exact founder-approved flag below writes ONE
zero-cost internal task into the EXISTING ASTRA queue. It never polls Gmail,
creates CRM leads, estimates conversion or executes commercial actions.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from empire_os.revenue_buyer_evidence_handoff import (
    enqueue_one_commercial_evidence_request,
    review_one_commercial_evidence_request,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="First-party buyer evidence path")
    parser.add_argument(
        "--enqueue-founder-approved-internal-review", action="store_true",
        help="Enqueue one OBSERVE-only £0 ASTRA desk-review task (no outbound)",
    )
    options = parser.parse_args()
    root = Path("/srv/empire_os")
    now = datetime.now(timezone.utc)
    prepared = review_one_commercial_evidence_request(root, as_of=now)
    output = {"evidence_review": prepared, "production_changes": False}
    if options.enqueue_founder_approved_internal_review:
        output["existing_astra_queue"] = enqueue_one_commercial_evidence_request(
            root, prepared, as_of=now,
        )
        output["production_changes"] = output["existing_astra_queue"]["created"]
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if prepared["status"] == "ONE_INTERNAL_EVIDENCE_REQUEST_PREPARED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
