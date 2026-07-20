"""grabber.py - Empire Cortex competitive intelligence grabber.

Pulls competitor + high-converting video hooks + transcripts into
hooks_transcripts.db. Self-running on cron (daily), idempotent upserts.

Primary path: yt-dlp (free, no API key) for transcript + stats.
Optional discovery: SerpAPI youtube search (degrades silently if 429/invalid).

Env: SERPAPI_KEY (optional) in /root/empire_os/.env
"""
from __future__ import annotations

import os
import sqlite3
import json
import subprocess
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


def _serp_key() -> str:
    key = os.environ.get("SERPAPI_KEY", "")
    if not key and ENV.exists():
        for line in ENV.read_text().splitlines():
            if line.strip().startswith("SERPAPI_KEY="):
                key = line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    return key


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


def _yt_dlp(video_url: str) -> dict:
    """Extract transcript + stats via yt-dlp (free)."""
    out = subprocess.run(
        ["yt-dlp", "--dump-json", "--no-warnings",
         "--skip-download", video_url],
        capture_output=True, text=True, timeout=60)
    if out.returncode != 0:
        raise RuntimeError(out.stderr[:200])
    meta = json.loads(out.stdout)
    # subtitles / auto-captions -> transcript
    trans = ""
    for lang, tracks in (meta.get("subtitles", {}) or {}).items():
        for t in tracks:
            if t.get("ext") in ("vtt", "srv3", "json3"):
                trans = _fetch_text(t["url"])
                break
        if trans:
            break
    if not trans:
        for lang, tracks in (meta.get("automatic_captions", {}) or {}).items():
            for t in tracks:
                if t.get("ext") in ("vtt", "srv3", "json3"):
                    trans = _fetch_text(t["url"])
                    break
            if trans:
                break
    return {
        "id": meta.get("id", ""),
        "title": meta.get("title", ""),
        "channel": meta.get("channel_id", ""),
        "channel_name": meta.get("channel", ""),
        "views": int(meta.get("view_count") or 0),
        "likes": int(meta.get("like_count") or 0),
        "subs": int(meta.get("channel_follower_count") or 0),
        "duration": str(meta.get("duration") or ""),
        "published": meta.get("upload_date", ""),
        "transcript": trans,
    }


def _fetch_text(url: str) -> str:
    try:
        import urllib.request, re, json
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        # json3 caption format
        if raw.strip().startswith("{"):
            try:
                obj = json.loads(raw)
                parts = []
                for ev in obj.get("events", []):
                    for seg in ev.get("segs", []):
                        t = seg.get("utf8", "")
                        if t:
                            parts.append(t)
                return " ".join(parts)[:20000]
            except Exception:
                pass
        # vtt format
        lines = [l for l in raw.splitlines()
                 if l and not l.startswith("WEBVTT") and "-->" not in l
                 and not re.match(r"^\d+$", l)]
        return " ".join(lines)[:20000]
    except Exception:
        return ""


def _conv_score(views: int, likes: int, subs: int) -> float:
    if not views:
        return 0.0
    like_rate = likes / views
    reach = (views / subs) if subs else 0.0
    return round(min(1.0, like_rate * 5 + min(reach, 3) / 3), 4)


def scrape_video(conn: sqlite3.Connection, url: str, niche: str):
    d = _yt_dlp(url)
    if not d["id"]:
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


def discover_via_serp(niche: str, limit: int = 5) -> list:
    """Optional. Returns list of video URLs. Silent on failure."""
    key = _serp_key()
    if not key:
        return []
    try:
        import urllib.request, urllib.parse
        params = {"api_key": key, "engine": "youtube",
                  "q": f"{niche} how to OR tutorial", "hl": "en"}
        u = "https://serpapi.com/search.json?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        d = json.loads(urllib.request.urlopen(req, timeout=20).read())
        urls = []
        for r in d.get("video_results", [])[:limit]:
            vid = r.get("id") or r.get("video_id") or ""
            if vid and not vid.startswith("UC"):
                urls.append(f"https://youtube.com/watch?v={vid}")
        return urls
    except Exception:
        return []


def run(niche_limit: int = 8, per_niche: int = 6) -> dict:
    from empire_os import niche_map
    conn = init_db()
    niches = list(getattr(niche_map, "VERTICALS", {}).keys())[:niche_limit]
    if not niches:
        niches = ["plumbing", "roofing", "hvac", "ai_automation", "lead_gen", "seo"]
    stats = {"niches": len(niches), "videos": 0, "errors": 0,
             "serp_used": 0}
    for nic in niches:
        urls = discover_via_serp(nic, per_niche)
        if urls:
            stats["serp_used"] += 1
        # fallbacks if serp empty: search yt-dlp via niche keyword
        if not urls:
            urls = [f"ytsearch{per_niche}:{nic} how to"]  # yt-dlp search syntax
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
