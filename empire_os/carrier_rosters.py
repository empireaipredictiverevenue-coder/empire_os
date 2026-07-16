"""Carrier DRP Roster Scraper — Blueprint v5 #1.

Scrapes insurance carrier "find a contractor" directories and stores
results in the carrier_rosters table. Falls back gracefully when
carriers block / require JS (documents the URL for later headless work).
"""
from __future__ import annotations

import json, os, time, sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests

HUB = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
FB = Path("/root/feedback")
LOG = Path("/tmp/carrier_roster_log.jsonl")
DB = "/root/empire_os/empire_os.db"

CARRIERS = {
    "statefarm":      ("State Farm",      "https://www.statefarm.com/claims/repair-service/find-contractor"),
    "allstate":       ("Allstate",         "https://www.allstate.com/claims/repair-center-locator"),
    "farmers":        ("Farmers",          "https://www.farmers.com/claims/repair-network"),
    "liberty_mutual": ("Liberty Mutual",   "https://www.libertymutual.com/claims/repair-network"),
    "usaa":           ("USAA",             "https://www.usaa.com/claims/contractor-directory"),
    "nationwide":     ("Nationwide",       "https://www.nationwide.com/claims/repair-network"),
    "travelers":      ("Travelers",        "https://www.travelers.com/claims/repair-network"),
    "progressive":    ("Progressive",      "https://www.progressive.com/claims/repair-network"),
}

def log(level, msg, **kw):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg, **kw}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)

def _ensure_tables():
    """Create carrier_rosters if missing."""
    conn = sqlite3.connect(DB)
    conn.execute("CREATE TABLE IF NOT EXISTS carrier_rosters ("
                 "id INTEGER PRIMARY KEY AUTOINCREMENT,"
                 "carrier TEXT NOT NULL,"
                 "company_name TEXT NOT NULL,"
                 "license_no TEXT,"
                 "city TEXT,"
                 "state TEXT,"
                 "zip TEXT,"
                 "service_areas TEXT,"
                 "specializations TEXT,"
                 "phone TEXT,"
                 "website TEXT,"
                 "scraped_at TEXT,"
                 "source_url TEXT)")
    conn.commit()
    conn.close()

def _scrape_generic(carrier_slug: str, url: str) -> list[dict]:
    """Generic scrape with retry + basic HTML parse.
    
    Most carrier directories require JS rendering, so this is a best-effort
    scrape that returns what we can get. When blocked, returns empty list
    with a log entry documenting the need for headless browser.
    """
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    for attempt in range(3):
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                log("INFO", "scrape_ok", carrier=carrier_slug, url=url, size=len(r.text))
                # Basic: extract business-like patterns from text
                # Most carriers require JS, so this is a stub that returns
                # the raw text for now — real parsing needs Playwright
                return [{"carrier": carrier_slug, "raw_snippet": r.text[:500],
                         "needs_js": True, "note": "JS-rendered directory, deferred to headless"}]
            elif r.status_code in (403, 404, 503):
                log("WARN", f"blocked_{r.status_code}", carrier=carrier_slug, url=url)
                return []
            time.sleep(1 * (attempt + 1))
        except requests.RequestException as e:
            log("WARN", "request_fail", carrier=carrier_slug, attempt=attempt, err=str(e)[:100])
            time.sleep(2 * (attempt + 1))
    log("ERROR", "scrape_failed_after_retries", carrier=carrier_slug, url=url)
    return []

def scrape_statefarm() -> list[dict]:
    """Scrape State Farm contractor directory."""
    label, url = CARRIERS["statefarm"]
    results = _scrape_generic("statefarm", url)
    return results

def scrape_allstate() -> list[dict]:
    label, url = CARRIERS["allstate"]; return _scrape_generic("allstate", url)
def scrape_farmers() -> list[dict]:
    label, url = CARRIERS["farmers"]; return _scrape_generic("farmers", url)
