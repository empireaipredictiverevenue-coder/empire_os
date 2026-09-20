#!/usr/bin/env python3
from __future__ import annotations

import json

from empire_os.astra_dispatcher import dispatch


def main() -> int:
    result = dispatch()
    print(json.dumps(result, indent=2, sort_keys=True))
    failed = any(
        row.get("decision") == "DISPATCHED"
        and row.get("returncode") not in (0, None)
        for row in result.get("executions", [])
    )
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
