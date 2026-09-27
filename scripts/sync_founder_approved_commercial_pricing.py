#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.founder_approved_commercial_sync import (
    sync_founder_approved_commercial_pricing,
)


def main() -> int:
    result = sync_founder_approved_commercial_pricing()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
