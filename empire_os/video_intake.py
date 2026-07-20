"""
video_intake.py — turn any video into text + frames for Empire agents.

Wraps bradautomates/claude-video's `watch.py` so content-seo / scout /
research agents can ingest a video URL or local file and get back a
transcript + frame paths to reason over (leads, testimonials, competitors).

Requires:
  - /root/claude-video/skills/watch/scripts/watch.py  (the upstream skill)
  - ffmpeg on PATH
  - yt-dlp on PATH  (uv tool install yt-dlp)
  - optional: GROQ_API_KEY / OPENAI_API_KEY for Whisper fallback

Usage:
  from empire_os.video_intake import watch
  res = watch("https://.../demo.mp4", detail="efficient", max_frames=8)
  print(res["transcript"])
  for f in res["frames"]:
      ...
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

WATCH_SCRIPT = "/root/claude-video/skills/watch/scripts/watch.py"


def watch(
    source: str,
    detail: str = "efficient",
    max_frames: int = 12,
    whisper: Optional[str] = None,
    out_dir: Optional[str] = None,
    start: Optional[str] = None,
    end: Optional[str] = None,
) -> dict:
    """Run /watch on a video and return {transcript, frames, work_dir, ok}.

    detail: transcript|efficient|balanced|token-burner
    frames: list of absolute JPEG paths extracted from the work dir
    """
    if not os.path.exists(WATCH_SCRIPT):
        return {"ok": False, "error": f"watch.py not found at {WATCH_SCRIPT}",
                "transcript": "", "frames": [], "work_dir": ""}

    work = out_dir or tempfile.mkdtemp(prefix="empire-watch-")
    Path(work).mkdir(parents=True, exist_ok=True)

    cmd = [
        "python3", WATCH_SCRIPT, source,
        "--detail", detail,
        "--max-frames", str(max_frames),
        "--out-dir", work,
        "--resolution", "512",
    ]
    if whisper:
        cmd += ["--whisper", whisper]
    else:
        cmd += ["--no-whisper"]
    if start:
        cmd += ["--start", start]
    if end:
        cmd += ["--end", end]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "watch timeout (600s)",
                "transcript": "", "frames": [], "work_dir": work}

    stdout = proc.stdout or ""
    transcript = _extract_transcript(stdout)
    frames = _collect_frames(work)
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "transcript": transcript,
        "frames": frames,
        "work_dir": work,
        "stderr": (proc.stderr or "")[-500:],
    }


def _extract_transcript(stdout: str) -> str:
    """Pull the '## Transcript' fenced block out of watch.py's markdown."""
    m = re.search(r"## Transcript\s*\n(.*?)(\n---|\Z)", stdout, re.DOTALL)
    if not m:
        return ""
    block = m.group(1)
    # strip the ``` fences
    block = re.sub(r"```", "", block)
    # strip the "_Source: ... _" caption line
    block = re.sub(r"_Source:.*?_\n?", "", block, flags=re.DOTALL)
    return block.strip()


def _collect_frames(work_dir: str) -> list[str]:
    """Frames watch.py writes are named like frame_0001.jpg / 0001.jpg."""
    out = []
    for p in sorted(Path(work_dir).rglob("*")):
        if p.suffix.lower() in (".jpg", ".jpeg", ".png") and p.is_file():
            out.append(str(p.resolve()))
    return out


if __name__ == "__main__":
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else "/tmp/bbb.mp4"
    r = watch(src, detail="efficient", max_frames=4, out_dir="/tmp/watch_demo")
    print("ok:", r["ok"])
    print("frames:", len(r["frames"]))
    print("transcript len:", len(r["transcript"]))
    print(r["transcript"][:300])
