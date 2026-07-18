#!/usr/bin/env python3
"""
Empire OS — AEO Subscription Refresh (SELLABLE PRODUCT, MRR line item).

Monthly re-optimization of AEO pages from search signal:
  (1) read currently published pages from container /srv/aeo/{tenant}
  (2) re-render them with refreshed keyword coverage (expand_questions + new verticals)
  (3) push back to the container via `incus file push --recursive`

Exposed to agents via MCP tool `aeo_refresh` (mcp_lead_server.py).
Settlement out-of-band (USDC, TS-5). This module is the DISCOVERY/SUPPLY refresh layer.

Run:
  python3 aeo_refresh.py --tenant empire          # one-shot refresh
  python3 aeo_refresh.py --tenant empire --loop   # sleep 86400 between refreshes
  python3 aeo_refresh.py --list-tenants           # show published tenants

Style: terse, stdlib, KISS/DRY. No credentials.
"""
import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

CONTAINER = "empire-hub"
SURFACE = "/srv/aeo"
STAGE_ROOT = os.environ.get("AEO_REFRESH_STAGE", "/tmp/aeo_refresh")
SLEEP = 86400

# New verticals to surface on every refresh for the empire tenant (search-signal expansion).
# Drop-in: any niche not yet published gets its own refreshed page.
NEW_VERTICALS = {
    "ai_search": ["AI search visibility + GEO optimization", "LLM citation capture",
                  "Structured-data authority pages"],
    "agentic_commerce": ["Autonomous agent buying/selling", "USDC-settled agent supply",
                         "Self-operating revenue loops"],
    "voice_search": ["Voice-assistant optimization", "Conversational intent capture",
                     "Featured-snippet + AEO dual coverage"],
}


# --------------------------------------------------------------------------- #
# container IO
# --------------------------------------------------------------------------- #
def _run(cmd, timeout=60):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def list_tenants():
    r = _run(["incus", "exec", CONTAINER, "--", "ls", SURFACE])
    if r.returncode != 0:
        return []
    return [t for t in r.stdout.split() if t]


def _niches_in(tenant):
    r = _run(["incus", "exec", CONTAINER, "--", "ls", f"{SURFACE}/{tenant}"])
    if r.returncode != 0:
        return []
    return [n for n in r.stdout.split() if n]


# --------------------------------------------------------------------------- #
# parse existing page -> render args (preserve content, refresh keywords)
# --------------------------------------------------------------------------- #
_TITLE_RE = re.compile(r"<title>(.*?) in (.*?) \|")
_META_RE = re.compile(r'content="(.*?)">', re.S)
_UL_RE = re.compile(r"<ul>(.*?)</ul>", re.S)
_LI_RE = re.compile(r"<li>(.*?)</li>")
_Q_SUM_RE = re.compile(r"<summary>(.*?)</summary>")
_AREA_RE = re.compile(r'"name": "(.*?)"\s*}\s*},\s*"provider"', re.S)


def _read_page(tenant, niche):
    """Pull published index.html and parse the render args it was built from."""
    src = f"{SURFACE}/{tenant}/{niche}/index.html"
    r = _run(["incus", "exec", CONTAINER, "--", "cat", src])
    if r.returncode != 0:
        return None
    html = r.stdout

    # city / areaServed
    m = _AREA_RE.search(html)
    city = m.group(1) if m else ""

    # tone: infer from description blurb (sharp/technical/warm/premium)
    tone = "sharp"
    if "caring, consistent" in html:
        tone = "warm"
    elif "Engineered" in html:
        tone = "technical"
    elif "definitive" in html or "white-glove" in html:
        tone = "premium"

    # selling points (li text under What We Deliver)
    pts = []
    um = _UL_RE.search(html)
    if um:
        pts = [x.strip() for x in _LI_RE.findall(um.group(1)) if x.strip()]

    # existing questions (summary text) — kept as the page's editorial FAQ
    questions = [q.strip() for q in _Q_SUM_RE.findall(html) if q.strip()]

    # CTA
    cm = re.search(r'class="cta"><p>(.*?)</p>', html, re.S)
    cta = cm.group(1).strip() if cm else ""

    return {"city": city, "tone": tone, "points": pts,
            "questions": questions, "cta": cta}


