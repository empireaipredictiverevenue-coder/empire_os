#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.solar_economics_apply import apply_all_solar_economics


def main() -> int:
    result = apply_all_solar_economics()
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["error_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
