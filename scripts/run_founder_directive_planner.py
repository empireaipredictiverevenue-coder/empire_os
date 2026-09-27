#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.founder_directive_planner import plan_captured_directives

ROOT = Path("/srv/empire_os")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    args = parser.parse_args()
    result = plan_captured_directives(ROOT, limit=args.limit)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