def scrape_liberty_mutual() -> list[dict]:
    label, url = CARRIERS["liberty_mutual"]; return _scrape_generic("liberty_mutual", url)
def scrape_usaa() -> list[dict]:
    label, url = CARRIERS["usaa"]; return _scrape_generic("usaa", url)
def scrape_nationwide() -> list[dict]:
    label, url = CARRIERS["nationwide"]; return _scrape_generic("nationwide", url)
def scrape_travelers() -> list[dict]:
    label, url = CARRIERS["travelers"]; return _scrape_generic("travelers", url)
def scrape_progressive() -> list[dict]:
    label, url = CARRIERS["progressive"]; return _scrape_generic("progressive", url)

SCRAPERS = {
    "statefarm": scrape_statefarm,
    "allstate": scrape_allstate,
    "farmers": scrape_farmers,
    "liberty_mutual": scrape_liberty_mutual,
    "usaa": scrape_usaa,
    "nationwide": scrape_nationwide,
    "travelers": scrape_travelers,
    "progressive": scrape_progressive,
}

def run_all(store: bool = True) -> dict[str, dict]:
    """Run all carrier scrapers and optionally store results in DB."""
    _ensure_tables()
    results: dict[str, dict] = {}
    for slug, scraper in SCRAPERS.items():
        try:
            entries = scraper()
            results[slug] = {"ok": True, "count": len(entries)}
            if store and entries:
                _store_entries(slug, entries)
        except Exception as e:
            results[slug] = {"ok": False, "error": str(e)[:200]}
            log("ERROR", "scraper_crash", carrier=slug, err=str(e)[:200])
    log("EVENT", "carrier_scrape_all_complete", results={k: v.get("count", v.get("error", 0)) for k, v in results.items()})
    return results

def _store_entries(carrier_slug: str, entries: list[dict]) -> int:
    """Store scraped entries in carrier_rosters table."""
    conn = sqlite3.connect(DB)
    inserted = 0
    now = datetime.now(timezone.utc).isoformat()
    url = CARRIERS.get(carrier_slug, ("", ""))[1]
    for e in entries:
        def _val(key, fallback=""):
            v = e.get(key)
            return v if v is not None else fallback
        conn.execute(
            "INSERT OR IGNORE INTO carrier_rosters "
            "(carrier, company_name, license_no, city, state, zip, "
            " service_areas, specializations, phone, website, scraped_at, source_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (carrier_slug,
             _val("company_name", _val("raw_snippet", "unknown")),
             _val("license_no"), _val("city"), _val("state"), _val("zip"),
             _val("service_areas"), _val("specializations"),
             _val("phone"), _val("website"), now, url))
        inserted += 1
    conn.commit()
    conn.close()
    return inserted

def list_rosters(carrier: Optional[str] = None, limit: int = 100) -> list[dict]:
    """Query carrier_rosters table."""
    conn = sqlite3.connect(DB)
    if carrier:
        rows = conn.execute(
            "SELECT id, carrier, company_name, license_no, city, state, "
            "       scraped_at FROM carrier_rosters WHERE carrier=? ORDER BY id DESC LIMIT ?",
            (carrier, limit)).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, carrier, company_name, license_no, city, state, "
            "       scraped_at FROM carrier_rosters ORDER BY id DESC LIMIT ?",
            (limit,)).fetchall()
    conn.close()
    return [{"id": r[0], "carrier": r[1], "company_name": r[2], "license_no": r[3],
             "city": r[4], "state": r[5], "scraped_at": r[6]} for r in rows]

def roster_stats() -> list[dict]:
    """Counts by carrier."""
    conn = sqlite3.connect(DB)
    rows = conn.execute(
        "SELECT carrier, COUNT(*) FROM carrier_rosters GROUP BY carrier ORDER BY carrier").fetchall()
    conn.close()
    return [{"carrier": r[0], "count": r[1]} for r in rows]

if __name__ == "__main__":
    print(json.dumps(run_all(), indent=2))
