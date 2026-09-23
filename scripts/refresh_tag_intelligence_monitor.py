#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json

from empire_os.tag_intelligence_monitor import (
    refresh_tag_intelligence_monitor,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    payload = refresh_tag_intelligence_monitor(args.repo_root)
    print(json.dumps({
        "ok": True,
        "target_count": payload["target_count"],
        "available_target_count": payload["available_target_count"],
        "failed_target_count": payload["failed_target_count"],
        "critical_issue_count": payload["critical_issue_count"],
        "high_issue_count": payload["high_issue_count"],
        "critical_change_count": payload["critical_change_count"],
        "automatic_tag_mutation": False,
        "execution_authority": "none",
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
