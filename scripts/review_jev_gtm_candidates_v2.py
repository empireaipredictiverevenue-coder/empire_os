"""Read-only, local JSON intake for tenant-scoped JEV GTM review.

No DB connection, network request, email send, scheduler, or file mutation.
Supply data already fetched from an authorised canonical reader.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import sys

from empire_os.jev_gtm_v2 import build_jev_gtm_review_queue


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="JEV GTM V2 zero-write review")
    parser.add_argument("--input", required=True, help="Local JSON file with a cases list")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--as-of", required=True, help="Timezone-aware ISO-8601 timestamp")
    parser.add_argument("--limit", type=int, default=250)
    parser.add_argument("--include-items", action="store_true", help="Print evidence-bearing items")
    args = parser.parse_args(argv)
    try:
        path = Path(args.input)
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 10_000_000:
            raise ValueError("input file unavailable, symlinked or oversized")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("cases"), list):
            raise ValueError("input must contain a cases list")
        as_of = datetime.fromisoformat(args.as_of.replace("Z", "+00:00"))
        queue = build_jev_gtm_review_queue(
            tenant_id=args.tenant_id,
            cases=data["cases"],
            as_of=as_of,
            max_candidates=args.limit,
        )
        # JSON on disk cannot attest canonical tenant bindings, contact
        # clearance, or reply provenance, regardless of embedded booleans.
        # Do not let an arbitrary export pretend to be a verified sales queue.
        for item in queue["items"]:
            if item["action"] not in {"HOLD", "EVIDENCE_REVIEW", "RESEARCH_REQUIRED"}:
                item["unverified_preview_action"] = item["action"]
                item["action"] = "EVIDENCE_REVIEW"
                item["reason"] = "local_export_origin_not_authenticated"
            if "local_export_origin_not_authenticated" not in item["blockers"]:
                item["blockers"].append("local_export_origin_not_authenticated")
            item["contact_permission_granted"] = False
            item["outbound_approved"] = False
        queue["action_counts"] = {
            action: sum(item["action"] == action for item in queue["items"])
            for action in queue["action_counts"]
        }
        queue["input_origin_authenticated"] = False
        queue["promotion_eligible"] = False
        if not args.include_items:
            queue.pop("items")
        print(json.dumps(queue, sort_keys=True, separators=(",", ":"), default=str))
        return 0
    except (ValueError, TypeError, OSError, json.JSONDecodeError):
        print(json.dumps({
            "schema_version": "empire.jev.gtm_review_queue.v2",
            "status": "HELD_INVALID_OR_UNTRUSTED_INPUT",
            "read_only": True,
            "execution_authority": "none",
        }))
        return 2


if __name__ == "__main__":
    sys.exit(main())
