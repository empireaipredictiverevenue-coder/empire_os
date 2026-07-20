"""social_watcher.py — 24/7 watcher for the YouTube autopilot.

Runs social_autopilot.run_cycle on a cadence. Logs every item to
social_log.jsonl. On CRITIC_PASSED=False it SKIPS publish (never ship bad
copy) and writes the item to review_queue.json for human edit + re-render.

Usage:
  python3 social_watcher.py --interval 1800   # every 30 min
  python3 social_watcher.py --once            # single cycle (test)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os import social_autopilot as auto

LOG = Path("/root/empire_os/empire_os/social_log.jsonl")
REVIEW = Path("/root/empire_os/empire_os/review_queue.json")


def _log(result: dict) -> None:
    row = {"ts": datetime.now(timezone.utc).isoformat(), **result}
    with LOG.open("a") as f:
        f.write(json.dumps(row, default=str) + "\n")
    # critic fail -> hold for review
    if not result.get("ok") or not result.get("critic", {}).get("CRITIC_PASSED"):
        rq = []
        if REVIEW.exists():
            try:
                rq = json.loads(REVIEW.read_text())
            except Exception:
                rq = []
        rq.append({"ts": row["ts"], "niche": result.get("niche"),
                   "critic": result.get("critic"), "video": result.get("video"),
                   "status": "NEEDS_REVIEW"})
        REVIEW.write_text(json.dumps(rq, default=str, indent=2))


def tick(post: bool = True) -> dict:
    try:
        # Layer 3: gate live publish on optimal-time signal when available
        from empire_os.agents.post_schedule_optimizer import PostScheduleOptimizer
        opt = PostScheduleOptimizer()
        effective_post = post and opt.should_post_now()
        r = auto.run_cycle("youtube", post=effective_post)
        r["schedule_gate"] = opt.should_post_now()
        r["scheduled_publish"] = effective_post
    except Exception as e:
        r = {"ok": False, "error": str(e)[:200]}
    _log(r)
    flag = "OK" if r.get("ok") and r.get("critic", {}).get("CRITIC_PASSED") \
        else "REVIEW"
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {flag} "
          f"niche={r.get('niche')} track={r.get('track')} "
          f"publish={r.get('publish')} url={r.get('url')}")
    return r


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=1800,
                    help="seconds between cycles (default 1800 = 30min)")
    ap.add_argument("--once", action="store_true", help="run one cycle and exit")
    ap.add_argument("--no-post", action="store_true",
                    help="queue only, do not upload")
    a = ap.parse_args()
    post = not a.no_post
    if a.once:
        tick(post=post)
        return
    print(f"WATCHER live: every {a.interval}s, post={post}. Ctrl-C to stop.")
    while True:
        tick(post=post)
        time.sleep(a.interval)


if __name__ == "__main__":
    main()
