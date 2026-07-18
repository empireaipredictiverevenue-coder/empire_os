"""
Empire OS v3 — Mass-Tort Scraper

Targets plaintiff-side intent for 11 mass-tort verticals already
indexed in our AEO tree:
  - camp_lejeune, asbestos_remediation, afff, 3m_earplugs,
    roundup, hernia_mesh, talc, hair_relaxer, hormone_therapy,
    pt_rehab, nec_formula

Each vertical has a known intake channel:
  - Plaintiff law-firm contact databases (public).
  - Mass-tort plaintiffs' Facebook groups (public).
  - Court filings at CourtListener (already wired).
  - Reddit communities (already wired via Reddit JSON).

Cadence: 12h. Output posted to /v1/mass-torts/direct.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

HUB   = os.environ.get("HUB_URL", "http://127.0.0.1:8000")
FB    = Path("/root/feedback")
LOG   = FB / "mass_tort_log.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(12 * 3600)))


VERTICALS = {
    "camp_lejeune":     "Camp Lejeune water contamination",
    "asbestos_remediation": "Asbestos exposure",
    "afff":             "AFFF / firefighting foam PFAS",
    "3m_earplugs":      "3M Combat Arms earplugs hearing loss",
    "roundup":          "Roundup weedkiller cancer (non-Hodgkin lymphoma)",
    "hernia_mesh":      "Hernia mesh complications",
    "talc":             "Talcum powder ovarian cancer",
    "hair_relaxer":     "Chemical hair relaxer uterine cancer",
    "hormone_therapy":  "Hormone replacement therapy breast cancer",
    "pt_rehab":         "Physical therapy rehab fraud",
    "nec_formula":      "Similac / Enfamil NEC preterm infant formula",
}


def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(),
         "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    print(json.dumps(e), flush=True)


def reddit_signal(niche: str) -> int:
    """Use Reddit .json public endpoint. Try r/Lawsuits + niche keywords."""
    keywords = {
        "camp_lejeune":     ["camp lejeune", "Marines water"],
        "asbestos_remediation": ["asbestos lawyer", "mesothelioma"],
        "afff":             ["afff pfas", "firefighter foam"],
        "3m_earplugs":      ["3m earplugs", "combat arms"],
        "roundup":          ["roundup cancer", "non-hodgkin lymphoma"],
        "hernia_mesh":      ["hernia mesh"],
        "talc":             ["talc lawsuit", "baby powder"],
        "hair_relaxer":     ["hair relaxer cancer"],
        "hormone_therapy":   ["hrt cancer", "hormone therapy"],
        "pt_rehab":         ["pt rehab fraud"],
        "nec_formula":      ["similac nec", "enfamil nec", "preterm baby formula"],
    }
    kw = keywords.get(niche, [niche.replace("_", " ")])
    url = "https://www.reddit.com/search.json"
    headers = {"User-Agent": "EmpireOS/3.0"}
    found = 0
    for query in kw[:2]:
        try:
            r = requests.get(url, params={"q": query, "sort": "new",
                                          "limit": 25},
                             headers=headers, timeout=10)
            if r.status_code != 200: continue
            data = r.json().get("data", {}).get("children", [])
            for child in data:
                title = child.get("data", {}).get("title", "")
                if any(k.lower() in title.lower() for k in kw):
                    found += 1
        except Exception as e:
            log("ERROR", "reddit_fail", niche=niche, err=str(e)[:100])
    return found


def cycle():
    log("CYCLE_START", "mass-tort cycle start")
    total = 0
    for niche, label in VERTICALS.items():
        try:
            n = reddit_signal(niche)
            log("EVENT", "vertical_probed",
                niche=niche, label=label, reddit_signals=n)
            total += n
            # POST to hub if we have any
            if n > 0:
                # heuristic - simulate finding attorney-firm landing page
                requests.post(f"{HUB}/v1/mass-torts/direct",
                              json={"niche": niche,
                                    "label": label,
                                    "signals": n,
                                    "url_template":
                                        f"https://reddit.com/search?q={niche.replace('_','+')}",
                                    "notes": f"{n} reddit threads; check Court Listener",
                                    "scraped_at": datetime.now(timezone.utc).isoformat()},
                              timeout=8)
        except Exception as e:
            log("ERROR", "vertical_fail", niche=niche, err=str(e)[:120])
    log("CYCLE_END", "mass-tort cycle done", signals=total)


if __name__ == "__main__":
    FB.mkdir(parents=True, exist_ok=True)
    print(f"[{datetime.now(timezone.utc).isoformat()}] mass-tort-agent online — {INTERVAL}s",
          flush=True)
    # grace + first cycle
    time.sleep(45)
    while True:
        try: cycle()
        except Exception as e:
            log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
