#!/usr/bin/env python3
"""scrape_contractors — pull REAL roofing/HVAC businesses via Serply (Google Maps).

Public-data lead sourcing for founder outreach. No fabrication: every row is a
real business Serply returned for a real query. Writes founder_leads.csv
(email,name,company,niche) for founder_outreach.py to queue.

Queries: "{niche} contractors near {metro}" for each metro/niche combo.
Caps total to stay within Serply quota (1 credit/query).

Usage:
    python3 scrape_contractors.py            # all metros x niches, capped
    python3 scrape_contractors.py --cap 40
"""
import os, sys, csv, json, time, argparse
sys.path.insert(0, "/root/empire_os")
SERPLY_KEY = os.environ.get("SERPLY_KEY", "")
os.environ.setdefault("SERPLY_KEY", SERPLY_KEY)
# pull from .env if not in shell
if not SERPLY_KEY:
    try:
        for ln in open("/root/empire_os/.env"):
            ln = ln.strip()
            if ln.startswith("SERPLY_KEY="):
                SERPLY_KEY = ln.split("=", 1)[1].strip().strip('"').strip("'")
                os.environ["SERPLY_KEY"] = SERPLY_KEY
    except Exception:
        pass

import requests

METROS = {
    "New York, NY": "NYC", "Los Angeles, CA": "LAX", "Chicago, IL": "CHI",
    "Houston, TX": "HOU", "Dallas, TX": "DFW", "Atlanta, GA": "ATL",
    "Miami, FL": "MIA", "Phoenix, AZ": "PHX",
}
NICHE_Q = {
    "residential_roofing": "roofing contractor",
    "commercial_roofing": "commercial roofer",
    "roof_repair": "roof repair",
    "hvac": "hvac contractor",
    "water_damage": "water damage restoration",
    "fire_damage": "fire damage restoration",
}
OUT = "/root/empire_os/founder_leads.csv"
API = "https://api.serply.io/api/v1/maps"


def search(q, geo, page=1):
    h = {"X-API-KEY": SERPLY_KEY, "Content-Type": "application/json",
          "X-Proxy-Location": "US"}
    params = {"q": q, "gl": "us", "hl": "en", "page": page}
    if geo:
        params["geo"] = geo
    r = requests.get(API, headers=h, params=params, timeout=30)
    if r.status_code != 200:
        return []
    data = r.json()
    # Serply maps returns 'results' or 'local_results'
    return data.get("results") or data.get("local_results") or data.get("organic_results") or []


def main(cap=40):
    if not SERPLY_KEY:
        print("NO SERPLY_KEY — cannot scrape. Set in .env.")
        return 0
    out = []
    seen = set()
    qcount = 0
    for metro, code in METROS.items():
        if len(out) >= cap:
            break
        for niche, qbase in NICHE_Q.items():
            if len(out) >= cap:
                break
            q = f"{qbase} in {metro}"
            try:
                res = search(q, geo=None)
            except Exception as e:
                print(f"  ERR {q}: {e}")
                res = []
            qcount += 1
            for r in res[:8]:
                name = r.get("name") or r.get("title") or ""
                site = r.get("website") or r.get("link") or ""
                addr = r.get("address") or r.get("formatted_address") or ""
                if not name or name.lower() in seen:
                    continue
                seen.add(name.lower())
                # email unknown from maps; leave blank -> we resolve separately
                out.append({
                    "email": "",  # filled by email_resolver pass
                    "name": "",
                    "company": name,
                    "niche": niche,
                    "metro": code,
                    "website": site,
                    "address": addr,
                })
            time.sleep(1.0)  # be polite to API
    # write CSV (founder_outreach expects email,name,company,niche)
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["email", "name", "company", "niche", "metro", "website", "address"])
        for o in out:
            w.writerow([o["email"], o["name"], o["company"], o["niche"], o["metro"], o["website"], o["address"]])
    print(f"Scraped {len(out)} REAL businesses across {qcount} Serply queries.")
    print(f"Wrote: {OUT}")
    print("NOTE: emails blank — run email_resolver.py to enrich from websites, OR")
    print("      hand-fill the email column, then founder_outreach.py queues them.")
    return len(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cap", type=int, default=40)
    a = ap.parse_args()
    main(cap=a.cap)
