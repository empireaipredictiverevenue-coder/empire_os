#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from empire_os.predictive_cloud_status import (
    refresh_predictive_cloud_status,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", default="/srv/empire_os")
    args = parser.parse_args()

    payload = refresh_predictive_cloud_status(
        Path(args.repo_root).resolve()
    )
    tag = (
        payload.get("components", {}).get("tag_intelligence", {})
    )
    print(json.dumps({
        "ok": True,
        "schema_version": payload.get("schema_version"),
        "generated_at": payload.get("generated_at"),
        "available_component_count": payload.get(
            "available_component_count"
        ),
        "tag_intelligence_available": tag.get("available"),
        "tag_intelligence_freshness": tag.get("freshness"),
        "execution_authority": payload.get(
            "execution_authority", "none"
        ),
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
