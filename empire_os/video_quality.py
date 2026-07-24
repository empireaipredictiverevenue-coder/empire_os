#!/usr/bin/env python3
"""Empire OS video quality producer — converts flat static-portrait+audio
into a real, watchable B2B avatar video.

Pipeline (no GPU, no paid APIs):
  1. Pass 1: render base looped portrait with Ken Burns push-in, 1080x1080
  2. Pass 2: overlay B-roll data cards at script-beat intervals + end-screen CTA
  3. Optional pass 3: mix voice + ambient music bed
"""
from __future__ import annotations
import json, math, subprocess, wave
from pathlib import Path

PORTRAIT = Path("/root/avatar_assets/portrait_hi.jpg")
PLACEHOLDER = Path("/root/avatar_assets/placeholder_portrait.png")
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_LIGHT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


# ----------------------------- audio helpers -----------------------------

def make_ambient_music(out_wav: str, duration: int, bpm: int = 84) -> bool:
    try:
        import numpy as np
    except ImportError:
        return False
    sr = 44100
    n = int(duration * sr)
    Path(out_wav).parent.mkdir(parents=True, exist_ok=True)
    t = np.linspace(0, duration, n, False)
    freqs = [65.41, 98.00, 164.81]
    amb = sum(np.sin(2*math.pi*f*t) for f in freqs) / len(freqs) * 0.06
    beat_period = 60.0 / bpm
    tick = np.zeros_like(t)
    for i in range(int(duration / beat_period)):
        ts = i * beat_period
        idx = int(ts * sr)
        env = np.exp(-np.linspace(0, 1, int(0.15*sr)))
        if idx + len(env) <= len(tick):
            tick[idx:idx+len(env)] += np.sin(2*math.pi*2200*np.linspace(0, 0.15, int(0.15*sr))) * env * 0.05
    mix = np.clip((amb + tick).astype("float32"), -1.0, 1.0)
    pcm = (mix * 32767).astype("<i2").tobytes()
    with wave.open(out_wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
        w.writeframes(pcm)
    return Path(out_wav).exists()


def mix_audio(voice_wav: str, music_wav: str, out_wav: str) -> bool:
    Path(out_wav).parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([
        "ffmpeg", "-y",
        "-i", voice_wav,
        "-i", music_wav,
        "-filter_complex", "[1:a]volume=0.12[mus];[0:a][mus]amix=inputs=2:duration=longest:normalize=0",
        "-c:a", "aac", "-b:a", "192k", out_wav
    ], capture_output=True, text=True, timeout=300)
    return r.returncode == 0 and Path(out_wav).exists() and Path(out_wav).stat().st_size > 0


# ----------------------------- graphics -----------------------------

def make_data_card(text: str, out_png: str, accent=(0, 230, 220)) -> bool:
    """Full-screen B-roll card with a single big data point."""
    from PIL import Image, ImageDraw, ImageFont
    w, h = 1920, 1080
    img = Image.new("RGB", (w, h), (10, 14, 24))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 18, h], fill=accent)
    safe = text if len(text) < 70 else text[:67] + "..."
    try:
        f = ImageFont.truetype(FONT_BOLD, 130)
        f2 = ImageFont.truetype(FONT_LIGHT, 34)
    except Exception:
        f = ImageFont.load_default(); f2 = f
    bb = d.textbbox((0, 0), safe, font=f)
    tw, th = bb[2]-bb[0], bb[3]-bb[1]
    d.text(((w-tw)//2, (h-th)//2 - 60), safe, fill=(255, 255, 255), font=f)
    d.text((60, h-80), "EMPIRE AI  •  Predictive Revenue Intelligence",
           fill=(170, 200, 220), font=f2)
    img.save(out_png, "PNG", optimize=True)
    return Path(out_png).exists()


# ----------------------------- main render -----------------------------

def render_quality_video(voice_wav: str, portrait_path: Path, beats: list[str],
                         out_path: str, accent=(0, 230, 220)) -> dict:
    """Single-pass render: portrait loop + voice + B-roll data cards + end-screen CTA.
    No zoompan (kept slow on this CPU); b-roll cards provide the visual motion.
    """
    # probe voice duration
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", voice_wav],
        capture_output=True, text=True, timeout=20)
    try:
        duration = float(r.stdout.strip())
    except Exception:
        duration = 60.0
    duration = min(max(duration, 8.0), 480.0)

    work_dir = Path("/tmp/empire_quality")
    work_dir.mkdir(parents=True, exist_ok=True)
    portrait_input = str(portrait_path if portrait_path.exists() else PLACEHOLDER)

    beats = beats if beats else ["Key insight"]
    usable = max(1.0, duration - 10.0)
    per = max(3.0, usable / len(beats))

    # build the inputs: portrait (-i 0), voice (-i 1), then cards (-i 2..N+1)
    cmd = ["ffmpeg", "-y",
           "-loop", "1", "-t", str(duration), "-i", portrait_input,
           "-i", voice_wav]
    fc_parts = [
        "[0:v]scale=1080:1080:force_original_aspect_ratio=increase,"
        "crop=1080:1080,format=yuv420p[bg]"
    ]
    last_label = "bg"
    for i, beat in enumerate(beats):
        cp = work_dir / f"card_{i:02d}.png"
        make_data_card(beat, str(cp), accent=accent)
        idx = i + 2  # inputs: 0=portrait, 1=voice, 2..=cards
        cmd.extend(["-i", str(cp)])
        start = 5.0 + i * per
        end = min(start + per - 0.5, duration - 5.0)
        if end <= start:
            continue
        card_label = f"c{i}"
        fc_parts.append(
            f"[{idx}:v]loop=loop=-1:size=1:start=0,trim=duration={end-start},setpts=PTS+{start:.2f}/TB,"
            f"format=yuva420p,fade=t=in:st={start:.2f}:d=0.4:alpha=1,"
            f"fade=t=out:st={end:.2f}:d=0.4:alpha=1[pcard{i}]"
        )
        out_label = f"step{i+1}"
        fc_parts.append(
            f"[{last_label}][pcard{i}]overlay=enable='between(t,{start:.2f},{end:.2f})':"
            f"x=(W-w)/2:y=(H-h)/2[{out_label}]"
        )
        last_label = out_label

    end_start = max(0.0, duration - 10.0)
    fc_parts.append(
        f"[{last_label}]drawtext=fontfile={FONT_BOLD}:"
        f"text='GET THE EMPIRE AI CASE STUDY  -  link in description':"
        f"fontcolor=white:fontsize=44:box=1:boxcolor=0x000000AA:boxborderw=18:"
        f"x=(w-text_w)/2:y=h-200:enable='gte(t,{end_start:.2f})'[vfinal]"
    )

    filter_complex = ";\n".join(fc_parts)
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[vfinal]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration),
        "-movflags", "+faststart",
        out_path,
    ])
    try:
        r2 = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "ffmpeg timeout"}
    ok = r2.returncode == 0 and Path(out_path).exists() and Path(out_path).stat().st_size > 0
    return {
        "ok": ok,
        "out": out_path,
        "duration": duration,
        "cards_used": len(beats),
        "stderr_tail": r2.stderr[-500:] if not ok else "",
    }


