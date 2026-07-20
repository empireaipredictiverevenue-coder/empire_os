"""
social_youtube.py — YouTube Data API v3 publishing adapter for Empire OS.

Creds (in /root/.empire_secrets/social.env):
  YOUTUBE_CLIENT_ID, YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN
Plus the YouTube Data API v3 enabled on the Google Cloud project.

Flow to get refresh token (one-time, operator does this):
  1. Create OAuth client (Desktop) in Google Cloud, enable YouTube Data API v3
  2. Run: python3 -c "from empire_os.social_youtube import get_auth_url; print(get_auth_url())"
  3. Open URL, authorize, copy code
  4. python3 -c "from empire_os.social_youtube import exchange; print(exchange('CODE'))"
  5. Paste printed refresh token into social.env

publish_youtube(item, secrets) -> posts item['video'] if creds present,
  else returns draft_only (engine keeps it queued).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

SECRETS_ENV = Path("/root/.empire_secrets/social.env")
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _load_secrets() -> dict:
    env = {}
    if SECRETS_ENV.exists():
        for line in SECRETS_ENV.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def get_auth_url(client_id: str = "", client_secret: str = "") -> str:
    """Return the OAuth consent URL (operator opens this to get a code)."""
    from google_auth_oauthlib.flow import Flow
    if not client_id or not client_secret:
        s = _load_secrets()
        client_id = client_id or s.get("YOUTUBE_CLIENT_ID", "")
        client_secret = client_secret or s.get("YOUTUBE_CLIENT_SECRET", "")
    if not client_id:
        return "ERROR: set YOUTUBE_CLIENT_ID + YOUTUBE_CLIENT_SECRET in social.env first"
    flow = Flow.from_client_config(
        {"installed": {"client_id": client_id,
                       "client_secret": client_secret,
                       "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
                       "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                       "token_uri": "https://oauth2.googleapis.com/token"}},
        scopes=SCOPES)
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
    return flow.authorization_url(prompt="consent")[0]


def exchange(code: str) -> str:
    """Exchange an auth code for a refresh token. Print + return it."""
    from google_auth_oauthlib.flow import Flow
    s = _load_secrets()
    flow = Flow.from_client_config(
        {"installed": {"client_id": s.get("YOUTUBE_CLIENT_ID", ""),
                       "client_secret": s.get("YOUTUBE_CLIENT_SECRET", ""),
                       "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob"],
                       "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                       "token_uri": "https://oauth2.googleapis.com/token"}},
        scopes=SCOPES)
    flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
    flow.fetch_token(code=code)
    rt = flow.credentials.refresh_token
    return f"Add this to social.env:\nYOUTUBE_REFRESH_TOKEN={rt}"


def _build_creds(secrets: dict):
    from google.oauth2.credentials import Credentials
    return Credentials(
        None,
        refresh_token=secrets.get("YOUTUBE_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=secrets.get("YOUTUBE_CLIENT_ID"),
        client_secret=secrets.get("YOUTUBE_CLIENT_SECRET"),
    )


def publish_youtube(item: dict, secrets: dict | None = None) -> dict:
    """Upload item['video'] to YouTube. Live only if all creds present."""
    secrets = secrets or _load_secrets()
    need = ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    missing = [k for k in need if not secrets.get(k)]
    if missing:
        return {"ok": False, "status": "draft_only",
                "reason": f"missing YouTube creds: {missing}",
                "note": "video queued; run get_auth_url + exchange to go live"}
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        creds = _build_creds(secrets)
        yt = build("youtube", "v3", credentials=creds)
        script = item.get("script", {})
        body = {
            "snippet": {
                "title": script.get("title", item.get("topic", "Empire OS"))[:100],
                "description": (script.get("cta", "")
                                + "\n\n" + " ".join(script.get("hashtags", []))),
                "tags": [h.lstrip("#") for h in script.get("hashtags", [])][:10],
                "categoryId": "28",  # Science & Technology
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(item["video"], chunksize=-1, resumable=True,
                                mimetype="video/mp4")
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = req.execute()
        return {"ok": True, "status": "published",
                "video_id": resp["id"],
                "url": f"https://youtu.be/{resp['id']}"}
    except Exception as e:
        return {"ok": False, "status": "error", "error": str(e)[:300]}
