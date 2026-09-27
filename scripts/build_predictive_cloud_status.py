#!/usr/bin/env python3
"""Refresh canonical Predictive Cloud status snapshot."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.predictive_cloud_status import refresh_predictive_cloud_status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    payload = refresh_predictive_cloud_status(
        Path(args.repo_root).resolve()
    )
    print(json.dumps({
        "ok": True,
        "component_count": payload["component_count"],
        "available_component_count": payload[
            "available_component_count"
        ],
        "unavailable_components": payload["unavailable_components"],
        "stale_components": payload["stale_components"],
        "unknown_freshness_components": payload[
            "unknown_freshness_components"
        ],
        "execution_authority": payload["execution_authority"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
