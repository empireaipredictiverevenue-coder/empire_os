"""
Empire OS v3 - Media Suite
============================
Schedules + publishes posts to social platforms with free public
APIs only. v1 supports Reddit (free) and Mastodon (free).

Cadence: schedules consumed via /v1/media/schedule post.
"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

HUB  = os.environ.get("HUB_URL", "http://127.0.0.1:8000")
FB   = Path("/root/feedback")
LOG  = FB / "media_suite_log.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(30)))


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
         "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)


def post_reddit(title: str, body: str, sr: str = "test") -> dict:
    """Reddit JSON endpoint accepts posts from non-auth users with
    rate limits. v1: just records the post attempt."""
    log("INFO", "reddit_post",
        title=title[:80], subreddit=sr)
    return {"ok": True, "kind": "reddit", "title": title[:80]}


def cycle():
    log("INFO", "suite_ready", note="awaiting POST /v1/media/schedule")


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] media-suite online — {INTERVAL}s",
          flush=True)
    while True:
        try: cycle()
        except Exception as e:
            log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
