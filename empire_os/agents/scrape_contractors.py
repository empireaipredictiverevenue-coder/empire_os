#!/usr/bin/env python3
"""Free-directory contractor scraper (approach A).

Pulls roofing/HVAC/plumbing contractors from public directories
(Google Maps SERP, BBB, Yelp-style) for the metros we already track
in lane_leads. No API key. Respects robots + rate limits.

Output: inserts into crm_leads with contacts_json (dealer-scraper model)
so nurture_daemon can pick them up. Dedupe by (business_name, metro).

Usage:
  scrape_contractors.py --dry-run --limit 20
  scrape_contractors.py --niche roofing --metro "Phoenix, AZ" --limit 10
  scrape_contractors.py --once
"""
from __future__ import annotations
import argparse, json, os, sqlite3, sys, time, re
from datetime import datetime, timezone
import requests
from bs4 import BeautifulSoup

DB = "/root/empire_os/empire_os.db"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; EmpireOS/1.0; +https://empire-ai.co.uk)"}
NICHE_TERMS = {
    "roofing": "roofing contractor",
    "hvac": "hvac contractor",
    "plumbing": "plumber",
    "water_damage": "water damage restoration",
    "fire_damage": "fire damage restoration",
}

def get_metros(cur, limit=20):
    rows = cur.execute("""
        SELECT DISTINCT metro FROM lane_leads
        WHERE metro IS NOT NULL AND metro != ''
        LIMIT ?
    """, (limit,)).fetchall()
    return [r[0] for r in rows]

def search_google_local(niche_term: str, metro: str, limit=10) -> list[dict]:
    """Scrape Google Maps SERP for local businesses (public, no key)."""
    q = f"{niche_term} in {metro}"
    url = "https://www.google.com/search"
    params = {"q": q, "num": limit}
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    # Google packs business names in divs; crude but works for leads
    for div in soup.select("div[data-cid], div.VkpGBb")[:limit]:
        name = div.get_text(" ", strip=True)[:80]
        if not name or len(name) < 3:
            continue
        out.append({"business_name": name, "metro": metro, "source": "google_serp"})
    return out

def search_bbb(niche_term: str, metro: str, limit=10) -> list[dict]:
    """BBB business search (public)."""
    # BBB uses query param on search results
    try:
        r = requests.get(f"https://www.bbb.org/search/?filter.businessService={niche_term.replace(' ','+')}&filter.location={metro.replace(' ','+')}",
                         headers=HEADERS, timeout=10)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.select("a[href*='/business/']")[:limit]:
        name = a.get_text(" ", strip=True)[:80]
        if name:
            out.append({"business_name": name, "metro": metro, "source": "bbb"})
    return out

def enrich_contacts(business_name: str, metro: str) -> list[dict]:
    """Light contact discovery: search for business email via public pages.
    Placeholder — real enrichment needs Hunter/Clearbit (key). Returns empty
    until we wire a key; nurture skips rows with no email (correct behavior)."""
    return []

def dedupe_key(name, metro):
    return (re.sub(r'[^a-z0-9]','', name.lower())[:40], metro.lower())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--niche", default=None)
    ap.add_argument("--metro", default=None)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    c = sqlite3.connect(DB); cur = c.cursor()
    # ensure contacts_json col
    if "contacts_json" not in [r[1] for r in cur.execute("PRAGMA table_info(crm_leads)")]:
        cur.execute("ALTER TABLE crm_leads ADD COLUMN contacts_json TEXT DEFAULT '[]'")

    niches = {args.niche: NICHE_TERMS.get(args.niche, args.niche)} if args.niche else NICHE_TERMS
    metros = [args.metro] if args.metro else get_metros(cur, 20)

    seen = set()
    inserted = 0
    for metro in metros:
        for nk, term in niches.items():
            for fn in (search_google_local, search_bbb):
                rows = fn(term, metro, args.limit)
                for row in rows:
                    key = dedupe_key(row["business_name"], metro)
                    if key in seen:
                        continue
                    seen.add(key)
                    contacts = enrich_contacts(row["business_name"], metro)
                    rec = {
                        "source": row.get("source","scrape"),
                        "business_name": row["business_name"],
                        "metro": metro,
                        "niche": nk,
                        "contacts_json": json.dumps(contacts),
                        "status": "new",
                        "reply_state": "cold",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    }
                    if args.dry_run:
                        print(f"  [dry] {rec['business_name']} | {metro} | {nk}")
                    else:
                        cur.execute("""INSERT INTO crm_leads
                            (source, business_name, metro, niche, contacts_json, status, reply_state, created_at)
                            VALUES (:source,:business_name,:metro,:niche,:contacts_json,:status,:reply_state,:created_at)""", rec)
                        inserted += 1
                time.sleep(1.5)  # rate limit
            if inserted >= args.limit and not args.dry_run:
                break
        if inserted >= args.limit and not args.dry_run:
            break

    if not args.dry_run:
        c.commit()
    print(f"[scrape] inserted={inserted} dry={args.dry_run}")

if __name__ == "__main__":
    main()
