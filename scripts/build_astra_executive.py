#!/usr/bin/env python3
"""Refresh Astra Executive world-state / goal / delegation plan."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.astra_executive import refresh_astra_executive


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    payload = refresh_astra_executive(
        Path(args.repo_root).resolve()
    )
    print(json.dumps({
        "ok": True,
        "plan_id": payload["plan_id"],
        "primary_goal": payload["primary_goal"]["key"],
        "plan_step_count": payload["plan_step_count"],
        "auto_dispatch_eligible_count": payload[
            "auto_dispatch_eligible_count"
        ],
        "founder_gate_step_count": payload[
            "founder_gate_step_count"
        ],
        "execution_authority": payload["execution_authority"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
