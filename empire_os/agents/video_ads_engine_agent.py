
"""
Empire OS v3 - Video Ads Engine
==================================
Generates 15s / 30s MP4 video ads from a brief + free media library.
Cadence: idempotent loop.
"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

HUB   = os.environ.get("HUB_URL", "http://127.0.0.1:8000")
FB    = Path("/root/feedback")
LOG   = FB / "video_ads_log.jsonl"
RENDERS = FB / "renders"
RENDERS.mkdir(parents=True, exist_ok=True)
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(10)))


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
         "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + chr(10))
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)


def render(brief):
    render_id = "rdr_" + hex(int(time.time()))[2:]
    path = RENDERS / (render_id + ".mp4")
    copy = brief.get("copy", "Empire AI")
    duration = int(brief.get("duration_s", 15))
    niche = brief.get("niche", "general")
    safe_copy = copy.replace("'", "")
    cmd = (
        "ffmpeg -y -f lavfi -i color=c=0x101828:s=720x1280:d=" + str(duration) + ":r=30 "
        "-vf " + chr(34) + "drawtext=text='" + safe_copy + "':fontcolor=white:fontsize=44:"
        "x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=0x101828@0.4:boxborderw=18" + chr(34) + " "
        "-c:v libx264 -preset ultrafast -pix_fmt yuv420p " + chr(34) + str(path) + chr(34) + " 2>/dev/null"
    )
    log("EVENT", "render_started", render_id=render_id, niche=niche,
        duration_s=duration, brief=copy[:140])
    rc = os.system(cmd)
    return {
        "render_id": render_id, "path": str(path), "niche": niche,
        "copy": copy[:140], "duration_s": duration,
        "ffmpeg_returncode": rc,
        "url": "/v1/renders/" + render_id + ".mp4",
    }


def cycle():
    log("INFO", "engine_ready", note="awaiting POST /v1/video/brief")


if __name__ == "__main__":
    print("[" + datetime.now(timezone.utc).isoformat() + "] video-ads engine online (idempotent loop)", flush=True)
    while True:
        try:
            cycle()
        except Exception as e:
            log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
