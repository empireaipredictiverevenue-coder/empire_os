#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.master_execution_ledger import build_execution_ledger


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CHECKLIST = ROOT / "docs/MASTER_REMAINING_CHECKLIST.md"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checklist", default=str(DEFAULT_CHECKLIST))
    parser.add_argument("--output", default="")
    parser.add_argument("--pending-only", action="store_true")
    args = parser.parse_args()

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
