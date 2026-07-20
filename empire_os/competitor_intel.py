"""competitor_intel.py — learn what wins, feed it back to our scripts.

Ingests competitor videos (transcribe via video_intake) or raw transcript
text dropped in /root/competitors/. An LLM extracts the PATTERNS that win
(hook structure, pacing, CTA style, title formulas, emotional triggers) and
writes style_profile.json. Our script generator reads that profile to mimic
winning structure WITHOUT copying their words (guard-railed).

Usage:
  python3 competitor_intel.py --ingest /root/competitors
  python3 competitor_intel.py --text "pasted transcript..." --name "channelX"
  python3 competitor_intel.py --build-profile   # merge all analyses -> style_profile.json
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

from empire_os import social_syndication as syn
from empire_os import video_intake as vi

COMP_DIR = Path("/root/competitors")
PROFILE_DIR = Path("/root/empire_os/empire_os/style_profile")
ANALYSIS_JSON = PROFILE_DIR / "analyses.jsonl"
STYLE_PROFILE = PROFILE_DIR / "style_profile.json"

ANALYSIS_PROMPT = """You are a viral-content strategist. Analyze this video
transcript from a competing YouTube channel. Extract ONLY the reusable
STRUCTURE and PATTERNS (do not copy their words). Return strict JSON:
{
  "hook_type": "question|statement|story|controversy|number",
  "hook_formula": "how the first 3 seconds are structured",
  "pacing": "fast|medium|slow, and why",
  "cta_style": "how they ask for subscribe/like",
  "title_pattern": "formula they use for titles",
  "emotional_triggers": ["fear","curiosity","greed",...],
  "structure": ["beat1","beat2",...] (the story arc),
  "winning_tactics": ["tactic1","tactic2",...]
}
Be precise. This feeds our script generator to mimic winning structure."""


def _transcribe(path: str) -> str:
    res = vi.watch_video(path, detail="efficient", max_frames=8,
                         out_dir="/tmp/ci_frames")
    return res.get("transcript", "") or ""


def analyze_one(name: str, transcript: str) -> dict:
    if not transcript or len(transcript) < 40:
        return {"ok": False, "reason": "transcript too short"}
    text = syn._llm([{"role": "user",
                      "content": ANALYSIS_PROMPT + "\n\nTRANSCRIPT:\n" + transcript[:6000]}])
    if text.startswith("__ERR__"):
        return {"ok": False, "error": text[7:]}
    s, e = text.find("{"), text.rfind("}") + 1
    if s < 0 or e <= s:
        return {"ok": False, "error": "no JSON", "raw": text[:200]}
    try:
        data = json.loads(text[s:e])
        data["source"] = name
        return {"ok": True, **data}
    except Exception as ex:
        return {"ok": False, "error": str(ex)[:120]}


def ingest(folder: str = None) -> list[dict]:
    folder = Path(folder or COMP_DIR)
    results = []
    for f in folder.iterdir():
        if f.suffix.lower() in (".mp4", ".mov", ".webm", ".mkv"):
            tr = _transcribe(str(f))
            r = analyze_one(f.stem, tr)
            results.append(r)
        elif f.suffix.lower() in (".txt", ".md", ".srt", ".vtt"):
            tr = f.read_text(errors="ignore")
            r = analyze_one(f.stem, tr)
            results.append(r)
    # append analyses
    with ANALYSIS_JSON.open("a") as fh:
        for r in results:
            if r.get("ok"):
                fh.write(json.dumps(r, default=str) + "\n")
    return results


def analyze_text(name: str, transcript: str) -> dict:
    r = analyze_one(name, transcript)
    if r.get("ok"):
        with ANALYSIS_JSON.open("a") as fh:
            fh.write(json.dumps(r, default=str) + "\n")
    return r


def build_profile() -> dict:
    """Merge all analyses into one style_profile.json our generator reads."""
    analyses = []
    if ANALYSIS_JSON.exists():
        for line in ANALYSIS_JSON.read_text().splitlines():
            try:
                analyses.append(json.loads(line))
            except Exception:
                pass
    if not analyses:
        return {"ok": False, "reason": "no analyses yet"}
    # aggregate the most common patterns
    from collections import Counter
    hooks = Counter(a.get("hook_type", "") for a in analyses)
    ctas = Counter(a.get("cta_style", "") for a in analyses)
    titles = [a.get("title_pattern", "") for a in analyses if a.get("title_pattern")]
    triggers = Counter(t for a in analyses for t in a.get("emotional_triggers", []))
    tactics = Counter(t for a in analyses for t in a.get("winning_tactics", []))
    structure = [a.get("structure", []) for a in analyses if a.get("structure")]
    profile = {
        "samples": len(analyses),
        "top_hook_types": hooks.most_common(3),
        "top_cta_style": ctas.most_common(2),
        "top_title_patterns": titles[:5],
        "top_emotional_triggers": triggers.most_common(5),
        "top_winning_tactics": tactics.most_common(8),
        "common_structure": structure[0] if structure else [],
        "updated": __import__("datetime").datetime.utcnow().isoformat(),
    }
    STYLE_PROFILE.write_text(json.dumps(profile, indent=2))
    return {"ok": True, "profile": profile}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--ingest", nargs="?", const=str(COMP_DIR), default=None)
    ap.add_argument("--text", default=None)
    ap.add_argument("--name", default="pasted")
    ap.add_argument("--build-profile", action="store_true")
    a = ap.parse_args()
    if a.ingest:
        print(json.dumps(ingest(a.ingest), default=str, indent=2))
    elif a.text:
        print(json.dumps(analyze_text(a.name, a.text), default=str, indent=2))
    elif a.build_profile:
        print(json.dumps(build_profile(), default=str, indent=2))
    else:
        print("use --ingest <dir> | --text '...' --name X | --build-profile")
