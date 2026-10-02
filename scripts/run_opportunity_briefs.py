#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.opportunity_brief import (
    materialize_opportunity_briefs,
    write_opportunity_briefs,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    source_path = (
        root
        / "runtime/competitive_intelligence/"
        "competitor_account_briefs_latest.json"
    )
    source = json.loads(source_path.read_text(encoding="utf-8"))
    payload = materialize_opportunity_briefs(source)
    paths = write_opportunity_briefs(root, payload)
    print(json.dumps({
        "ok": True,
        "brief_count": payload["brief_count"],
        "review_ready_count": payload["review_ready_count"],
        "paths": [str(path) for path in paths],
        "external_send_allowed": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
