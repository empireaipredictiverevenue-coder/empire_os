#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from empire_os.control_fabric_snapshot import build_control_fabric_snapshot

OUT = Path("/srv/empire_os/runtime/control_fabric/latest.json")


def main() -> int:
    payload = build_control_fabric_snapshot()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUT)
    print(json.dumps({
        "ok": True,
        "path": str(OUT),
        "component_count": payload["component_count"],
        "authority_counts": payload["authority_counts"],
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
