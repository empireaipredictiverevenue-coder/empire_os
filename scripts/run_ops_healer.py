#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.ops_healer import execute_plan

SENTINEL = Path("/srv/empire_os/runtime/ops_sentinel/latest.json")
OUTPUT = Path("/srv/empire_os/runtime/ops_healer/latest.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("OBSERVE", "GUARDED_EXECUTE"), default="OBSERVE")
    parser.add_argument("--max-actions", type=int, default=3)
    args = parser.parse_args()

    try:
        sentinel = json.loads(SENTINEL.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        sentinel = {}
    plan = sentinel.get("repair_plan") if isinstance(sentinel, dict) else []
    plan = plan if isinstance(plan, list) else []

    results = []
    if args.mode == "GUARDED_EXECUTE":
        results = execute_plan(plan, max_actions=args.max_actions)

    payload = {
        "schema_version": "empire.ops_healer.v1",
        "mode": args.mode,
        "proposed": len(plan),
        "executed": len(results),
        "results": results,
        "prohibited": [
            "fund_movement",
            "payment_confirmation",
            "revenue_recognition",
            "commercial_terms_acceptance",
            "schema_or_data_destruction",
            "authority_expansion",
            "arbitrary_shell",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUTPUT)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if all(row.get("ok") for row in results) else (2 if results else 0)


if __name__ == "__main__":
    raise SystemExit(main())
