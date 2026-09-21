#!/usr/bin/env python3
"""One bounded EmpireOS reliability control cycle."""
from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from empire_os.ops_healer import execute_plan
from empire_os.ops_sentinel import observe

OUTPUT = Path("/srv/empire_os/runtime/ops_control/latest.json")


def unit_state(unit: str) -> str:
    result = subprocess.run(
        ["systemctl", "is-active", unit],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )
    return (result.stdout or "").strip() or "unknown"


def main() -> int:
    mode = os.getenv("EMPIRE_OPS_HEAL_MODE", "OBSERVE").strip().upper()
    if mode not in {"OBSERVE", "GUARDED_EXECUTE"}:
        mode = "OBSERVE"

    sentinel = observe(unit_state)
    repairs = []
    if mode == "GUARDED_EXECUTE":
        repairs = execute_plan(sentinel.get("repair_plan") or [], max_actions=3)

    payload = {
        "schema_version": "empire.ops_control_cycle.v1",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "mode": mode,
        "sentinel": sentinel,
        "healer": {
            "proposed": len(sentinel.get("repair_plan") or []),
            "executed": len(repairs),
            "results": repairs,
        },
        "healthy": not any(
            row.get("severity") in {"critical", "warning"}
            for row in sentinel.get("findings") or []
        ),
        "business_blocker": next(
            (
                row.get("evidence", {}).get("highest_blocker")
                for row in sentinel.get("findings") or []
                if row.get("code") == "commercial_loop_blocked"
            ),
            None,
        ),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUTPUT)
    print(json.dumps(payload, indent=2, sort_keys=True))

    failed_repairs = [row for row in repairs if row.get("ok") is not True]
    return 2 if failed_repairs else 0


if __name__ == "__main__":
    raise SystemExit(main())
