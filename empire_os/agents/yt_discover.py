"""yt_discover.py - YouTube Data API v3 discovery (official, no cookie wall).

Uses our existing Desktop OAuth client (refresh token in social.env).
Searches videos per niche, returns watch URLs.
No browser login needed - refresh token builds credentials.
"""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path("/root/empire_os")
ENV = ROOT / ".env"
SOCIAL_ENV = Path("/root/.empire_secrets/social.env")


def _load() -> dict:
    d = {}
    for p in (SOCIAL_ENV, ENV):
        if p.exists():
            for line in p.read_text().splitlines():
                if line.strip().startswith(("YOUTUBE_", "YOUTUBE_")) or \
                   line.strip().startswith("YOUTUBE_"):
                    k, _, v = line.strip().partition("=")
                    d[k.strip()] = v.strip().strip('"').strip("'")
    return d


def get_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    c = _load()
    creds = Credentials(
        token=None,
        refresh_token=c.get("YOUTUBE_REFRESH_TOKEN"),
        client_id=c.get("YOUTUBE_CLIENT_ID"),
        client_secret=c.get("YOUTUBE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("youtube", "v3", credentials=creds, cache_discovery=False)


def search(niche: str, limit: int = 6) -> list:
    """Return list of video URLs for a niche query."""
    try:
        yt = get_service()
        resp = yt.search().list(
            part="snippet", q=f"{niche} how to OR tutorial OR automation",
            type="video", order="viewCount", maxResults=limit,
            safeSearch="none",
        ).execute()
        urls = []
        for it in resp.get("items", []):
            vid = it.get("id", {}).get("videoId", "")
            if vid:
                urls.append(f"https://youtube.com/watch?v={vid}")
        return urls
    except Exception as e:
        print(f"[yt_discover] search fail {niche}: {e}")
        return []


def fetch_video(video_id: str) -> dict:
    """Return stats + transcript for one video via YT Data API (official)."""
    try:
        yt = get_service()
        resp = yt.videos().list(
            part="snippet,statistics,contentDetails",
            id=video_id,
        ).execute()
        items = resp.get("items", [])
        if not items:
            return {}
        it = items[0]
        sn = it.get("snippet", {})
        st = it.get("statistics", {})
        dur = it.get("contentDetails", {}).get("duration", "")
        # captions: YT Data API only allows DOWNLOAD of OWN videos.
        # Competitor caption download returns 403 -> skip (title is the hook).
        trans = ""
        try:
            caps = yt.captions().list(part="snippet", videoId=video_id).execute()
            trans = f"[captions_available:{len(caps.get('items', []))}]"
        except Exception:
            trans = ""
        return {
            "id": video_id,
            "title": sn.get("title", ""),
            "channel": sn.get("channelId", ""),
            "channel_name": sn.get("channelTitle", ""),
            "views": int(st.get("viewCount", 0) or 0),
            "likes": int(st.get("likeCount", 0) or 0),
            "subs": 0,  # not in videos.list; filled from channel if needed
            "duration": dur,
            "published": sn.get("publishedAt", ""),
            "transcript": trans,
        }
    except Exception as e:
        print(f"[yt_discover] fetch_video fail {video_id}: {e}")
        return {}


if __name__ == "__main__":
    import json
    print(json.dumps(search("plumbing", 3), indent=2))