def render_cinematic(voice_wav: str, portrait_path: Path, beats: list[str],
                     out_path: str, script: dict | None = None) -> dict:
    """Cinematic render using the full branding kit from video_branding.py.
    Overlay layers:
      - always-on logo watermark (bottom-right)
      - cinematic lower-third name plate (first 6s, fade in/out)
      - B-roll cutaways: dashboard, data table (full-screen)
      - animated subscribe button (last 12s of video)
      - end screen (last 12s, fade-in)
    """
    from video_branding import (
        make_logo_watermark, make_name_plate, make_end_screen,
        make_broll_dashboard, make_broll_data_table,
        make_subscribe_button_frames, OUT_DIR,
    )

    # probe voice duration
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", voice_wav],
        capture_output=True, text=True, timeout=20)
    try:
        duration = float(r.stdout.strip())
    except Exception:
        duration = 60.0
    duration = min(max(duration, 12.0), 480.0)

    # render all branding assets fresh
    logo = make_logo_watermark()
    name_plate = make_name_plate(
        (script or {}).get("founder_name", "Phillip Livesley"),
        (script or {}).get("founder_title", "Founder, Empire AI"),
    )
    end_screen = make_end_screen([
        "How we 10X'd pipeline with one AI agent",
        "Inside the Empire AI scoring model",
    ])
    sub_frames = make_subscribe_button_frames()
    broll_dash = make_broll_dashboard()
    broll_table = make_broll_data_table()

    # total b-roll cutaways — alternate dashboard and data table
    brolls = [broll_dash, broll_table, broll_dash, broll_table, broll_dash]
    brolls = brolls[: max(1, min(5, len(beats)))]

    portrait_path = Path(portrait_path)
    portrait_input = str(portrait_path if portrait_path.exists() else PLACEHOLDER)
    cmd = ["ffmpeg", "-y",
           "-loop", "1", "-t", str(duration), "-i", portrait_input,
           "-i", voice_wav,
           "-i", logo, "-i", name_plate,
           "-i", brolls[0]]
    for b in brolls[1:]:
        cmd.extend(["-i", b])
    for sf in sub_frames:
        cmd.extend(["-i", sf])
    cmd.extend(["-i", end_screen])

    # input index map:
    #   0=portrait, 1=voice, 2=logo, 3=name_plate, 4..N+=broll, then sub frames, then end_screen
    n_brolls = len(brolls)
    sub_start_idx = 4 + n_brolls  # sub_frames start here
    end_idx = sub_start_idx + len(sub_frames)

    fc_parts = [
        "[0:v]scale=1080:1080:force_original_aspect_ratio=increase,"
        "crop=1080:1080,format=yuv420p[bg]"
    ]
    last = "bg"

    # ----- Logo watermark: always-on, bottom-right -----
    # logo size is 360x90, place at x=W-380, y=H-110
    fc_parts.append(
        f"[2:v]scale=300:75[logo]"
    )
    fc_parts.append(
        f"[{last}][logo]overlay=W-320:H-110[v1]"
    )
    last = "v1"

    # ----- Name plate: first 6s, lower-third -----
    fc_parts.append(
        f"[3:v]scale=1100:172,format=yuva420p[np_prep]"
    )
    fc_parts.append(
        f"[{last}][np_prep]overlay=x=(W-w)/2:y=H-h-200:enable='between(t,1,5.5)'[v2]"
    )
    last = "v2"

    # ----- B-roll cutaways (full-screen, alternating dashboard/table) -----
    if duration > 12:
        usable = max(1.0, duration - 12.0)
        per = max(4.0, usable / n_brolls)
        for i, _ in enumerate(brolls):
            start = 8.0 + i * per
            end = min(start + per - 0.5, duration - 14.0)
            if end <= start:
                continue
            idx = 4 + i
            fc_parts.append(
                f"[{idx}:v]loop=loop=-1:size=1:start=0,trim=duration={min(end-start, duration)},"
                f"scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080,"
                f"fade=t=in:st=0:d=0.5:alpha=1,"
                f"setpts=PTS-STARTPTS[br{i}]"
            )
            out_label = f"v_br{i+1}"
            fc_parts.append(
                f"[{last}][br{i}]overlay=enable='between(t,{start:.2f},{end:.2f})':"
                f"format=auto["
                f"{out_label}]"
            )
            last = out_label

    # ----- Subscribe button: pulsing near top-right for last 12s -----
    if duration > 16:
        sub_start = duration - 12.0
        # build a sequence input that cycles the 12 frames at 12fps (each frame ~0.83s)
        # ffmpeg can do this with concat or with -loop on each frame; simplest:
        # use all 12 as independent overlays with one-second windows each
        per_frame = 1.0  # each frame visible for 1.0s
        for i, _sf in enumerate(sub_frames):
            idx = sub_start_idx + i
            t_show = sub_start + i * per_frame
            t_hide = t_show + per_frame
            if i == 0:
                fc_parts.append(f"[{idx}:v]format=yuva420p,setpts=PTS+{t_show:.2f}/TB[sf0]")
                fc_parts.append(
                    f"[{last}][sf0]overlay=W-360:H-200:enable='between(t,{t_show:.2f},{t_hide:.2f})'[vsub1]"
                )
                last = "vsub1"
            else:
                fc_parts.append(f"[{idx}:v]format=yuva420p,setpts=PTS+{t_show:.2f}/TB[sf{i}]")
                fc_parts.append(
                    f"[{last}][sf{i}]overlay=W-360:H-200:enable='between(t,{t_show:.2f},{t_hide:.2f})'[vsub{i+1}]"
                )
                last = f"vsub{i+1}"

    # ----- End screen: show in last 8s, simpler chained enable-based overlay -----
    end_start = max(0.0, duration - 8.0)
    # Use trim + setpts to put the end screen at t=end_start and forward
    fc_parts.append(
        f"[{end_idx}:v]scale=1080:1080,trim=duration={8.0:.2f},setpts=PTS+{end_start:.2f}/TB,format=yuva420p[es]"
    )
    fc_parts.append(
        f"[{last}][es]overlay=format=auto[vfinal]"
    )

    filter_complex = ";\n".join(fc_parts)
    cmd.extend([
        "-filter_complex", filter_complex,
        "-map", "[vfinal]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "23",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-t", str(duration),
        "-movflags", "+faststart",
        out_path,
    ])
    try:
        rr = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "ffmpeg timeout"}
    ok = rr.returncode == 0 and Path(out_path).exists() and Path(out_path).stat().st_size > 0
    return {
        "ok": ok,
        "out": out_path,
        "duration": duration,
        "brolls": n_brolls,
        "subscribe_frames": len(sub_frames),
        "stderr_tail": rr.stderr[-500:] if not ok else "",
    }


if __name__ == "__main__":
    import sys as _s
    if len(_s.argv) < 3:
        print("usage: video_quality.py <voice.wav> <portrait.jpg> [out.mp4]")
        _s.exit(1)
    voice = _s.argv[1]
    portrait = Path(_s.argv[2])
    out = _s.argv[3] if len(_s.argv) > 3 else "/tmp/empire_quality.mp4"
    beats = [
        "10X BETTER\nLEAD QUALIFICATION",
        "REAL REVENUE\nCONVERSATIONS",
        "10X ROI IN\nFIRST 90 DAYS",
    ]
    res = render_quality_video(voice, portrait, beats, out)
    print(json.dumps(res, default=str, indent=2))
