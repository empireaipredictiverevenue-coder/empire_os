#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.official_license_identity import refresh_texas_tdlr_ac_cache


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()
    path = (
        Path(args.repo_root).resolve()
        / "runtime/license_identity/texas_tdlr_ac_contractors.json"
    )
    result = refresh_texas_tdlr_ac_cache(
        cache_path=path,
        timeout=max(5.0, min(float(args.timeout), 60.0)),
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
