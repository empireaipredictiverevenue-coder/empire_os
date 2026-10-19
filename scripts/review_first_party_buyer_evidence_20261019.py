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
    choices = parser.add_mutually_exclusive_group()
    choices.add_argument(
        "--enqueue-founder-approved-internal-review", action="store_true",
        help="Enqueue one OBSERVE-only £0 ASTRA desk-review task (no outbound)",
    )
    choices.add_argument(
        "--inspect-existing-buyer-projection", action="store_true",
        help="Bounded read of existing EmpireDB buyer projection, with masked output",
    )
    options = parser.parse_args()
    root = Path("/srv/empire_os")
    now = datetime.now(timezone.utc)
    prepared = review_one_commercial_evidence_request(root, as_of=now)
    output = {"evidence_review": prepared, "production_changes": False}
    if options.inspect_existing_buyer_projection:
        from empire_os.revenue_market_buyer_linkage import inspect_existing_buyer_projection_readonly
        from scripts.build_buyer_capacity_readiness import fetch_all_buyers
        output["existing_buyer_projection"] = inspect_existing_buyer_projection_readonly(
            root, prepared=prepared, as_of=now,
            # Existing canonical query-only projection. 10001 lets us
            # detect an oversized dataset rather than silently truncate it.
            buyer_reader=lambda: fetch_all_buyers(max_rows=10001),
        )
    if options.enqueue_founder_approved_internal_review:
        output["existing_astra_queue"] = enqueue_one_commercial_evidence_request(
            root, prepared, as_of=now,
        )
        output["production_changes"] = output["existing_astra_queue"]["created"]
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0 if prepared["status"] == "ONE_INTERNAL_EVIDENCE_REQUEST_PREPARED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
