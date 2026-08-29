#!/usr/bin/env python3
"""Empire OS — throttled YouTube bulk uploader.

Reality: YouTube Data API v3 default quota = 10000 units/day.
Each videos.insert = 1600 units. Max ~6 uploads/day on default quota.

This dispatcher:
  - scans /root/empire_os/empire_os/social_queue/*.json
  - skips already-uploaded files (progress persisted)
  - uploads up to MAX_PER_RUN (default 6) this run
  - writes progress to /root/empire_os/feedback/yt_bulk_progress.json
  - re-runnable daily: resumes where it left off

Usage:
  python3 /root/empire_os/scripts/yt_bulk_upload.py          # max 6
  python3 /root/empire_os/scripts/yt_bulk_upload.py 3        # max 3
"""
import json
import sys
import time
from pathlib import Path

ROOT = Path("/root/empire_os/empire_os")
QUEUE = ROOT / "social_queue"
RENDER = ROOT / "social_render"
FEED = Path("/root/empire_os/feedback")
PROGRESS = FEED / "yt_bulk_progress.json"

MAX_PER_RUN = int(sys.argv[1]) if len(sys.argv) > 1 else 6

sys.path.insert(0, "/root/empire_os")

def load_progress():
    if PROGRESS.exists():
        try:
            return json.loads(PROGRESS.read_text())
        except Exception:
            pass
    return {"done": [], "failed": []}

def save_progress(p):
    FEED.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(p, indent=2))

def main():
    p = load_progress()
    done = set(p.get("done", []))
    failed = set(p.get("failed", []))

    files = sorted(QUEUE.glob("*.json"))
    pending = [f for f in files if f.name not in done and f.name not in failed]

    print(f"QUEUE={len(files)} DONE={len(done)} FAILED={len(failed)} PENDING={len(pending)} MAX_THIS_RUN={MAX_PER_RUN}")

    if not pending:
        print("NOTHING_PENDING — all queue files processed.")
        return

    count = 0
    for f in pending:
        if count >= MAX_PER_RUN:
            print(f"REACHED_MAX {MAX_PER_RUN} — stop. Re-run tomorrow for more.")
            break
        try:
            sc = json.loads(f.read_text())
            out = RENDER / f"{f.stem}.mp4"
            from empire_os.avatar_pipeline import run
            res = run(sc, str(out), upload_to_youtube=True)
            yt = res.get("youtube_uploaded") or {}
            if yt.get("success"):
                url = yt.get("url")
                print(f"OK   {f.name} -> {url}")
                done.add(f.name)
                p["done"] = sorted(done)
                save_progress(p)
                count += 1
            else:
                err = yt.get("error", "unknown")
                print(f"FAIL {f.name}: {err}")
                failed.add(f.name)
                p["failed"] = sorted(failed)
                save_progress(p)
        except Exception as e:
            print(f"ERR  {f.name}: {e}")
            failed.add(f.name)
            p["failed"] = sorted(failed)
            save_progress(p)

    # summarize
    p = load_progress()
    print(f"SUMMARY DONE={len(p['done'])} FAILED={len(p['failed'])}")
    print("RE-RUN DAILY: python3 /root/empire_os/scripts/yt_bulk_upload.py")

if __name__ == "__main__":
    main()