def _refresh_questions(niche, city, existing):
    """Refresh keyword coverage: expand_questions + merge any existing editorial Qs."""
    sys.path.insert(0, os.path.dirname(__file__))
    import aeo_generator as ag
    fresh = ag.expand_questions(niche, city)
    # dedupe-preserve: existing first (editorial intent), then fresh new coverage
    seen, out = set(), []
    for q in existing + fresh:
        k = q.lower().strip()
        if k and k not in seen:
            seen.add(k)
            out.append(q)
    return out


# --------------------------------------------------------------------------- #
# core refresh
# --------------------------------------------------------------------------- #
def refresh_tenant(tenant, add_verticals=True, surface_root=None):
    """
    Re-render + push all AEO pages for a tenant.
    Returns {"tenant", "refreshed":[...], "pushed":bool, "errors":[...]}.
    """
    sys.path.insert(0, os.path.dirname(__file__))
    import aeo_generator as ag

    tenant = re.sub(r"[^a-z0-9]+", "_", tenant.lower()).strip("_")
    # aeo_generator.render() already writes <root>/<tenant>/<niche>/index.html,
    # so stage at STAGE_ROOT and push STAGE_ROOT/<tenant> -> /srv/aeo/
    stage = Path(surface_root or STAGE_ROOT)
    if stage.exists():
        import shutil
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)
    root = stage  # render() adds the tenant subdir under this

    refreshed, errors = [], []

    # (1) existing niches
    niches = _niches_in(tenant)

    # (2) append new verticals not yet published (search-signal expansion)
    if add_verticals and tenant == "empire":
        for v in NEW_VERTICALS:
            if v not in niches:
                niches.append(v)

    for niche in niches:
        try:
            if niche in NEW_VERTICALS:
                # brand-new vertical — no existing page to read
                city = "United States"
                tone = "sharp"
                points = NEW_VERTICALS[niche]
                existing_q = []
                cta = "Explore on empire-ai.co.uk"
            else:
                meta = _read_page(tenant, niche)
                if meta is None:
                    errors.append(f"{niche}: page unreadable")
                    continue
                city = meta["city"]
                tone = meta["tone"]
                points = meta["points"]
                existing_q = meta["questions"]
                cta = meta["cta"]

            questions = _refresh_questions(niche, city, existing_q)
            ag.render(tenant, niche, city=city, tone=tone,
                      points=points, questions=questions, cta=cta,
                      surface_root=str(root))
            refreshed.append(niche)
        except Exception as e:
            errors.append(f"{niche}: {str(e)[:80]}")

    # (3) push back via incus file push --recursive
    # stage/tenant dir -> /srv/aeo/ (render already added the tenant subdir)
    pushed = False
    if refreshed:
        try:
            _run(["incus", "file", "push", "--recursive",
                  str(stage / tenant), f"{CONTAINER}{SURFACE}/"], timeout=120)
            pushed = True
        except Exception as e:
            errors.append(f"push: {str(e)[:80]}")

    return {"tenant": tenant, "refreshed": refreshed,
            "count": len(refreshed), "pushed": pushed, "errors": errors}


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="AEO Subscription Refresh")
    ap.add_argument("--tenant", default="empire")
    ap.add_argument("--loop", action="store_true", help="sleep 86400 between refreshes")
    ap.add_argument("--list-tenants", action="store_true")
    ap.add_argument("--no-new-verticals", action="store_true")
    args = ap.parse_args()

    if args.list_tenants:
        ts = list_tenants()
        print("tenants:", ", ".join(ts) or "(none)")
        return

    while True:
        res = refresh_tenant(args.tenant, add_verticals=not args.no_new_verticals)
        ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        print(f"[{ts}] aeo_refresh {res['tenant']}: "
              f"refreshed={res['count']} pushed={res['pushed']} "
              f"errors={len(res['errors'])}")
        for e in res["errors"]:
            print("   !", e)
        if not args.loop:
            break
        time.sleep(SLEEP)


if __name__ == "__main__":
    main()
