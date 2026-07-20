#!/usr/bin/env python3
"""Empire OS video branding: intro, outro, watermark.

Free, local, asset-less. Builds intro/outro motion graphics from the
channel name + tagline using ffmpeg drawtext (no image assets needed).
Applies a persistent corner watermark to every Short so uploads carry
the brand even when the face is the spokesperson.

Config (edit BRAND):
  CHANNEL  - text shown big (channel name)
  TAGLINE  - smaller line under it
  COLOR    - accent hex (no leading #)
  FONT     - ttf path
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

BRAND = {
    "channel": "Empire-AI",
    "tagline": "AI that closes deals",
    "color": "FFD400",          # accent yellow
    "bg": "0B0B0B",             # near-black
    "font": "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
}
W, H = 1080, 1920               # 9:16 Shorts
FPS = 30


def _run(cmd: list[str]) -> bool:
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        print("BRAND_ERR:", r.stderr[-300:])
    return r.returncode == 0


def make_intro(out_mp4: str, dur: float = 2.5) -> str:
    """Animated intro: bg fade-in, channel name scales up, tagline drops."""
    ch, tg = BRAND["channel"], BRAND["tagline"]
    col, bg, fn = BRAND["color"], BRAND["bg"], BRAND["font"]
    vf = (
        f"color=c=0x{bg}:s={W}x{H}:r={FPS},"
        f"format=yuv420p,"
        # channel name: scale-in + hold
        f"drawtext=fontfile='{fn}':text='{ch}':fontcolor=0x{col}:"
        f"fontsize=110:box=1:boxcolor=black@0.6:"
        f"x=(w-text_w)/2:y=(h-text_h)/2-60:"
        f"alpha='if(lt(t,0.4),0,if(lt(t,1.0),(t-0.4)/0.6,1))',"
        # tagline: fade in after name
        f"drawtext=fontfile='{fn}':text='{tg}':fontcolor=white:"
        f"fontsize=46:box=1:boxcolor=black@0.6:"
        f"x=(w-text_w)/2:y=(h)/2+40:"
        f"alpha='if(lt(t,0.9),0,if(lt(t,1.5),(t-0.9)/0.6,1))'"
    )
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", vf,
           "-t", str(dur), "-c:v", "libx264", "-pix_fmt", "yuv420p", out_mp4]
    return out_mp4 if _run(cmd) else ""


def make_outro(out_mp4: str, dur: float = 3.0) -> str:
    """Outro CTA: 'Subscribe to Empire-AI' + bell prompt, animated."""
    ch = BRAND["channel"]
    col, bg, fn = BRAND["color"], BRAND["bg"], BRAND["font"]
    vf = (
        f"color=c=0x{bg}:s={W}x{H}:r={FPS},"
        f"format=yuv420p,"
        f"drawtext=fontfile='{fn}':text='SUBSCRIBE':fontcolor=0x{col}:"
        f"fontsize=120:box=1:boxcolor=black@0.6:"
        f"x=(w-text_w)/2:y=(h-text_h)/2-120:"
        f"alpha='if(lt(t,0.5),0,1)',"
        f"drawtext=fontfile='{fn}':text='{ch}':fontcolor=white:"
        f"fontsize=64:box=1:boxcolor=black@0.6:"
        f"x=(w-text_w)/2:y=(h)/2-10:"
        f"alpha='if(lt(t,0.8),0,1)',"
        f"drawtext=fontfile='{fn}':text='tap the bell for daily AI wins':"
        f"fontcolor=0xCCCCCC:fontsize=38:"
        f"x=(w-text_w)/2:y=(h)/2+90:"
        f"alpha='if(lt(t,1.1),0,1)'"
    )
    cmd = ["ffmpeg", "-y", "-f", "lavfi", "-i", vf,
           "-t", str(dur), "-c:v", "libx264", "-pix_fmt", "yuv420p", out_mp4]
    return out_mp4 if _run(cmd) else ""


def add_watermark(src_mp4: str, out_mp4: str, text: str = "") -> str:
    """Persistent corner watermark (channel name) burned into the video."""
    mark = text or BRAND["channel"]
    col, fn = BRAND["color"], BRAND["font"]
    vf = (
        f"[0:v]drawtext=fontfile='{fn}':text='{mark}':fontcolor=0x{col}@0.85:"
        f"fontsize=40:box=1:boxcolor=black:"
        f"x=w-text_w-30:y=h-text_h-30:alpha=0.85[v]"
    )
    cmd = ["ffmpeg", "-y", "-i", src_mp4, "-filter_complex", vf,
           "-map", "[v]", "-map", "0:a?", "-c:v", "libx264",
           "-pix_fmt", "yuv420p", "-c:a", "copy", out_mp4]
    return out_mp4 if _run(cmd) else src_mp4


def assemble(body_mp4: str, out_mp4: str,
             intro_dur: float = 2.5, outro_dur: float = 3.0) -> str:
    """Full branded Short: intro + watermarked body + outro, one file."""
    tmp = Path(tempfile.gettempdir())
    intro = make_intro(str(tmp / "brand_intro.mp4"), intro_dur)
    outro = make_outro(str(tmp / "brand_outro.mp4"), outro_dur)
    if not intro or not outro:
        return body_mp4
    wm = add_watermark(body_mp4, str(tmp / "brand_body_wm.mp4"))
    # concat (re-encode to uniform params)
    listf = tmp / "brand_list.txt"
    listf.write_text(
        f"file '{intro}'\nfile '{wm}'\nfile '{outro}'\n")
    cmd = ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(listf),
           "-vsync", "vfr", "-c:v", "libx264", "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "128k", out_mp4]
    return out_mp4 if _run(cmd) else body_mp4


if __name__ == "__main__":
    import sys
    body = sys.argv[1] if len(sys.argv) > 1 else ""
    out = sys.argv[2] if len(sys.argv) > 2 else "/tmp/branded.mp4"
    if not body:
        print("usage: video_brand.py <body.mp4> [out.mp4]")
        raise SystemExit(1)
    res = assemble(body, out)
    print("BRANDED:", res)
