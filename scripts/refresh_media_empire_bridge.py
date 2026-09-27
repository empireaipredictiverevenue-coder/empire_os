#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.media_empire_bridge import (
    refresh_media_empire_bridge,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--git-limit", type=int, default=30)
    args = parser.parse_args()

    payload = refresh_media_empire_bridge(
        Path(args.repo_root).resolve(),
        git_limit=args.git_limit,
    )

    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
