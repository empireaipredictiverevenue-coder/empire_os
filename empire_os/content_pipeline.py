#!/usr/bin/env python3
"""content_pipeline.py — autonomous content→video→distribute engine.

Runs on cron (e.g. hourly). Each cycle:
  1. Pick next niche from aeo_seed.NICHES (round-robin via state)
  2. Generate blog + social + email (content_engine)
  3. Render branded short video (video_engine)
  4. Distribute:
       - write blog -> /srv/aeo/blog/<niche>/index.html (AEO-indexed)
       - append to social queue for social_autopilot to post
       - record in content_library for the brain
  5. Heartbeat to agent_heartbeats.json

Credential-free: OpenRouter if key present, else template. ffmpeg local video.
"""
from __future__ import annotations
import os, sys, json, sqlite3, time, html, subprocess
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
STATE = "/root/empire_os/logs/content_pipeline_state.json"
BLOG_DIR = "/srv/aeo/blog"
HEARTBEATS = "/root/empire_os/config/agent_heartbeats.json"

import empire_os.aeo_seed as aeo
import empire_os.content_engine as ce
import empire_os.video_engine as ve


def _blog_html(niche: str, content: dict) -> str:
    blog = content.get("blog", "").replace("\n", "\n  ")
    title = html.escape(content.get("title", niche))
    return f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{title} — Empire AI</title>
<meta name="description" content="{html.escape(content.get('title',''))}">
</head><body style="background:#0a0a12;color:#e6f1ff;font-family:sans-serif;max-width:720px;margin:0 auto;padding:48px 24px;line-height:1.7">
<h1 style="background:linear-gradient(90deg,#00BFFF,#39FF14);-webkit-background-clip:text;-webkit-text-fill-color:transparent">{title}</h1>
<pre style="white-space:pre-wrap;font-family:inherit;color:#9fb6cc;font-size:16px">{html.escape(content.get('blog',''))}</pre>
<a href="https://empire-ai.co.uk/v1/pay/prod:AMBIENT-AI" style="display:inline-block;background:#39FF14;color:#0a0a12;font-weight:800;padding:14px 32px;border-radius:12px;text-decoration:none;margin-top:24px">⚡ Get Ambient AI — $49/mo</a>
</body></html>"""


def _next_niche() -> str:
    keys = list(aeo.NICHES.keys())
    try:
        st = json.load(open(STATE))
        idx = st.get("idx", 0)
    except Exception:
        idx = 0
    niche = keys[idx % len(keys)]
    json.dump({"idx": (idx + 1) % len(keys)}, open(STATE, "w"))
    return niche


def cycle() -> dict:
    niche = _next_niche()
    content = ce.generate(niche)
    ce.save(niche, content)
    # blog page
    os.makedirs(f"{BLOG_DIR}/{niche}", exist_ok=True)
    open(f"{BLOG_DIR}/{niche}/index.html", "w").write(_blog_html(niche, content))
    # sync blog to container (AEO served from container /srv/aeo)
    try:
        subprocess.run(["incus", "exec", "empire-hub", "--", "mkdir", "-p",
                        f"/srv/aeo/blog/{niche}"], capture_output=True, timeout=20)
        subprocess.run(["incus", "file", "push", f"{BLOG_DIR}/{niche}/index.html",
                        f"empire-hub/srv/aeo/blog/{niche}/index.html"],
                       capture_output=True, timeout=30)
    except Exception as e:
        print(f"[content_pipeline] sync warn: {e}")
    # video
    vid = ve.render(niche, content.get("title", niche), content.get("social", [])[:5])
    # social queue
    social = content.get("social", [])
    try:
        q = json.load(open("/root/empire_os/empire_os/social_queue.json")) if Path("/root/empire_os/empire_os/social_queue.json").exists() else []
    except Exception:
        q = []
    for s in social:
        q.append({"niche": niche, "text": s, "ts": time.time()})
    json.dump(q[-200:], open("/root/empire_os/empire_os/social_queue.json", "w"))
    # heartbeat
    try:
        hb = json.load(open(HEARTBEATS)) if Path(HEARTBEATS).exists() else {}
    except Exception:
        hb = {}
    hb["content_pipeline"] = {"status": "OK", "ts": time.time(), "engine": "content"}
    json.dump(hb, open(HEARTBEATS, "w"))
    return {"niche": niche, "source": content.get("source"), "blog": True,
            "video": bool(vid), "social_queued": len(social)}


if __name__ == "__main__":
    print(json.dumps(cycle(), indent=2))
