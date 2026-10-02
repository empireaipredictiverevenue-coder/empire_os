#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.coder.plan_delegation import (
    delegate_oversized_plans,
    reconcile_delegated_plans,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument(
        "--phase",
        choices=("delegate", "reconcile", "both"),
        default="both",
    )
    parser.add_argument("--max-jobs", type=int, default=3)
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    payload: dict[str, object] = {
        "schema_version": "empire.coder.plan-delegation-cycle.v1",
        "execution_authority": "none",
    }
    if args.phase in {"reconcile", "both"}:
        payload["reconciliation"] = reconcile_delegated_plans(root)
    if args.phase in {"delegate", "both"}:
        payload["delegation"] = delegate_oversized_plans(
            root,
            max_jobs=max(0, min(int(args.max_jobs), 10)),
        )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
