"""grabber.py - Empire Cortex competitive intelligence grabber.

Pulls competitor + high-converting video hooks + transcripts into
hooks_transcripts.db. Self-running on cron (daily), idempotent upserts.

Path: 100% official YouTube Data API v3 (our OAuth client, no cookie wall).
Discovery + stats via API. Transcripts of competitor videos are NOT
downloadable via API (403) — title/hook + view/like stats are the core
signal. For transcripts, provide cookies.txt + re-enable yt-dlp fallback.
"""

from __future__ import annotations

import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/root/empire_os")
ENV = ROOT / ".env"
DB = ROOT / "empire_os" / "hooks_transcripts.db"
sys_path = str(ROOT)
import sys
if sys_path not in sys.path:
    sys.path.insert(0, sys_path)



def init_db() -> sqlite3.Connection:
    c = sqlite3.connect(DB)
    c.executescript("""
        CREATE TABLE IF NOT EXISTS channels (
            id TEXT PRIMARY KEY, name TEXT, niche TEXT,
            subs INTEGER, avg_views REAL, scraped_at TEXT);
        CREATE TABLE IF NOT EXISTS videos (
            id TEXT PRIMARY KEY, channel TEXT, channel_name TEXT, niche TEXT,
            title TEXT, hook TEXT, transcript TEXT,
            views INTEGER, likes INTEGER, subs INTEGER, duration TEXT,
            published TEXT, fetched_at TEXT, converted_score REAL);
        CREATE INDEX IF NOT EXISTS idx_videos_niche ON videos(niche);
        CREATE INDEX IF NOT EXISTS idx_videos_conv ON videos(converted_score DESC);
    """)
    return c


def scrape_video(conn: sqlite3.Connection, url: str, niche: str):
    vid = url.split("v=")[-1].split("&")[0] if "v=" in url else url
    d = fetch_video(vid)
    if not d.get("id"):
        return
    hook = d["title"].split("|")[0].strip()
    score = _conv_score(d["views"], d["likes"], d["subs"])
    conn.execute(
        "INSERT OR REPLACE INTO videos"
        "(id,channel,channel_name,niche,title,hook,transcript,views,likes,"
        "subs,duration,published,fetched_at,converted_score) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (d["id"], d["channel"], d["channel_name"], niche, d["title"], hook,
         d["transcript"][:20000], d["views"], d["likes"], d["subs"],
         d["duration"], d["published"],
         datetime.now(timezone.utc).isoformat(), score))
    if d["channel"]:
        conn.execute(
            "INSERT OR IGNORE INTO channels(id,name,niche,subs,avg_views,scraped_at)"
            " VALUES(?,?,?,?,?,?)",
            (d["channel"], d["channel_name"], niche, d["subs"], 0.0,
             datetime.now(timezone.utc).isoformat()))
    conn.commit()


def fetch_video(video_id: str) -> dict:
    from empire_os.agents.yt_discover import fetch_video as _fv
    return _fv(video_id)


def discover(niche: str, limit: int = 6) -> list:
    """Discover top video URLs via YouTube Data API v3 (our OAuth)."""
    try:
        from empire_os.agents.yt_discover import search as yt_search
        return yt_search(niche, limit)
    except Exception as e:
        print(f"[grabber] discover fail {niche}: {e}")
        return []


def _conv_score(views: int, likes: int, subs: int) -> float:
    if not views:
        return 0.0
    like_rate = likes / views
    reach = (views / subs) if subs else 0.0
    return round(min(1.0, like_rate * 5 + min(reach, 3) / 3), 4)


def run(niche_limit: int = 8, per_niche: int = 6) -> dict:
    from empire_os import niche_map
    conn = init_db()
    niches = list(getattr(niche_map, "VERTICALS", {}).keys())[:niche_limit]
    if not niches:
        niches = ["plumbing", "roofing", "hvac", "ai_automation", "lead_gen", "seo"]
    stats = {"niches": len(niches), "videos": 0, "errors": 0,
             "ytapi_used": 0}
    for nic in niches:
        urls = discover(nic, per_niche)
        if urls:
            stats["ytapi_used"] += 1
        for u in urls[:per_niche]:
            try:
                scrape_video(conn, u, nic)
                stats["videos"] += 1
            except Exception:
                stats["errors"] += 1
            time.sleep(1.5)
    conn.close()
    return stats


if __name__ == "__main__":
    print(json.dumps(run(), indent=2))
