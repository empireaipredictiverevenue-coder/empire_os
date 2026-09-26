#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from empire_os.daily_results import build_daily_results

ROOT = Path("/srv/empire_os")
LATEST = ROOT / "runtime" / "daily_results" / "latest.json"


def main() -> int:
    payload = build_daily_results(ROOT)
    history = (
        ROOT / "runtime" / "daily_results" / "history"
        / f"{payload['date']}.json"
    )
    for path in (LATEST, history):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        tmp.replace(path)
    print(json.dumps({
        "date": payload["date"],
        "headline": payload["headline"],
        "commercial_funnel": payload["commercial_funnel"],
        "intent_and_pain": payload["intent_and_pain"],
        "coder": payload["coder"],
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
