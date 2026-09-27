#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.supabase_egress_guard import run_guard


def main() -> int:
    result = run_guard()
    print(json.dumps(result, indent=2, sort_keys=True))
    # Containment is an expected protected state, not a systemd failure.
    return 0 if result.get("state") in {"healthy", "contained"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
