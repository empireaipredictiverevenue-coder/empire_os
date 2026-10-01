#!/usr/bin/env python3

from __future__ import annotations

import json

from empire_os.supabase_egress_guard import run_guard


SUCCESS_STATES = {
    "healthy",
    "contained",
    "inactive_empiredb",
}


def main() -> int:
    payload = run_guard()

    print(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            default=str,
        )
    )

    state = str(payload.get("state") or "")

    return 0 if state in SUCCESS_STATES else 2


if __name__ == "__main__":
    raise SystemExit(main())
