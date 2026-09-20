#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from empire_os.conversion_runtime import build_live_conversion_review

LATEST = Path("/srv/empire_os/runtime/conversion/latest.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-sample-size", type=int, default=20)
    args = parser.parse_args()

    payload = build_live_conversion_review(
        min_sample_size=args.min_sample_size,
    )
    payload["observed_at"] = datetime.now(timezone.utc).isoformat()
    payload["mode"] = "OBSERVE"
    payload["owner"] = "conversion_intelligence"
    LATEST.parent.mkdir(parents=True, exist_ok=True)
    tmp = LATEST.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    tmp.replace(LATEST)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
