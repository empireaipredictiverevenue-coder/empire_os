#!/usr/bin/env python3
"""Hermes North-mini reader — print latest North-mini outputs on demand.

Usage:
  python3 /root/empire_os/scripts/north_mini_read.py          # latest of each
  python3 /root/empire_os/scripts/north_mini_read.py growth   # latest growth_plan
  python3 /root/empire_os/scripts/north_mini_read.py product  # latest product_design
  python3 /root/empire_os/scripts/north_mini_read.py mgmt     # latest management
  python3 /root/empire_os/scripts/north_mini_read.py agi      # latest agi_intel
  python3 /root/empire_os/scripts/north_mini_read.py proj     # latest projection
  python3 /root/empire_os/scripts/north_mini_read.py actions  # last 10 actions
"""
import json
import sys
from pathlib import Path

FEED = Path("/root/feedback")
PLANS = FEED / "north_mini_plans.jsonl"
ACTS = FEED / "north_mini_actions.jsonl"

KIND_MAP = {
    "growth": "growth_plan", "product": "product_design",
    "mgmt": "management", "agi": "agi_intel", "proj": "projection",
}


def latest(kind=None, n=1):
    if not PLANS.exists():
        return []
    out = []
    for ln in reversed(PLANS.read_text().splitlines()):
        if not ln.strip():
            continue
        try:
            d = json.loads(ln)
        except Exception:
            continue
        if d.get("skipped"):
            continue
        if kind and d.get("type") != kind:
            continue
        out.append(d)
        if len(out) >= n:
            break
    return out


def main():
    arg = (sys.argv[1] if len(sys.argv) > 1 else "").lower()
    if arg in ("actions", "log"):
        if not ACTS.exists():
            print("(no actions yet)")
            return
        lines = [l for l in ACTS.read_text().splitlines() if l.strip()][-10:]
        for l in lines:
            try:
                print(json.dumps(json.loads(l), indent=1)[:400])
            except Exception:
                print(l[:300])
        return
    kind = KIND_MAP.get(arg)
    recs = latest(kind, n=1)
    if not recs:
        print(f"(no {kind or 'plans'} yet — North-mini may be rate-limited)")
        return
    for r in recs:
        print(f"=== {r.get('type')} @ {r.get('ts')} (model {r.get('model')}) ===")
        print(json.dumps(r.get("doc", {}), indent=2)[:1500])
        sig = r.get("state_sig")
        if sig:
            print(f"  state: {sig}")


if __name__ == "__main__":
    main()
