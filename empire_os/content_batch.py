#!/usr/bin/env python3
"""content_batch.py — generate content for ALL AEO niches in one run.

Used for the initial footprint expansion (all 132 niches). Each niche:
generate -> save -> blog page -> sync -> video -> social queue.
Skips niches already in content_library (idempotent re-run safe).
"""
from __future__ import annotations
import os, sys, json, sqlite3, time, html, subprocess
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
BLOG_DIR = "/srv/aeo/blog"
HEARTBEATS = "/root/empire_os/config/agent_heartbeats.json"

import empire_os.aeo_seed as aeo
import empire_os.content_engine as ce
import empire_os.video_engine as ve


def _blog_html(niche, content):
    title = html.escape(content.get("title", niche))
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} — Empire AI</title>
<meta name="description" content="{html.escape(content.get('title',''))}">
</head><body style="background:#0a0a12;color:#e6f1ff;font-family:sans-serif;max-width:720px;margin:0 auto;padding:48px 24px;line-height:1.7">
<h1 style="background:linear-gradient(90deg,#00BFFF,#39FF14);-webkit-background-clip:text;-webkit-text-fill-color:transparent">{title}</h1>
<pre style="white-space:pre-wrap;font-family:inherit;color:#9fb6cc;font-size:16px">{html.escape(content.get('blog',''))}</pre>
<a href="https://empire-ai.co.uk/v1/pay/prod:AMBIENT-AI" style="display:inline-block;background:#39FF14;color:#0a0a12;font-weight:800;padding:14px 32px;border-radius:12px;text-decoration:none;margin-top:24px">⚡ Get Ambient AI — $49/mo</a>
</body></html>"""


def _done(niche):
    try:
        conn = sqlite3.connect(DB, timeout=30)
        n = conn.execute("SELECT count(*) FROM content_library WHERE niche=?", (niche,)).fetchone()[0]
        conn.close()
        return n > 0
    except Exception:
        return False


def main():
    niches = list(aeo.NICHES.keys())
    total = len(niches)
    done = 0
    for i, niche in enumerate(niches):
        if _done(niche):
            print(f"[{i+1}/{total}] skip {niche} (exists)")
            continue
        content = ce.generate(niche)
        ce.save(niche, content)
        os.makedirs(f"{BLOG_DIR}/{niche}", exist_ok=True)
        open(f"{BLOG_DIR}/{niche}/index.html", "w").write(_blog_html(niche, content))
        try:
            subprocess.run(["incus", "exec", "empire-hub", "--", "mkdir", "-p", f"/srv/aeo/blog/{niche}"], capture_output=True, timeout=20)
            subprocess.run(["incus", "file", "push", f"{BLOG_DIR}/{niche}/index.html", f"empire-hub/srv/aeo/blog/{niche}/index.html"], capture_output=True, timeout=30)
        except Exception as e:
            print(f"  sync warn: {e}")
        ve.render(niche, content.get("title", niche), content.get("social", [])[:5])
        social = content.get("social", [])
        qpath = "/root/empire_os/empire_os/social_queue.json"
        q = json.load(open(qpath)) if Path(qpath).exists() else []
        for s in social:
            q.append({"niche": niche, "text": s, "ts": time.time()})
        json.dump(q[-300:], open(qpath, "w"))
        done += 1
        print(f"[{i+1}/{total}] {niche} -> {content.get('source')} | blog+video+social")
    # heartbeat
    try:
        hb = json.load(open(HEARTBEATS)) if Path(HEARTBEATS).exists() else {}
    except Exception:
        hb = {}
    hb["content_pipeline"] = {"status": "OK", "ts": time.time(), "engine": "content", "batch": done}
    json.dump(hb, open(HEARTBEATS, "w"))
    print(f"BATCH DONE: generated {done} new niches ({total} total)")


if __name__ == "__main__":
    main()
