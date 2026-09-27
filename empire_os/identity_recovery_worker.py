"""Isolated entrypoint for bounded buyer identity recovery."""
from __future__ import annotations

import json
import sys

from empire_os.identity_recovery import recover_identity


def main() -> int:
    payload = json.loads(sys.stdin.read() or "{}")
    result = recover_identity(
        business_name=str(payload.get("business_name") or "").strip(),
        website=str(payload.get("website") or "").strip(),
        metro=str(payload.get("metro") or "").strip(),
    )
    print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
