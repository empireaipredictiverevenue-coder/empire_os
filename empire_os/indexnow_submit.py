#!/usr/bin/env python3
"""indexnow_submit — Submit URLs to IndexNow (Bing/DuckDuckGo/Yandex).

Reads sitemap.xml, extracts up to 10k URLs, submits via IndexNow API
using the stored key. Tracks submission state in /root/empire_os/feedback/indexnow.jsonl.

Key: /srv/aeo/{key}.txt (must be publicly served at /{key}.txt)
"""
from __future__ import annotations
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

SITEMAP = "/srv/aeo/sitemap.xml"
AEO_DIR = Path("/srv/aeo")
HOST = "empire-ai.co.uk"
LOG_PATH = Path("/root/empire_os/feedback/indexnow.jsonl")
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
MAX_URLS = 10000  # IndexNow hard cap


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _log(record: dict) -> None:
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(record, default=str) + "\n")


def find_key() -> str:
    """Find the IndexNow key (32 hex chars) in /srv/aeo/{key}.txt."""
    for p in AEO_DIR.glob("*.txt"):
        if len(p.stem) == 32 and all(c in "0123456789abcdef" for c in p.stem.lower()):
            return p.stem
    return ""


def read_sitemap(max_urls: int = MAX_URLS) -> list:
    """Read up to max_urls URLs from sitemap."""
    try:
        tree = ET.parse(SITEMAP)
        urls = [u.text for u in tree.getroot().iter()
                if u.text and "empire-ai.co.uk" in u.text]
        return urls[:max_urls]
    except Exception as e:
        _log({"ts": _now(), "event": "read_sitemap_error", "error": str(e)[:200]})
        return []


def submit(urls: list, key: str) -> dict:
    """Submit URLs to IndexNow."""
    if not urls or not key:
        return {"ok": False, "error": "missing_input"}
    key_url = f"https://{HOST}/{key}.txt"
    payload = {
        "host": HOST,
        "key": key,
        "keyLocation": key_url,
        "urlList": urls,
    }
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        "https://api.indexnow.org/indexnow",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return {
                "ok": True,
                "status": r.status,
                "url_count": len(urls),
            }
    except urllib.error.HTTPError as e:
        return {
            "ok": False,
            "status": e.code,
            "error": e.read().decode()[:200],
            "url_count": len(urls),
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200], "url_count": len(urls)}


def main() -> dict:
    key = find_key()
    if not key:
        return {"ok": False, "error": "no_key_file"}

    urls = read_sitemap()
    if not urls:
        return {"ok": False, "error": "no_urls"}

    summary = {
        "ts": _now(),
        "key": key[:8] + "...",
        "url_count": len(urls),
    }
    result = submit(urls, key)
    summary.update(result)
    _log(summary)
    return summary


if __name__ == "__main__":
    print(json.dumps(main(), indent=2, default=str))