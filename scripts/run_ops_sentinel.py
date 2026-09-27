#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from empire_os.ops_sentinel import observe

OUTPUT = Path("/srv/empire_os/runtime/ops_sentinel/latest.json")


def unit_state(unit: str) -> str:
    result = subprocess.run(
        ["systemctl", "is-active", unit],
        capture_output=True, text=True, check=False, timeout=10,
    )
    return (result.stdout or "").strip() or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("OBSERVE", "GUARDED_EXECUTE"), default="OBSERVE")
    args = parser.parse_args()

    payload = observe(unit_state)
    payload["mode"] = args.mode
    # v1 intentionally emits the repair plan only. Execution is added through
    # an explicit allowlisted healer adapter, never raw shell from the sentinel.
    payload["repairs_executed"] = []
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUTPUT)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
