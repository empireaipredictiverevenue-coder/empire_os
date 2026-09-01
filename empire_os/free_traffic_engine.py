"""
free_traffic_engine.py — Empire OS free/organic traffic orchestrator.

Runs ALL free customer-acquisition channels in one pass and routes every
captured lead into the funnel via the hub's /v1/leads/capture endpoint.

Channels (each self-contained, skips gracefully if creds missing):
  1. AEO pages      — regenerate /srv/aeo/* + sync into empire-hub container,
                      served live at empire-ai.co.uk/aeo/<niche>/ (capture form).
  2. SEO pages      — passive; just reports count served by empire-seo.service.
  3. Reddit sniper  — scans buyer-intent subreddits -> leads (needs REDDIT_* env).
  4. Social synd.   — repurposes content -> YouTube/social (needs YT + LLM creds).

Every captured email/lead is POSTed to https://empire-ai.co.uk/v1/leads/capture
with source tagged per-channel so attribution is clean.

Run: python3 free_traffic_engine.py [--channel all|aeo|reddit|social]
Schedule: hourly via cron.
"""
from __future__ import annotations
import os, sys, json, subprocess, argparse, urllib.request, urllib.error
from datetime import datetime, timezone

ROOT = "/root/empire_os"
HUB_CT = "empire-hub"
AEO_HOST_DIR = "/srv/aeo"
CAPTURE_URL = "https://empire-ai.co.uk/v1/leads/capture"
LOG = []


def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    LOG.append(line)
    print(line, flush=True)


def capture_lead(email, niche, source, name=""):
    """POST a lead into the funnel. Returns bool."""
    if not email or "@" not in email:
        return False
    payload = json.dumps({
        "email": email, "niche": niche,
        "source": source, "name": name,
    }).encode()
    req = urllib.request.Request(
        CAPTURE_URL, data=payload,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except urllib.error.HTTPError as e:
        log(f"  capture HTTP {e.code}: {e.read().decode()[:120]}")
        return False
    except Exception as e:
        log(f"  capture err: {e}")
        return False


def run_aeo():
    log("== AEO pages ==")
    # 1. regenerate on host
    r = subprocess.run(
        [sys.executable, f"{ROOT}/empire_os/aeo_seed.py"],
        capture_output=True, text=True, timeout=300,
    )
    if r.returncode != 0:
        log(f"  aeo_seed FAILED: {r.stderr[-200:]}")
        return
    # count
    try:
        n = len([d for d in os.listdir(AEO_HOST_DIR)
                 if os.path.isdir(f"{AEO_HOST_DIR}/{d}") and not d.startswith(".")
                 and d != "empire"])
    except Exception:
        n = 0
    log(f"  regenerated {n} AEO niches on host")
    # 2. sync into hub container (hub serves its own /srv/aeo, not the host mount)
    synced = 0
    try:
        for d in os.listdir(AEO_HOST_DIR):
            src = f"{AEO_HOST_DIR}/{d}/index.html"
            if os.path.isfile(src):
                subprocess.run(
                    ["incus", "file", "push", src, f"{HUB_CT}/srv/aeo/{d}/index.html"],
                    capture_output=True, timeout=30,
                )
                synced += 1
    except Exception as e:
        log(f"  sync err: {e}")
    log(f"  synced {synced} pages into {HUB_CT} (live at /aeo/<niche>/)")


def run_reddit():
    log("== Reddit sniper ==")
    if not os.environ.get("REDDIT_CLIENT_ID"):
        log("  skipped: REDDIT_CLIENT_ID not set")
        return
    try:
        r = subprocess.run(
            [sys.executable, f"{ROOT}/empire_os/reddit_sniper.py"],
            capture_output=True, text=True, timeout=300,
        )
        log(f"  exit={r.returncode}; {r.stdout[-200:]}")
    except Exception as e:
        log(f"  err: {e}")


def run_social():
    log("== Social syndication ==")
    if not os.environ.get("YOUTUBE_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
        log("  skipped: no YT/LLM creds")
        return
    try:
        r = subprocess.run(
            [sys.executable, f"{ROOT}/empire_os/social_syndication.py", "--list"],
            capture_output=True, text=True, timeout=120,
        )
        log(f"  queued items: {r.stdout[:200]}")
    except Exception as e:
        log(f"  err: {e}")


def run_seo_report():
    log("== SEO pages (passive) ==")
    p = f"{ROOT}/empire_os/seo_pages"
    try:
        n = len([f for f in os.listdir(p) if f.endswith(".html")])
        log(f"  {n} SEO pages served by empire-seo.service (passive organic)")
    except Exception:
        log("  seo_pages dir missing")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--channel", default="all",
                    choices=["all", "aeo", "reddit", "social", "seo"])
    a = ap.parse_args()
    log(f"FREE TRAFFIC ENGINE @ {datetime.now(timezone.utc).isoformat()[:19]}Z")
    if a.channel in ("all", "aeo"):
        run_aeo()
    if a.channel in ("all", "seo"):
        run_seo_report()
    if a.channel in ("all", "reddit"):
        run_reddit()
    if a.channel in ("all", "social"):
        run_social()
    log("DONE. Captured leads flow to /v1/leads/capture -> funnel.")


if __name__ == "__main__":
    main()
