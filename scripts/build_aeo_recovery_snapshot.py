#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from empire_os.aeo_recovery import build_aeo_recovery_census

ROOT = Path("/srv/empire_os/scripts/_aeo_pages")
OUTPUT = Path("/srv/empire_os/runtime/search_intelligence/aeo_recovery/latest.json")


def main() -> int:
    payload = build_aeo_recovery_census(ROOT)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUTPUT)
    print(json.dumps({
        key: payload[key]
        for key in (
            "asset_count", "niche_count", "metro_count",
            "unique_content_hashes", "status_counts", "risk_counts",
        )
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
