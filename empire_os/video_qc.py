#!/usr/bin/env python3
"""Empire OS Video Quality Council + Judge.

Multi-inspector council scores every rendered Short before publish.
A single hard-fail (no face, silent audio, bad format) rejects the
video so junk never ships. The Judge aggregates weighted scores and
returns a SHIP / HOLD verdict with reasons.

Free, local, CPU-only: OpenCV Haar face detection + ffmpeg probes.
No external API, no branding, no paid service.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import cv2

QC_DIR = Path("/root/avatar_assets/qc")
FACE_CASCADE = str(QC_DIR / "haarcascade_frontalface_default.xml")
MIN_W, MIN_H = 1080, 1920          # 9:16 Shorts floor
MIN_DUR, MAX_DUR = 7.0, 75.0       # acceptable Short length (s)
SHIP_THRESHOLD = 0.70              # weighted score to publish

# Council weights (sum = 1.0)
W_FACE, W_AUDIO, W_FORMAT = 0.45, 0.30, 0.25
W_FACE_LF = 0.15          # longform: face less critical (title cards)


def _probe(video: str) -> dict:
    """ffprobe duration + stream info, or {} on failure."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries",
             "format=duration:stream=width,height,codec_type,codec_name",
             "-of", "json", video],
            capture_output=True, text=True, timeout=30).stdout
        return json.loads(out or "{}")
    except Exception:
        return {}


def _face_score(video: str, sample_n: int = 6, mode: str = "short") -> tuple[float, str]:
    """Detect a centered, non-blurry face in sampled frames.

    Returns (score 0-1, reason). Score = fraction of frames with a
    well-placed face, penalized for blur / off-center.

    mode="longform": title-card segments have no face, so we only require
    that a face appears in at least one sampled frame (avatar is present);
    we do NOT hard-fail on zero-face frames.
    """
    cap = cv2.VideoCapture(video)
    if not cap.isOpened():
        return 0.0, "cannot open video"
    cascade = cv2.CascadeClassifier(FACE_CASCADE)
    if cascade.empty():
        return 0.0, "cascade missing"
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 1
    hits, checks = 0, 0
    for i in range(sample_n):
        idx = int(total * (i + 0.5) / sample_n)
        cap.set(cv2.CAP_PROP_POS_FRAMES, idx)
        ok, frame = cap.read()
        if not ok:
            continue
        checks += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.1, 3, minSize=(40, 40))
        # keep only plausibly-large faces (real subject, not noise speck)
        fw0, fh0 = gray.shape[1], gray.shape[0]
        faces = [f for f in faces if f[2] > 0.12 * fw0]
        if len(faces) == 0:
            continue
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        # centered? face center within middle 70% box
        cx, cy = x + w / 2, y + h / 2
        centered = (0.15 * fw0 < cx < 0.85 * fw0) and (0.15 * fh0 < cy < 0.85 * fh0)
        # sharp? lap-variance above threshold
        lap = cv2.Laplacian(gray[y:y+h, x:x+w], cv2.CV_64F).var()
        sharp = lap > 30
        if centered and sharp:
            hits += 1.0
        elif centered:          # large + centered but slightly soft -> still good
            hits += 0.85
        elif sharp:
            hits += 0.4
    cap.release()
    if checks == 0:
        return 0.0, "no frames read"
    if mode == "longform":
        # title cards have no face; accept if a face appears anywhere
        return (1.0, "avatar present") if hits > 0 else (0.0, "no face anywhere")
    return round(hits / checks, 3), "face ok" if hits / checks > 0.5 else "weak/missing face"


