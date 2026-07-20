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
SCOPES = ["https://www.googleapis.com/auth/youtube.upload",
           "https://www.googleapis.com/auth/youtube.readonly"]


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
    """Return the OAuth consent URL (operator opens this to get a code).

    Uses the plain client_secret flow (NO PKCE) so the returned code can be
    exchanged server-side without a code_verifier.
    """
    if not client_id or not client_secret:
        s = _load_secrets()
        client_id = client_id or s.get("YOUTUBE_CLIENT_ID", "")
        client_secret = client_secret or s.get("YOUTUBE_CLIENT_SECRET", "")
    if not client_id:
        return "ERROR: set YOUTUBE_CLIENT_ID + YOUTUBE_CLIENT_SECRET in social.env first"
    from urllib.parse import urlencode
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        "scope": " ".join(SCOPES),
        "prompt": "consent",
        "access_type": "offline",
    }
    return "https://accounts.google.com/o/oauth2/auth?" + urlencode(params)


def exchange(code: str) -> str:
    """Exchange an auth code for a refresh token. Print + return it."""
    import requests
    s = _load_secrets()
    data = {
        "code": code,
        "client_id": s.get("YOUTUBE_CLIENT_ID", ""),
        "client_secret": s.get("YOUTUBE_CLIENT_SECRET", ""),
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        "grant_type": "authorization_code",
    }
    r = requests.post("https://oauth2.googleapis.com/token", data=data, timeout=30)
    j = r.json()
    rt = j.get("refresh_token")
    if not rt:
        return f"ERROR no refresh_token: {j}"
    return f"Add this to social.env:\nYOUTUBE_REFRESH_TOKEN={rt}"


def exchange_and_save(code: str) -> dict:
    """Exchange code AND write refresh token into social.env automatically."""
    import requests
    s = _load_secrets()
    data = {
        "code": code,
        "client_id": s.get("YOUTUBE_CLIENT_ID", ""),
        "client_secret": s.get("YOUTUBE_CLIENT_SECRET", ""),
        "redirect_uri": "urn:ietf:wg:oauth:2.0:oob",
        "grant_type": "authorization_code",
    }
    r = requests.post("https://oauth2.googleapis.com/token", data=data, timeout=30)
    j = r.json()
    rt = j.get("refresh_token")
    if not rt:
        return {"ok": False, "error": f"no refresh_token in response: {j}"}
    lines = SECRETS_ENV.read_text().splitlines() if SECRETS_ENV.exists() else []
    kept = [ln for ln in lines if not ln.strip().startswith("YOUTUBE_REFRESH_TOKEN=")]
    kept.append(f"YOUTUBE_REFRESH_TOKEN={rt}")
    SECRETS_ENV.write_text("\n".join(kept) + "\n")
    os.chmod(SECRETS_ENV, 0o600)
    return {"ok": True, "saved": str(SECRETS_ENV), "refresh_token_len": len(rt)}


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
    """Upload item['video'] to YouTube. Live only if all creds present.

    Guard-rail: defaults to PRIVATE (YOUTUBE_DEFAULT_PRIVACY env, else
    'private'). Set YOUTUBE_DEFAULT_PRIVACY=public only after review.
    """
    secrets = secrets or _load_secrets()
    need = ["YOUTUBE_CLIENT_ID", "YOUTUBE_CLIENT_SECRET", "YOUTUBE_REFRESH_TOKEN"]
    missing = [k for k in need if not secrets.get(k)]
    if missing:
        return {"ok": False, "status": "draft_only",
                "reason": f"missing YouTube creds: {missing}",
                "note": "video queued; run get_auth_url + exchange to go live"}
    privacy = secrets.get("YOUTUBE_DEFAULT_PRIVACY", "private").lower()
    if privacy not in ("public", "private", "unlisted"):
        privacy = "private"
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
            "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
        }
        media = MediaFileUpload(item["video"], chunksize=-1, resumable=True,
                                mimetype="video/mp4")
        req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = req.execute()
        video_id = resp["id"]
        # attach custom thumbnail if rendered
        thumb_path = item.get("thumbnail")
        if thumb_path and Path(thumb_path).exists():
            try:
                yt.thumbnails().set(
                    videoId=video_id,
                    media_body=MediaFileUpload(thumb_path, mimetype="image/jpeg")
                ).execute()
            except Exception as te:
                # thumbnail is best-effort; don't fail the upload
                print(f"[youtube] thumbnail set failed: {te}")
        return {"ok": True, "status": "published", "privacy": privacy,
                "video_id": video_id,
                "url": f"https://youtu.be/{video_id}"}
    except Exception as e:
        return {"ok": False, "status": "error", "error": str(e)[:300]}
