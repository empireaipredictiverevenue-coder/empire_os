#!/usr/bin/env python3
"""Build the canonical OBSERVE-only Revenue Pulse snapshot."""
from __future__ import annotations

import json
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from empire_os.qualification_worker_v2 import request_json
from empire_os.revenue_pulse import StormPulse, build_revenue_pulse
from empire_os.revenue_pulse_reader import fetch_current_and_previous_windows


ROOT = Path("/srv/empire_os")
OUT = ROOT / "runtime" / "revenue_pulse" / "latest.json"


def reader(path: str, params: dict[str, str]) -> Any:
    query = urllib.parse.urlencode(params)
    return request_json("GET", f"{path}?{query}")


def load_commercial_blocker() -> tuple[str | None, str | None]:
    path = ROOT / "runtime" / "commercial_loop" / "latest.json"
    if not path.exists():
        return None, None
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None, None
    return (
        data.get("highest_priority_blocker"),
        data.get("blocker_state"),
    )


def load_storm_pulse() -> StormPulse | None:
    root = ROOT / "runtime" / "revenue_strike"
    if not root.exists():
        return None
    paths = sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not paths:
        return None
    try:
        data = json.loads(paths[-1].read_text())
    except Exception:
        return None

    prospects = data.get("prospects")
    trigger = data.get("trigger")
    if not isinstance(prospects, list) or not isinstance(trigger, dict):
        return None
    source = str(trigger.get("source_url") or "").strip()
    if not source:
        return None
    return StormPulse(
        opportunity_count=len(prospects),
        max_multiplier=(
            float(trigger["modeled_multiplier"])
            if trigger.get("modeled_multiplier") is not None
            else None
        ),
        priority_boost_max=(
            float(trigger["priority_boost"])
            if trigger.get("priority_boost") is not None
            else None
        ),
        evidence_refs=(source,),
    )


def main() -> int:
    now = datetime.now(timezone.utc)
    current, previous = fetch_current_and_previous_windows(
        reader,
        now=now,
        hours=24,
    )
    blocker, blocker_state = load_commercial_blocker()
    pulse = build_revenue_pulse(
        current=current,
        previous=previous,
        highest_priority_blocker=blocker,
        blocker_state=blocker_state,
        storm=load_storm_pulse(),
    )
    pulse["generated_at"] = now.isoformat()
    pulse["snapshot_source"] = "canonical_supabase_rest"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(pulse, indent=2, sort_keys=True) + "\n")
    tmp.replace(OUT)

    print(json.dumps({
        "ok": True,
        "path": str(OUT),
        "pulse_state": pulse["pulse_state"],
        "blocker": pulse["highest_priority_blocker"],
        "recognized_revenue_cents": (
            pulse["recognized_revenue_truth"]["recognized_revenue_cents"]
        ),
        "realized_gp_cents": (
            pulse["recognized_revenue_truth"]["realized_gp_cents"]
        ),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
