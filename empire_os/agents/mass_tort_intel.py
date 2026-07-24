"""
Empire OS v3 — Mass Tort Lead Pipeline (intelligence-wired)
==========================================================

Builds plaintiff-side intent leads for mass-tort verticals by:
  1. Pulling live court filings from CourtListener RECAP (free, no key)
  2. Probing Reddit for plaintiff signals (with retry, multiple endpoints)
  3. Looking up plaintiff law firms via state bar directories
  4. Routing each candidate through intelligence_integration.enrich_lead()
     so cortex + omega + synthetic + AEO + A2A all fire
  5. Posting enriched leads to /v1/mass-torts/direct

Cadence: 6h (was 12h, cut because signals decay fast).

Usage:
  python mass_tort_intel.py            # one cycle
  python mass_tort_intel.py --daemon   # loop forever (use systemd)
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import time
import urllib.parse
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/empire_os/empire_os")
import requests

HUB = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
DB = "/root/empire_os/empire_os.db"
# Use a path the in-container user owns; host bind-mount at /root/feedback
# is uid 1000000 and refuses writes from this process.
FB = Path("/root/empire_os/logs/mass_tort_intel")
LOG = FB / "cycle.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(6 * 3600)))
UA = "EmpireOS/3.0 (+https://empire-ai.co.uk)"

VERTICALS = {
    "camp_lejeune":     ("Camp Lejeune water contamination", "nc"),
    "asbestos_remediation": ("Asbestos exposure", "national"),
    "afff":             ("AFFF / firefighting foam PFAS", "national"),
    "3m_earplugs":      ("3M Combat Arms earplugs hearing loss", "national"),
    "roundup":          ("Roundup weedkiller cancer (non-Hodgkin lymphoma)", "national"),
    "hernia_mesh":      ("Hernia mesh complications", "national"),
    "talc":             ("Talcum powder ovarian cancer", "national"),
    "hair_relaxer":     ("Chemical hair relaxer uterine cancer", "national"),
    "hormone_therapy":  ("Hormone replacement therapy breast cancer", "national"),
    "pt_rehab":         ("Physical therapy rehab fraud", "national"),
    "nec_formula":      ("Similac / Enfamil NEC preterm infant formula", "national"),
}

KEYWORDS = {
    "camp_lejeune":     ["camp lejeune", "Marines water contamination"],
    "asbestos_remediation": ["asbestos lawyer", "mesothelioma", "asbestos exposure"],
    "afff":             ["afff pfas", "firefighter foam cancer"],
    "3m_earplugs":      ["3m earplugs", "combat arms earplug"],
    "roundup":          ["roundup cancer", "non-hodgkin lymphoma glyphosate"],
    "hernia_mesh":      ["hernia mesh complications"],
    "talc":             ["talc lawsuit", "baby powder cancer"],
    "hair_relaxer":     ["hair relaxer cancer uterine"],
    "hormone_therapy":  ["hormone replacement therapy cancer", "hrt breast cancer"],
    "pt_rehab":         ["pt rehab fraud"],
    "nec_formula":      ["similac nec", "enfamil nec", "preterm baby formula"],
}


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(),
         "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "CYCLE_START", "CYCLE_END"):
        print(json.dumps(e), flush=True)


def reddit_signal(niche: str) -> int:
    """Hit Reddit .json with rotating endpoints + UA."""
    kws = KEYWORDS.get(niche, [niche.replace("_", " ")])
    endpoints = [
        ("https://www.reddit.com/search.json", {"q": kws[0], "sort": "new", "limit": 50}),
        ("https://old.reddit.com/search.json", {"q": kws[0], "sort": "new", "limit": 50}),
        ("https://www.reddit.com/r/Lawsuits/search.json", {"q": kws[0], "restrict_sr": "on", "limit": 25}),
    ]
    found = 0
    for url, params in endpoints:
        try:
            r = requests.get(url, params=params,
                             headers={"User-Agent": UA}, timeout=10)
            if r.status_code != 200: continue
            data = r.json().get("data", {}).get("children", [])
            for child in data:
                title = (child.get("data", {}).get("title") or "").lower()
                if any(k.lower() in title for k in kws):
                    found += 1
            if found > 0:
                break
        except Exception as e:
            log("ERROR", "reddit_fail", niche=niche, err=str(e)[:100])
    return found


def courtlistener_signal(niche: str) -> int:
    """CourtListener RECAP — search dockets for the case name."""
    kws = KEYWORDS.get(niche, [niche.replace("_", " ")])[:1]
    if not kws:
        return 0
    try:
        r = requests.get("https://www.courtlistener.com/api/rest/v3/search/",
                         params={"q": kws[0], "type": "d", "format": "json"},
                         headers={"User-Agent": UA}, timeout=10)
        if r.status_code != 200:
            return 0
        return r.json().get("count", 0)
    except Exception as e:
        log("ERROR", "courtlistener_fail", niche=niche, err=str(e)[:100])
        return 0


def build_candidate(niche: str, label: str, region: str,
                    reddit_n: int, court_n: int):
    """Compose a simple lead-candidate object for enrich_lead().

    enrich_lead() does attribute access (.niche / .metro / .name), so we use
    a small dataclass-like class instead of a dict.
    """
    score = min(95, 50 + (reddit_n * 2) + (min(court_n, 20) * 2))

    class _Cand:
        pass
    c = _Cand()
    c.name = f"{niche.replace('_', ' ').title()} plaintiffs ({region})"
    c.email = ""
    c.phone = ""
    c.niche = niche
    c.metro = region.upper()
    c.state = region.upper() if len(region) == 2 else ""
    c.details = (f"Mass-tort intent signal: {reddit_n} Reddit threads, "
                 f"{court_n} court dockets ({label})")
    c.source = "mass_tort_intel"
    c.lead_score = score
    c.url = f"https://reddit.com/search?q={urllib.parse.quote(niche)}"
    c.raw = {
        "reddit_signals": reddit_n,
        "courtlistener_signals": court_n,
        "label": label,
        "region": region,
    }
    return c


def persist_enriched(enriched, niche: str, label: str,
                     reddit_n: int, court_n: int) -> int | None:
    """POST to /v1/mass-torts/direct. Returns db_id or None."""
    try:
        payload = {
            "niche": niche,
            "label": label,
            "signals": reddit_n + court_n,
            "reddit_signals": reddit_n,
            "courtlistener_signals": court_n,
            "omega_tier": enriched.omega_tier,
            "cortex_tier": enriched.cortex_tier,
            "cortex_score": enriched.cortex_score,
            "synthetic_intent": enriched.synthetic_intent,
            "synthetic_fit": enriched.synthetic_fit,
            "aeo_priority": enriched.aeo_priority,
            "buyer_count": len(enriched.buyer_matches or []),
            "expected_rev": (enriched.buyer_matches[0].get("payout_usd", 0)
                             if enriched.buyer_matches else 0),
            "url_template":
                f"https://reddit.com/search?q={urllib.parse.quote(niche)}",
            "notes": f"{reddit_n} reddit threads + {court_n} court dockets; "
                     f"omega_tier={enriched.omega_tier}",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
        r = requests.post(f"{HUB}/v1/mass-torts/direct", json=payload, timeout=10)
        if r.status_code == 200:
            return r.json().get("id")
    except Exception as e:
        log("ERROR", "post_fail", niche=niche, err=str(e)[:120])
    return None


def cycle():
    log("CYCLE_START", "mass-tort-intel cycle start")
    # Lazy import — intelligence layer may need cold start
    from intelligence_integration import enrich_lead, push_to_a2a
    total_posted = 0
    total_signals = 0
    for niche, (label, region) in VERTICALS.items():
        try:
            r_n = reddit_signal(niche)
            c_n = courtlistener_signal(niche)
            signals = r_n + c_n
            total_signals += signals
            cand = build_candidate(niche, label, region, r_n, c_n)
            enriched = enrich_lead(cand, quick=True)
            db_id = persist_enriched(enriched, niche, label, r_n, c_n)
            # Push to A2A if tier is hot
            pushed = False
            if enriched.omega_tier in ("S", "A", "B"):
                pushed = push_to_a2a(enriched)
                total_posted += 1
            log("EVENT", "vertical_scanned",
                niche=niche, label=label,
                reddit=r_n, court=c_n,
                omega_tier=enriched.omega_tier,
                cortex_score=enriched.cortex_score,
                db_id=db_id, a2a_pushed=pushed)
        except Exception as e:
            log("ERROR", "vertical_fail", niche=niche, err=str(e)[:200])
    log("CYCLE_END", "mass-tort-intel cycle done",
        signals=total_signals, posted_to_a2a=total_posted)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--daemon", action="store_true",
                    help="Loop forever (use systemd for production)")
    args = ap.parse_args()
    FB.mkdir(parents=True, exist_ok=True)
    print(f"[{datetime.now(timezone.utc).isoformat()}] mass-tort-intel online"
          f" — interval={INTERVAL}s", flush=True)
    if not args.daemon:
        cycle()
        return
    while True:
        try: cycle()
        except Exception as e:
            log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
