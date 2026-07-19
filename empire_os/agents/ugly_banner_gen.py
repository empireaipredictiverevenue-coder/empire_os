#!/usr/bin/env python3
"""
ugly_banner_gen.py — UGLY BANNER COPY GENERATOR (real asset output).

Extracts high-engagement, raw, pattern-interrupting social hooks from the
last30days artifacts (Reddit/HN/Polymarket titles with real engagement) and
writes them as ad-copy assets to a JSON file for human review.

This is the REAL version of the blueprint's ugly_banner_gen.py:
- No fictional /var/www/html/ads webroot — writes to /root/feedback/ads/.
- No Solana tracking pixel injection — just clean copy assets.
- Hooks come from REAL engagement data, not a fabricated social_comments feed.

Output asset shape:
  {"id": "ad_<niche>_<idx>", "headline": "<HOOK>", "style":
   "BACKGROUND_NEON_YELLOW_TEXT_BLACK_BOLD", "cta": "TAP TO CALL NOW",
   "source": "<reddit/hackernews/...>", "engagement": <int>, "url": "<src>"}
"""
import os, sys, json, glob, logging
sys.path.insert(0, os.path.dirname(__file__))

log = logging.getLogger("ugly_banner_gen")
FEED = "/root/feedback"
OUT_DIR = os.getenv("AD_ASSET_DIR", "/root/feedback/ads")
MIN_LEN, MAX_LEN = 10, 80
MIN_ENG = int(os.getenv("BANNER_MIN_ENG", "20"))


def _engagement_of(item: dict) -> int:
    eng = item.get("engagement", {})
    if isinstance(eng, dict):
        # real last30days engine schema
        return int(eng.get("score", 0) or 0) + int(eng.get("num_comments", 0) or 0)
    return int(eng or 0)


def extract_hooks() -> list:
    hooks = []
    for f in glob.glob(f"{FEED}/last30days_*.jsonl"):
        if "runs" in f:
            continue
        try:
            with open(f) as fh:
                for line in fh:
                    try:
                        r = json.loads(line)
                    except Exception:
                        continue
                    data = r.get("data") or {}
                    topic = r.get("topic", "general")
                    if not isinstance(data, dict):
                        continue
                    candidates = data.get("results") or []
                    if not isinstance(candidates, list):
                        candidates = []
                    if not candidates:  # legacy per-source lists
                        for src, rows in data.items():
                            if isinstance(rows, list):
                                candidates.extend(rows)
                    for it in candidates:
                        if not isinstance(it, dict):
                            continue
                        text = (it.get("title") or it.get("summary") or "")
                        text = text.strip()
                        eng = _engagement_of(it)
                        if MIN_LEN <= len(text) <= MAX_LEN and eng >= MIN_ENG:
                            hooks.append({
                                "id": f"ad_{topic}_{len(hooks)}",
                                "headline": text.upper().replace('"', "'"),
                                "style": "BACKGROUND_NEON_YELLOW_TEXT_BLACK_BOLD",
                                "cta": "TAP TO CALL NOW",
                                "source": it.get("source", "unknown"),
                                "engagement": eng,
                                "url": it.get("url", ""),
                                "niche": topic,
                            })
        except Exception:
            continue
    # de-dup by headline
    seen = {h["headline"]: h for h in hooks}
    return list(seen.values())


def run(dry_run: bool = False) -> dict:
    hooks = extract_hooks()
    if not dry_run:
        os.makedirs(OUT_DIR, exist_ok=True)
        out = os.path.join(OUT_DIR, "ugly_banners.json")
        with open(out, "w") as f:
            json.dump(hooks, f, indent=2)
    return {"hooks": len(hooks), "sample": hooks[:3]}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    print(json.dumps(run(dry_run=a.dry), indent=2))
