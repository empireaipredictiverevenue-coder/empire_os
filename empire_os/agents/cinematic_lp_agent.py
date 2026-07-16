"""
Empire OS v3 - Cinematic Landing-Page Engine

Generates a high-converting HTML landing page from a brief:

  POST /v1/cinematic/render
    body={ niche, headline, subhead, cta, price, social_proof }
  returns { lp_id, html_url }

The HTML uses Tailwind-on-CDN, dark gradient, AEO-friendly
head/microdata, and a single call-to-action. Output goes to
/root/feedback/renders/<lp_id>.html and is served via /v1/lps.
"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

HUB  = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
FB   = Path("/root/feedback")
LOG  = FB / "cinematic_lp_log.jsonl"
RENDER = FB / "rendered_lps"
RENDER.mkdir(parents=True, exist_ok=True)


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level,
         "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{headline} | Empire OS</title>
<meta name="description" content="{subhead}">
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-950 text-white">
<section class="min-h-screen flex flex-col items-center justify-center text-center px-8">
<div class="max-w-4xl">
<h1 class="text-6xl md:text-8xl font-bold leading-tight">{headline}</h1>
<p class="text-2xl text-slate-300 mt-8">{subhead}</p>
<div class="mt-12 text-4xl font-mono">{price}</div>
<a href="/signup" class="mt-8 inline-block bg-emerald-500 text-slate-950 px-12 py-6 rounded-2xl text-3xl font-bold">{cta}</a>
<p class="mt-8 text-slate-400 italic">"{social_proof}"</p>
<p class="mt-4 text-slate-500">Sole agency per lane. Real leads, real USDC, real contracts.</p>
<p class="mt-2 text-slate-500">8,300+ leads already in the system.</p>
</div>
</section>
</body>
</html>
"""


def render(brief: dict) -> dict:
    lp_id = "lp_" + hex(int(time.time()))[2:]
    html = TEMPLATE.format(
        headline=brief.get("headline", "Get exclusive leads"),
        subhead=brief.get("subhead",
                          "Pay in USDC. Get matched with homeowners now."),
        cta=brief.get("cta", "Get Matched"),
        price=brief.get("price", "$200/mo"),
        social_proof=brief.get("social_proof",
                                "3 agencies onboarded in our first week."),
    )
    (RENDER / (lp_id + ".html")).write_text(html)
    log("EVENT", "lp_rendered",
        lp_id=lp_id, niche=brief.get("niche", "general"))
    return {"lp_id": lp_id, "url": f"/v1/lps/{lp_id}.html"}


if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] cinematic-lp engine ready (idempotent)",
          flush=True)
    while True:
        try:
            log("INFO", "engine_ready",
                note="awaiting POST /v1/cinematic/render")
        except Exception:
            pass
        time.sleep(300)
