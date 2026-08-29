#!/usr/bin/env python3
"""Real YouTube upload via Data API v3 with refresh-token OAuth."""
import os, json, time, subprocess, sys
from pathlib import Path
import requests

ENV_FILE = Path("/root/.empire_secrets/social.env")

def _load_env():
    env = {}
    for line in ENV_FILE.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def get_access_token():
    env = _load_env()
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id": env["YOUTUBE_CLIENT_ID"],
        "client_secret": env["YOUTUBE_CLIENT_SECRET"],
        "refresh_token": env["YOUTUBE_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]

def initiate_resumable_upload(video_path, title, description, tags, privacy, token):
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Upload-Content-Type": "video/*",
        "Content-Length": "0",
    }
    body = {
        "snippet": {"title": title, "description": description, "tags": tags, "categoryId": "22"},
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    r = requests.post(
        "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status",
        headers=headers, json=body, timeout=30,
    )
    r.raise_for_status()
    return r.headers["Location"]

def upload_bytes(upload_url, video_path, token):
    size = Path(video_path).stat().st_size
    with open(video_path, "rb") as f:
        data = f.read()
    r = requests.put(upload_url, headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "video/*",
        "Content-Length": str(size),
    }, data=data, timeout=1800)
    r.raise_for_status()
    return r.json()

def delete_video(video_id, token=None):
    """Delete a YouTube video by ID. (Quota for the original insert is NOT recovered.)"""
    if not token:
        token = get_access_token()
    r = requests.delete(
        f"https://www.googleapis.com/youtube/v3/videos?id={video_id}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )
    return r.status_code in (204, 200)

def set_thumbnail(video_id, image_path, token=None):
    """Upload a custom thumbnail for a video. Returns True on success."""
    if not token:
        token = get_access_token()
    try:
        with open(image_path, "rb") as f:
            r = requests.post(
                f"https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId={video_id}",
                headers={"Authorization": f"Bearer {token}"},
                files={"image": ("thumb.png", f, "image/png")},
                timeout=60,
            )
        return r.status_code in (200, 201, 204)
    except Exception as e:
        print(f"⚠️ set_thumbnail failed: {e}")
        return False

def upload_video(video_path, title, description, tags=None, privacy=None, thumbnail_path=None):
    if tags is None:
        tags = ["EmpireAI", "RevenueIntelligence", "B2BSaaS", "AIautomation"]
    if privacy is None:
        privacy = _load_env().get("YOUTUBE_DEFAULT_PRIVACY", "unlisted")
    token = get_access_token()
    upload_url = initiate_resumable_upload(video_path, title, description, tags, privacy, token)
    result = upload_bytes(upload_url, video_path, token)
    vid = result.get("id")
    if vid and thumbnail_path and Path(thumbnail_path).exists():
        set_thumbnail(vid, thumbnail_path, token)
    return vid, result.get("status", {}).get("uploadStatus")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("usage: youtube_uploader.py <video> <title> <description>")
        sys.exit(1)
    vid, title, desc = sys.argv[1], sys.argv[2], sys.argv[3]
    youtube_id, status = upload_video(vid, title, desc)
    print(json.dumps({"youtube_id": youtube_id, "upload_status": status, "url": f"https://youtu.be/{youtube_id}"}))
