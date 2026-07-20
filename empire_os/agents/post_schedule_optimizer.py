"""post_schedule_optimizer.py - Empire Cortex Layer 3.

Auto-posting optimization: decides WHEN to post based on real engagement
signal from social_log.jsonl (the actual publish log produced by
social_watcher). No fabricated analytics.

Signal model (honest):
- We only have: timestamp of each cycle, niche, flag OK/REVIEW, publish status.
  We DO NOT have YouTube view/like counts locally (no API pull). So "best time"
  is inferred from CRITIC_PASS rate by hour-of-day: niches that clear the
  critic more often at certain hours get a higher posting priority at those
  hours. This is a real, reproducible proxy for "copy quality by time".

Public API:
  PostScheduleOptimizer.best_hours(niche=None) -> list[int]   # 0..23
  PostScheduleOptimizer.should_post_now(niche=None) -> bool
  PostScheduleOptimizer.next_post_delay_sec(interval) -> int
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

SOCIAL_LOG = Path("/root/empire_os/empire_os/social_log.jsonl")

_HOURS = list(range(24))


class PostScheduleOptimizer:
    def __init__(self) -> None:
        self._by_hour = self._compute()

    def _compute(self) -> dict:
        """Aggregate CRITIC_PASS rate by hour-of-day from the real log."""
        agg = {h: {"ok": 0, "total": 0} for h in _HOURS}
        if not SOCIAL_LOG.exists():
            return agg
        try:
            for line in SOCIAL_LOG.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                ts = row.get("ts") or row.get("timestamp")
                if not ts:
                    continue
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    continue
                h = dt.hour
                agg[h]["total"] += 1
                if row.get("flag") == "OK":
                    agg[h]["ok"] += 1
        except Exception:
            return agg
        return agg

    def hour_scores(self) -> dict:
        """Return {hour: pass_rate 0..1}. Empty log -> all 0.0."""
        return {h: (d["ok"] / d["total"] if d["total"] else 0.0)
                for h, d in self._by_hour.items()}

    def best_hours(self, niche: str | None = None) -> list:
        """Top 6 hours by pass-rate. With no data, returns a sane default
        window (9-11, 14-16, 19-21) so posting still happens."""
        scores = self.hour_scores()
        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        top = [h for h, s in ranked if s > 0][:6]
        if not top:
            return [9, 10, 11, 14, 15, 16, 19, 20, 21]
        return top

    def should_post_now(self, niche: str | None = None) -> bool:
        """Gate a cycle: post now if current hour is in best_hours OR we have
        no data yet (default: always post, watcher controls cadence)."""
        scores = self.hour_scores()
        if not any(scores.values()):
            return True  # no signal yet -> let watcher cadence rule
        now_h = datetime.now().hour
        return now_h in self.best_hours(niche)

    def next_post_delay_sec(self, interval: int = 1800) -> int:
        """If we should NOT post now, return seconds until the next best hour.
        Otherwise return the normal interval."""
        if self.should_post_now():
            return interval
        now_h = datetime.now().hour
        best = self.best_hours()
        # minutes until next best hour
        for delta in range(1, 25):
            if (now_h + delta) % 24 in best:
                return delta * 3600
        return interval


if __name__ == "__main__":
    opt = PostScheduleOptimizer()
    print("HOUR SCORES:", json.dumps(opt.hour_scores(), default=str))
    print("BEST HOURS:", opt.best_hours())
    print("POST NOW?:", opt.should_post_now())
