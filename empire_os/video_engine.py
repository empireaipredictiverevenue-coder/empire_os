#!/usr/bin/env python3
"""video_engine.py — turn content into a branded short video (credential-free).

Takes a title + script lines, renders an ffmpeg slideshow with:
  - branded dark background (cyan/blue/neon-green)
  - text slides (wrapped)
  - Empire AI logo watermark
  - 3s per slide, 1080x1920 (vertical, social-ready)
No external API, no TTS needed (silent branded video). If espeak/TTS is
later added, audio track can be muxed in.

Outputs: /srv/aeo/video/<niche>.mp4
"""
from __future__ import annotations
import os, sys, subprocess, textwrap, tempfile
from pathlib import Path

OUT_DIR = "/srv/aeo/video"
W, H = 1080, 1920
SLIDE_SEC = 4


def _slide_png(text: str, idx: int, total: int, path: str):
    """Render one text slide as PNG using ffmpeg drawtext (no PIL dep)."""
    safe = text.replace("'", "").replace('"', "")
    # wrap to ~22 chars/line, max 6 lines
    lines = []
    for para in safe.split("\n"):
        lines += textwrap.wrap(para, 22) or [""]
    lines = lines[:6]
    # build drawtext filters
    filters = []
    y = 700
    for i, ln in enumerate(lines):
        esc = ln.replace(":", r"\:").replace("%", r"\%").replace(",", r"\,")
        filters.append(
            f"drawtext=text='{esc}':fontcolor=white:fontsize=54:"
            f"x=(w-text_w)/2:y={y}:fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        )
        y += 70
    # footer progress
    filters.append(
        f"drawtext=text='Empire AI  ({idx}/{total})':fontcolor=#00BFFF:"
        f"fontsize=34:x=60:y={H-120}:"
        f"fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    )
    vf = ",".join(filters)
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"color=c=0x0a0a12:s={W}x{H}:d={SLIDE_SEC}",
        "-vf", vf, "-frames", "1", path,
    ]
    subprocess.run(cmd, capture_output=True, timeout=30)


def render(niche: str, title: str, lines: list[str]) -> str:
    """Render a vertical video from title + bullet lines. Returns mp4 path."""
    os.makedirs(OUT_DIR, exist_ok=True)
    tmp = tempfile.mkdtemp()
    slides = [title] + lines
    slide_paths = []
    for i, s in enumerate(slides):
        p = os.path.join(tmp, f"s{i}.png")
        _slide_png(s, i + 1, len(slides), p)
        slide_paths.append(p)
    # concat slides
    concat = os.path.join(tmp, "list.txt")
    with open(concat, "w") as f:
        for p in slide_paths:
            f.write(f"file '{p}'\n")
    out = os.path.join(OUT_DIR, f"{niche}.mp4")
    cmd = [
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat,
        "-vf", f"scale={W}:{H},format=yuv420p",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-r", "25", out,
    ]
    r = subprocess.run(cmd, capture_output=True, timeout=120)
    if r.returncode != 0:
        print(f"[video_engine] ffmpeg failed: {r.stderr.decode()[:200]}")
        return ""
    print(f"[video_engine] wrote {out}")
    return out


if __name__ == "__main__":
    niche = sys.argv[1] if len(sys.argv) > 1 else "hvac"
    title = f"{niche.replace('_',' ').title()} Leads on Autopilot"
    lines = [
        "Find in-market buyers",
        "Score with Omega engine",
        "Route hot leads to close",
        "Settle in USDT",
        "empire-ai.co.uk",
    ]
    render(niche, title, lines)
