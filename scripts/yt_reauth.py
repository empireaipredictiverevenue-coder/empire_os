#!/usr/bin/env python3
"""Re-authorize YouTube OAuth with full scope (incl. youtube.force-ssl).

Thumbnail.set + videos.delete require youtube.force-ssl, which the existing
refresh token lacks. This script walks the user through a one-time consent
and writes the new refresh token into /root/.empire_secrets/social.env.

Usage:
  python3 /root/empire_os/scripts/yt_reauth.py
  1) open the printed URL in a browser, grant access
  2) copy the ?code=... value (or the whole redirect URL) and paste it back
"""
import re
import sys
import requests
from pathlib import Path

ENV = Path("/root/.empire_secrets/social.env")
SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.readonly",
]
# out-of-band redirect works for Desktop OAuth clients; if your GCP client
# only allows a specific URI, pass it as the first arg.
REDIRECT = sys.argv[1] if len(sys.argv) > 1 else "urn:ietf:wg:oauth:2.0:oob"


def read_env():
    env = {}
    for line in ENV.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def write_refresh(new_token):
    lines = ENV.read_text().splitlines()
    out = []
    replaced = False
    for line in lines:
        if line.startswith("YOUTUBE_REFRESH_TOKEN="):
            out.append(f'YOUTUBE_REFRESH_TOKEN="{new_token}"')
            replaced = True
        else:
            out.append(line)
    if not replaced:
        out.append(f'YOUTUBE_REFRESH_TOKEN="{new_token}"')
    ENV.write_text("\n".join(out) + "\n")
    print(f"✅ wrote new refresh token to {ENV}")


def main():
    env = read_env()
    cid = env["YOUTUBE_CLIENT_ID"]
    csec = env["YOUTUBE_CLIENT_SECRET"]

    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={cid}&redirect_uri={REDIRECT}&response_type=code&"
        f"scope={'%20'.join(s.replace(':', '%3A').replace('/', '%2F') for s in SCOPES)}&"
        "access_type=offline&prompt=consent"
    )
    print("\n=== OPEN THIS URL IN YOUR BROWSER ===\n")
    print(auth_url)
    print("\n=== AFTER GRANTING ACCESS, PASTE THE CODE BELOW ===\n")
    code = input("code (or full redirect URL): ").strip()
    if "code=" in code:
        code = re.search(r"code=([^&]+)", code).group(1)

    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": cid,
            "client_secret": csec,
            "code": code,
            "redirect_uri": REDIRECT,
            "grant_type": "authorization_code",
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    refresh = data.get("refresh_token")
    if not refresh:
        print("⚠️ no refresh_token returned. Re-run with prompt=consent (already set) "
              "and ensure you revoke the old grant first, or use a different Google account.")
        sys.exit(1)
    write_refresh(refresh)
    print("DONE. Thumbnails + delete will now work.")


if __name__ == "__main__":
    main()
