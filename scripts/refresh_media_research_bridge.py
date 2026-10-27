#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.media_research_bridge import (
    refresh_media_research_bridge,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    parser.add_argument("--preview", action="store_true",
                        help="Validate the current research inputs without writing the queue")
    parser.add_argument("--no-source-refresh", action="store_true",
                        help="Only use already cached, fresh Last30Days exports")
    args = parser.parse_args()

    payload = refresh_media_research_bridge(
        Path(args.repo_root).resolve(),
        preview=args.preview, enable_last30days_fetch=not args.no_source_refresh,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
