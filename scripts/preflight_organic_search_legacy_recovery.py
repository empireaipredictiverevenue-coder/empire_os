#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.organic_search_legacy_recovery import build_recovery_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("/srv/empire_os"))
    parser.add_argument(
        "--twenty-plugin",
        type=Path,
        default=Path("/home/ubuntu/.hermes/hermes-agent/plugin-catalog/twenty-crm.yaml"),
    )
    args = parser.parse_args()

    result = build_recovery_manifest(
        args.root,
        twenty_plugin_path=args.twenty_plugin,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
