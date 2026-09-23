#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.solar_economics_readiness import (
    refresh_economics_snapshot,
)


def main() -> int:
    payload = refresh_economics_snapshot()
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
