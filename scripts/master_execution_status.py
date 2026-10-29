#!/usr/bin/env python3
"""Read-only canonical checklist and commercial-register inspection."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path

from empire_os.master_execution_ledger import build_execution_ledger


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKLIST = ROOT / "docs/MASTER_REMAINING_CHECKLIST.md"
DEFAULT_REGISTER = ROOT / "docs/handoffs/EMPIRE_MASTER_COMPLETION_REGISTER_20261028.csv"
DEFAULT_RELEASE_REGISTER = ROOT / "docs/website/release_candidates/EMPIRE_FOUNDER_ACTIVE_RELEASE_REGISTER_20261028.md"
REGISTER_FIELDS = (
    "id", "priority", "title", "audit_status", "owner", "evidence_next_action", "source",
)


def audit_commercial_register(register: Path, release_register: Path) -> dict:
    """Detect inconsistent tracking without accepting a file as independent live proof."""
    with register.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != REGISTER_FIELDS:
            raise ValueError("commercial_register_schema_mismatch")
        rows = list(reader)
    if any(None in row or any(not str(row.get(k) or "").strip() for k in REGISTER_FIELDS)
           for row in rows):
        raise ValueError("commercial_register_incomplete_row")
    by_id = {row["id"]: row for row in rows}
    if len(by_id) != len(rows):
        raise ValueError("commercial_register_duplicate_task_id")
    release_bytes = release_register.read_bytes()
    release_text = release_bytes.decode("utf-8")
    owner_claim = (
        "Original 707→746 website release is LIVE." in release_text
        and "Scoped public HTTPS verification PASS 49/49" in release_text
        and "746/746" in release_text
    )
    conflicts = []
    if owner_claim:
        for key in ("P1-03", "P1-04"):
            row = by_id.get(key)
            if row is None:
                conflicts.append({"task_id": key, "reason": "tracked_release_item_missing"})
            elif row["audit_status"] != "LIVE":
                conflicts.append({"task_id": key, "reason": "recorded_live_release_still_open"})
    return {
        "schema_version": "empire.master-commercial-register-audit.v1",
        "mode": "OBSERVE",
        "execution_authority": "none",
        "commercial_execution_performed": False,
        "register_sha256": sha256(register.read_bytes()).hexdigest(),
        "release_register_sha256": sha256(release_bytes).hexdigest(),
        "row_count": len(rows),
        "status_counts": dict(sorted(Counter(row["audit_status"] for row in rows).items())),
        "owner_release_claim_present": owner_claim,
        "owner_release_claim_independently_verified_by_this_command": False,
        "tracker_conflicts": conflicts,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checklist", default=str(DEFAULT_CHECKLIST))
    parser.add_argument("--output", default="")
    parser.add_argument("--pending-only", action="store_true")
    parser.add_argument("--audit-commercial-register", action="store_true")
    parser.add_argument("--commercial-register", default=str(DEFAULT_REGISTER))
    parser.add_argument("--release-register", default=str(DEFAULT_RELEASE_REGISTER))
    args = parser.parse_args()

    if args.audit_commercial_register:
        # This optional audit never writes a file or dispatches a task.
        if args.output:
            parser.error("--output is unavailable with --audit-commercial-register")
        print(json.dumps(
            audit_commercial_register(
                Path(args.commercial_register), Path(args.release_register)
            ), indent=2, sort_keys=True,
        ))
        return 0

    ledger = build_execution_ledger(Path(args.checklist))
    if args.pending_only:
        ledger["items"] = [
            item
            for item in ledger["items"]
            if item["status"] == "PENDING"
        ]

    payload = json.dumps(ledger, indent=2, sort_keys=True)
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload + "\n", encoding="utf-8")
        print(json.dumps({
            "schema_version": "empire.master-execution-ledger-run.v1",
            "output": str(output),
            "total": ledger["summary"]["total"],
            "done": ledger["summary"]["done"],
            "pending": ledger["summary"]["pending"],
            "execution_authority": "none",
        }, sort_keys=True))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
