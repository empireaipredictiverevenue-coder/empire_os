"""trend_sentiment_monitor.py - Empire Cortex Layer 2.

Real-time trend + sentiment signal for the social autopilot.

Design (honest, no fabricated data):
- Trend source: Google Trends RSS (no API key) for the verticals we serve.
  If the network is unavailable, we fall back to a local trend cache file
  (trend_cache.json) that the operator can populate, and ultimately to the
  static weighted rotation in social_autopilot._WEIGHTS.
- Sentiment: we do not scrape live comments (no platform creds). Instead we
  track sentiment of OUR OWN published copy via the social_log.jsonl
  reviewer flags (CRITIC_PASSED / NEEDS_REVIEW) as a proxy for "did this copy
  land". That is real, locally-available signal.

Public API:
  TrendSentimentMonitor.trending_niches() -> dict[niche, score]
  TrendSentimentMonitor.sentiment_for(niche) -> float  # 0..1, 1 = clean
"""

from __future__ import annotations

import json
import socket
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys_path = "/root/empire_os"
import sys
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)

from empire_os import social_autopilot as auto

# Hard global network cap so the monitor can never block the autopilot.
socket.setdefaulttimeout(5)

CACHE = Path("/root/empire_os/empire_os/agents/trend_cache.json")
SOCIAL_LOG = Path("/root/empire_os/empire_os/social_log.jsonl")

# Vertical -> a Google Trends RSS query we can poll for free
_TREND_QUERIES = {
    "plumbing": "plumbing leads",
    "roofing": "roofing marketing",
    "hvac": "hvac automation",
    "water_damage": "water damage restoration",
    "towing": "towing business",
    "electrical": "electrical contractor leads",
    "storm_damage": "storm damage claims",
    "mold_remediation": "mold remediation",
    "cybersecurity": "cybersecurity for business",
    "ai_automation": "AI automation agency",
    "lead_gen": "lead generation",
    "seo": "local SEO",
    "disaster_restoration": "disaster restoration",
    "legal_mass_tort": "mass tort leads",
}


def _fetch_trend_score(query: str) -> float | None:
    """Pull the latest 'trending' flag from Google Trends RSS (no key).

    Returns a 0..1 score or None on any failure (offline, blocked, etc).
    """
    url = ("https://trends.google.com/trends/trendingsearches/daily/rss"
           "?geo=US")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=8) as r:
            body = r.read().decode("utf-8", "ignore")
    except Exception:
        return None
    # crude signal: is our query (or a token of it) mentioned in the feed?
    q = query.lower()
    hits = sum(1 for token in q.split() if token in body.lower())
    if not hits:
        return 0.0
    return min(1.0, hits / max(1, len(q.split())))


class TrendSentimentMonitor:
    def __init__(self) -> None:
        self._cache = self._load_cache()

    def _load_cache(self) -> dict:
        if CACHE.exists():
            try:
                return json.loads(CACHE.read_text())
            except Exception:
                return {}
        return {}

    def _save_cache(self, data: dict) -> None:
        try:
            CACHE.write_text(json.dumps(data, indent=2, default=str))
        except Exception:
            pass

    def trending_niches(self) -> dict:
        """Return {niche: 0..1 trend_score} across served verticals.

        Live-polls Google Trends RSS; falls back to cached scores; falls back
        to empty dict (caller uses static weights).
        """
        scores: dict[str, float] = {}
        for niche, query in _TREND_QUERIES.items():
            live = _fetch_trend_score(query)
            if live is None:
                live = self._cache.get(niche, {}).get("score", 0.0)
            scores[niche] = round(live, 3)
        # cache for offline fallback
        self._cache = {n: {"score": s, "ts": datetime.now(timezone.utc).isoformat()}
                       for n, s in scores.items()}
        self._save_cache(self._cache)
        # only return niches with a real (non-zero) signal
        return {n: s for n, s in scores.items() if s > 0}

    def sentiment_for(self, niche: str) -> float:
        """Proxy sentiment from our own publish log.

        1.0 = always passed critic (clean copy). 0.0 = always held for review.
        No log / no entries -> neutral 0.5.
        """
        if not SOCIAL_LOG.exists():
            return 0.5
        ok = bad = 0
        try:
            for line in SOCIAL_LOG.read_text().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except Exception:
                    continue
                if row.get("niche") != niche:
                    continue
                if row.get("flag") == "OK":
                    ok += 1
                elif row.get("flag") == "REVIEW":
                    bad += 1
        except Exception:
            return 0.5
        if ok + bad == 0:
            return 0.5
        return round(ok / (ok + bad), 3)

    def boosted_pick(self) -> dict:
        """Return a cortex_pick_niche() dict, biased by cached trend signal.

        Uses the CACHED trend scores (populated by trending_niches / a cron)
        so the autopilot cycle never blocks on network. Live refresh happens
        out-of-band via `trending_niches()` or the cronjob, not per-post.
        """
        base = auto.cortex_pick_niche()
        cache = self._load_cache()
        trends = {n: d.get("score", 0.0) for n, d in cache.items() if n in auto._WEIGHTS}
        served = [n for n in trends if trends[n] > 0.3]
        if served:
            best = max(served, key=lambda n: trends[n])
            sec = auto._load_secrets()
            is_local = best in auto.LOCAL_TRACK
            phone = (sec.get("VONAGE_NUMBER_B") if is_local
                     else sec.get("VONAGE_NUMBER_A", ""))
            return {"niche": best, "is_local": is_local,
                    "phone": phone,
                    "track": "local-services" if is_local else "automation",
                    "per_lead_cents": getattr(auto.niche_map,
                                              "TIER_PER_LEAD_CENTS",
                                              {}).get("gold", 9900),
                    "trend_score": trends[best]}
        return base


if __name__ == "__main__":
    mon = TrendSentimentMonitor()
    print("TRENDING:", json.dumps(mon.trending_niches(), indent=2))
    print("PICK:", json.dumps(mon.boosted_pick(), indent=2, default=str))
