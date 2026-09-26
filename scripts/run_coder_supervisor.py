#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from empire_os.coder_supervisor import run_coder_supervisor

ROOT = Path("/srv/empire_os")


def main() -> int:
    result = run_coder_supervisor(ROOT)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
