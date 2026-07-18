#!/usr/bin/env python3
"""
empire_lead_crawler.py — stealth B2B lead crawler (Apify-method, free).

Pipeline:
  1. Camoufox (anti-detect Firefox) renders a search engine SERP via Tor SOCKS
     -> defeats "are you a robot" + gives us a fresh rotating exit IP.
  2. Extract real business DOMAINS from the rendered results.
  3. For each domain, fetch /contact /about and scrape a real email
     (no fabrication — skip if none found).
  4. POST the prospect to the hub CRM (/v1/outreach/prospect/register).

Usage:
  ./empire_lead_crawler.py --verticals logistics warehouse --limit 40 --tor
"""
import argparse, hashlib, json, re, sys, time, os
sys.path.insert(0, "/root/empire_os")
from camoufox.sync_api import Camoufox

HUB = "http://10.118.155.218:8081"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:135.0) "
      "Gecko/20100101 Firefox/135.0")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
DOM_RE = re.compile(r'https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})')
BAD = ("google.com","bing.com","duckduckgo.com",".gov",".edu","wikipedia.org",
       "linkedin.com","facebook.com","youtube.com","w3.org","gstatic.com",
       "live.com","brave.com","microsoft.com","yahoo.com","pinterest.com",
       "instagram.com","twitter.com","reddit.com","yelp.com","tripadvisor.com")

VERTICALS = {
    "logistics":  ("logistics trucking freight company", "satellite_idle_watch,warehouse_asset"),
    "warehouse":  ("warehouse storage distribution company", "warehouse_asset,satellite_wastage"),
    "ai_team":    ("ai machine learning startup company", "skillspector_audit,hermes_framework"),
    "marketing":  ("marketing agency video production company", "opencut_studio,marketingskills,empire_templates"),
    "agency":     ("lead generation agency company", "empire_leads_engine,empire_templates"),
    "roofing":    ("roofing contractor company", "empire_leads_engine"),
    "hvac":       ("hvac contractor company", "empire_leads_engine"),
    "law":        ("law firm attorney practice", "empire_leads_engine"),
    "dental":     ("dental practice clinic", "empire_leads_engine"),
    "realestate": ("real estate brokerage agency", "empire_leads_engine"),
}

def new_circuit():
    try:
        import socket
        s = socket.socket(); s.settimeout(5)
        s.connect(("127.0.0.1", 9051))
        s.sendall(b"AUTHENTICATE\r\nSIGNEWNYM\r\n"); s.close()
    except Exception:
        pass
    time.sleep(4)

def search_domains(query, proxy, engine="brave"):
    if engine == "brave":
        url = f"https://search.brave.com/search?q={query}+contact+email"
    elif engine == "ddg":
        url = f"https://html.duckduckgo.com/html/?q={query}+contact+email"
    elif engine == "google":
        url = f"https://www.google.com/search?q={query}+contact+email&num=30"
    else:
        url = f"https://lite.duckduckgo.com/lite/?q={query}+contact+email"
    try:
        with Camoufox(headless=True,
                      proxy={"server": proxy} if proxy else None,
                      geoip=bool(proxy)) as browser:
            page = browser.new_page()
            page.goto(url, timeout=35000, wait_until="domcontentloaded")
            page.wait_for_timeout(3500)
            html = page.content()
        doms = set()
        for u in DOM_RE.findall(html):
            d = u.lower()
            if not d.endswith(BAD) and "." in d.split("/")[0]:
                doms.add(d.split("/")[0])
        return list(doms)
    except Exception as e:
        print(f"    [search err {engine}] {str(e)[:60]}")
        return []

def scrape_email(domain):
    for path in ("", "/contact", "/contact-us", "/about", "/get-in-touch"):
        try:
            with Camoufox(headless=True, geoip=False) as browser:
                page = browser.new_page()
                page.goto(f"https://{domain}{path}", timeout=15000,
                          wait_until="domcontentloaded")
                page.wait_for_timeout(1500)
                html = page.content()
            ems = [e for e in EMAIL_RE.findall(html)
                   if not e.lower().endswith((".png",".jpg",".svg",".webp",".gif"))]
            if ems:
                local = ems[0].split("@")[0].lower()
                if local in ("info","sales","contact","hello","admin","office","support"):
                    return ems[0]
                return ems[0]
        except Exception:
            continue
    return ""

def register(prospect):
    import urllib.request
    r = urllib.request.Request(
        f"{HUB}/v1/outreach/prospect/register",
        data=json.dumps(prospect).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        return urllib.request.urlopen(r, timeout=10).status == 200
    except Exception:
        return False

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
    "https://overpass.openstreetmap.ru/api/interpreter",
]

