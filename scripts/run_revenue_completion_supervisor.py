#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.revenue_completion_supervisor import build_snapshot, write_snapshot


def main() -> int:
    payload = build_snapshot()
    path = write_snapshot(payload=payload)
    print(json.dumps({
        "ok": True,
        "path": str(path),
        "tam_state": payload["tam"]["state"],
        "genuine_review_ready_count": (
            payload["buyers"]["genuine_review_ready_count"]
        ),
        "next_action": payload["next_action"],
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
