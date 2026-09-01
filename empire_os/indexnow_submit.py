"""
indexnow_submit.py — submit all AEO page URLs to Bing/DuckDuckGo/Yandex via
IndexNow (credential-free, no Webmaster account needed).

The key file lives at https://empire-ai.co.uk/<KEY>.txt (served by caddy from
/srv/aeo). Run after generating/updating AEO pages.

Run:
  python3 indexnow_submit.py
"""
from __future__ import annotations
import json, re, urllib.request, urllib.error
from pathlib import Path

KEY = "d857ca343ba6a720246b88872937f277"
KEY_FILE = f"https://empire-ai.co.uk/{KEY}.txt"
SITEMAP = Path("/srv/aeo/sitemap.xml")
API = "https://api.indexnow.org/indexnow"


def collect_urls() -> list[str]:
    xml = SITEMAP.read_text()
    return re.findall(r"<loc>(.*?)</loc>", xml)


def submit(urls: list[str]) -> int:
    payload = json.dumps({
        "host": "empire-ai.co.uk",
        "key": KEY,
        "keyLocation": KEY_FILE,
        "urlList": urls,
    }).encode()
    req = urllib.request.Request(API, data=payload,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def main():
    urls = collect_urls()
    if not urls:
        print("no URLs found in sitemap")
        return
    code = submit(urls)
    print(f"[indexnow] submitted {len(urls)} URLs -> HTTP {code}")
    print("  (202=accepted by Bing/DuckDuckGo/Yandex; indexing follows)")


if __name__ == "__main__":
    main()