def _audio_score(video: str) -> tuple[float, str]:
    """Verify real, non-silent audio present."""
    try:
        # RMS via volumedetect
        out = subprocess.run(
            ["ffmpeg", "-i", video, "-af", "volumedetect",
             "-f", "null", "-"],
            capture_output=True, text=True, timeout=30).stderr
        for line in out.splitlines():
            if "mean_volume" in line:
                vol = float(line.split(":")[1].strip().replace(" dB", ""))
                if vol < -55:          # near-silent
                    return 0.0, f"silent audio ({vol} dB)"
                return 1.0, f"audio ok ({vol} dB)"
        return 0.0, "no audio stream"
    except Exception as e:
        return 0.0, f"audio probe error: {e}"


def _format_score(video: str, probe: dict, mode: str = "short") -> tuple[float, str]:
    """9:16 (short) or 16:9 (longform) aspect, min res, valid dur, h264/aac."""
    if not probe.get("streams"):
        return 0.0, "no streams"
    v = next((s for s in probe["streams"] if s.get("codec_type") == "video"), None)
    a = next((s for s in probe["streams"] if s.get("codec_type") == "audio"), None)
    if not v:
        return 0.0, "no video stream"
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    if w < MIN_W or h < MIN_H:
        return 0.0, f"low res {w}x{h}"
    if mode == "longform":
        ok_ar = abs(w / h - 16 / 9) < 0.05
        max_dur = 1200.0
    else:
        ok_ar = abs(w / h - 9 / 16) < 0.05
        max_dur = MAX_DUR
    if h <= 0 or not ok_ar:
        return 0.0, f"not 9:16/16:9 ({w}x{h})"
    dur = float(probe.get("format", {}).get("duration", 0) or 0)
    if dur < MIN_DUR or dur > max_dur:
        return 0.3, f"dur {dur:.1f}s out of range"
    if v.get("codec_name") not in ("h264", "avc1") or not a:
        return 0.4, "codec/audio mismatch"
    return 1.0, "format ok"


def council(video: str, mode: str = "short") -> dict:
    """Run all inspectors. Returns per-inspector scores + reasons."""
    probe = _probe(video)
    f_score, f_reason = _face_score(video, mode=mode)
    a_score, a_reason = _audio_score(video)
    fmt_score, fmt_reason = _format_score(video, probe, mode=mode)
    return {
        "face": {"score": f_score, "reason": f_reason},
        "audio": {"score": a_score, "reason": a_reason},
        "format": {"score": fmt_score, "reason": fmt_reason},
    }


def judge(video: str, mode: str = "short") -> dict:
    """Aggregate council into a SHIP/HOLD verdict.

    Hard fails (auto-reject regardless of score):
      - no detectable face (f_score == 0)
      - silent / missing audio (a_score == 0)
      - wrong format (fmt_score == 0)
    mode="longform": face weight reduced (title cards have no face);
      format accepts 16:9 and longer duration.
    """
    c = council(video, mode=mode)
    wf = W_FACE_LF if mode == "longform" else W_FACE
    f, a, fmt = c["face"]["score"], c["audio"]["score"], c["format"]["score"]
    weighted = f * wf + a * W_AUDIO + fmt * W_FORMAT

    hard_fail = (f == 0) or (a == 0) or (fmt == 0)
    ship = (not hard_fail) and (weighted >= SHIP_THRESHOLD)

    reasons = [f"face({f}): {c['face']['reason']}",
               f"audio({a}): {c['audio']['reason']}",
               f"format({fmt}): {c['format']['reason']}"]
    if hard_fail:
        reasons.append("HARD_FAIL: rejected before scoring")
    reasons.append(f"weighted={weighted:.2f} (ship>={SHIP_THRESHOLD}) mode={mode}")

    return {
        "verdict": "SHIP" if ship else "HOLD",
        "weighted": round(weighted, 3),
        "hard_fail": hard_fail,
        "scores": c,
        "reasons": reasons,
    }


if __name__ == "__main__":
    import sys
    vid = sys.argv[1] if len(sys.argv) > 1 else ""
    if not vid:
        print("usage: video_qc.py <video.mp4>")
        raise SystemExit(1)
    print(json.dumps(judge(vid), indent=2, default=str))