# US regions (bbox: south, west, north, east) — rotate for coverage
REGIONS = [
    (25.0, -97.0, 31.0, -91.0),   # TX gulf
    (29.5, -98.0, 33.0, -93.0),   # TX central
    (33.0, -118.5, 38.0, -113.0), # CA south
    (37.0, -122.5, 41.0, -117.0), # CA north
    (40.0, -74.5, 45.0, -69.0),   # NE corridor
    (41.0, -88.0, 45.0, -82.0),   # midwest
    (29.0, -82.0, 33.0, -76.0),   # FL
    (33.5, -84.5, 37.0, -78.0),   # SE
]

def overpass_domains(vertical, endpoints=None, regions=None):
    """OpenStreetMap Overpass — structured business data, no bot wall.
    Rotates endpoints + regions. Returns list of (domain, name)."""
    TAGS = {
        "logistics":  ['office="logistics"', 'shop="logistics"', 'industrial="logistics"'],
        "warehouse":  ['office="logistics"', 'building="warehouse"', 'amenity="storage"'],
        "ai_team":    ['office="it"', 'office="software"', 'office="computer"'],
        "marketing":  ['office="advertising"', 'office="marketing"', 'office="design"'],
        "agency":     ['office="consulting"', 'office="recruiter"'],
        "roofing":    ['craft="roofer"', 'trade="roofing"'],
        "hvac":       ['craft="hvac"', 'trade="hvac"'],
        "law":        ['office="lawyer"', 'office="notary"'],
        "dental":     ['office="dentist"', 'amenity="dentist"'],
        "realestate": ['office="real_estate_agent"', 'office="estate_agent"'],
    }
    eps = endpoints or OVERPASS_ENDPOINTS
    regs = regions or REGIONS
    import urllib.request
    out = []
    seen = set()
    for ep in eps:
        for bbox in regs:
            q = f'[out:json][timeout:40];('
            for t in TAGS.get(vertical, ['office="company"']):
                q += f'node[{t}]["website"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});'
                q += f'way[{t}]["website"]({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]});'
            q += ');out center 300;'
            try:
                req = urllib.request.Request(ep, data=q.encode(),
                    headers={"Content-Type": "text/plain"}, method="POST")
                d = json.loads(urllib.request.urlopen(req, timeout=45).read())
                for e in d.get("elements", []):
                    t = e.get("tags", {})
                    site = t.get("website", "").strip()
                    if not site:
                        continue
                    dm = DOM_RE.search(site)
                    if dm:
                        dml = dm.group(1).lower()
                        if dml not in seen:
                            seen.add(dml)
                            out.append((dml, t.get("name", dml)))
                if out:
                    return out  # first endpoint that yields wins
            except Exception:
                continue
    return out


def hunt(vertical, skus, limit, proxy, use_overpass=True, endpoints=None):
    print(f"[hunt] {vertical}: sourcing domains...")
    doms = []
    if use_overpass:
        doms = overpass_domains(vertical, endpoints=endpoints)
    if not doms:
        query, _ = VERTICALS[vertical]
        for eng in ("brave", "ddg", "google"):
            rd = search_domains(query, proxy, eng)
            doms += [(d, d) for d in rd]
            if doms:
                break
    pushed = 0
    for dm, name in doms:
        if pushed >= limit:
            break
        email = scrape_email(dm)
        if not email:
            continue
        pid = "b2b_" + hashlib.sha1(dm.encode()).hexdigest()[:12]
        prospect = {
            "prospect_id": pid,
            "business_name": name[:80],
            "email": email,
            "metro": "",
            "niche": "b2b",
            "phone": "",
            "source": f"camoufox_overpass:{vertical}",
            "score": 80,
            "url": f"skus:{skus}",
            "reply_state": "cold",
        }
        if register(prospect):
            pushed += 1
            print(f"  + {name[:30]:30} {dm:28} {email}")
        time.sleep(1.0)
    print(f"[hunt] {vertical}: pushed {pushed} real prospects")
    return pushed

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verticals", nargs="*", default=list(VERTICALS))
    ap.add_argument("--limit", type=int, default=30)
    ap.add_argument("--tor", action="store_true")
    ap.add_argument("--loop", action="store_true", help="run forever (daemon)")
    ap.add_argument("--endpoint", default=None, help="force one Overpass endpoint")
    a = ap.parse_args()
    proxy = "socks5://127.0.0.1:9050" if a.tor else None
    cycle = 0
    while True:
        cycle += 1
        total = 0
        for i, v in enumerate(a.verticals):
            if v not in VERTICALS:
                continue
            if a.tor and i > 0:
                new_circuit()
            total += hunt(v, VERTICALS[v][1], a.limit, proxy,
                          endpoints=[a.endpoint] if a.endpoint else None)
        print(f"[cycle {cycle}] {total} leads this pass @ {time.strftime('%H:%M:%S')}")
        if not a.loop:
            break
        time.sleep(120)  # let rate-limits reset between passes

if __name__ == "__main__":
    main()
