"""
Empire OS v3 — B2B scraper agent (enriched with headless browser).

1. OpenStreetMap Overpass — free, no block. Always works.
2. YellowPages — JS-rendered; use BrowserTool to bypass bot wall.
3. Google Maps local — browser-rendered fallback.

Posts to /v1/b2b/direct on hub (port 8081).
"""
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
import requests

HUB  = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
FB   = Path("/root/feedback")
LOG  = FB / "b2b_log.jsonl"
INTERVAL = int(os.environ.get("INTERVAL_SEC", str(6 * 3600)))
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
PARALLEL_METROS = os.environ.get("PARALLEL_METROS", "").split(",") if os.environ.get("PARALLEL_METROS") else []
MAX_TIMEOUT = int(os.environ.get("MAX_OVERPASS_TIMEOUT", "45"))
YP_URL = ""  # deprecated; replaced by google_scan (browser-rendered)

def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg, **fields}
    FB.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(json.dumps(e) + "\n")
    if level in ("ERROR", "EVENT"):
        print(json.dumps(e), flush=True)

def overpass_scan(metro: str, niche: str, limit: int = 10):
    q = f"""[out:json][timeout:20];area[name="{metro}"]->.a;nwr["name"]["{niche}"](area.a);out center {limit};"""
    try:
        r = requests.post(OVERPASS_URL, data={"data": q}, timeout=25)
        if r.status_code != 200: return []
        rows = []
        for el in r.json().get("elements", []):
            t = el.get("tags") or {}
            lat = el.get("lat") or (el.get("center") or {}).get("lat")
            lon = el.get("lon") or (el.get("center") or {}).get("lon")
            rows.append({
                "kind": "b2b",
                "name": t.get("name", ""),
                "phone": t.get("phone") or t.get("contact:phone", ""),
                "email": t.get("email") or t.get("contact:email", ""),
                "address": t.get("addr:full") or t.get("addr:street", ""),
                "city": t.get("addr:city", ""), "state": t.get("addr:state", ""),
                "postcode": t.get("addr:postcode", ""),
                "category": t.get("amenity") or t.get("shop") or t.get("office") or niche,
                "website": t.get("website", ""),
                "lat": lat, "lon": lon,
                "source": "openstreetmap",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })
        return rows
    except Exception as e:
        log("ERROR", "overpass_fail", metro=metro, niche=niche, err=str(e)[:150])
        return []

def bing_scan(term: str, loc: str, limit: int = 10):
    """JS-rendered Bing local results — headless browser bypasses Bing's bot wall."""
    from empire_os.browser_tool import get_tool
    try:
        import urllib.parse
        from bs4 import BeautifulSoup
        q = f"{term} in {loc}"
        url = "https://www.bing.com/search?q=" + urllib.parse.quote(q) + "&count=20"
        tool = get_tool()
        html = tool.get_html(url, wait="domcontentloaded", extra_sleep=2)
        if not html or html.startswith("<error>"):
            return []
        soup = BeautifulSoup(html, "html.parser")
        rows = []
        for card in soup.select("li.b_algo")[:limit]:
            name_el = card.select_one("h2 a")
            name = name_el.get_text(strip=True) if name_el else ""
            if not name or len(name) < 3: continue
            # Phone often in caption text
            caption = card.select_one("div.b_caption p, div.b_lineclamp")
            text = caption.get_text(" ", strip=True) if caption else ""
            import re
            m = re.search(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
            phone = m.group(0) if m else ""
            web = name_el.get("href", "") if name_el else ""
            rows.append({
                "kind": "b2b",
                "name": name, "phone": phone, "email": "",
                "address": "", "city": "", "state": "", "postcode": "",
                "category": term, "website": web, "lat": None, "lon": None,
                "source": "bing_browser",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            })
        return rows
    except Exception as e:
        log("ERROR", "bing_fail", term=term, loc=loc, err=str(e)[:150])
        return []

def hot_metros():
    try:
        r = requests.get(f"{HUB}/v1/swarm/lane-heat", timeout=8).json()
        heat = r.get("by_lane", {}) if isinstance(r, dict) else {}
        return sorted(heat.items(), key=lambda kv: -kv[1])[:10]
    except Exception: return []

def post(b):
    try: return requests.post(f"{HUB}/v1/b2b/direct", json=b, timeout=8).json().get("ok", False)
    except Exception: return False

def cycle():
    lanes = hot_metros()
    log("CYCLE_START", "b2b cycle", lanes=len(lanes))
    posted = 0
    for lane_key, _ in lanes:
        try: niche, metro = lane_key.split(":")
        except Exception: continue
        # 1) Overpass (free, reliable)
        for row in overpass_scan(metro, niche, 10):
            if not (row.get("phone") or row.get("email")): continue
            row["lane_key"] = lane_key
            if post(row): posted += 1
            if posted >= 25: break
        if posted >= 25: break
        # 2) Bing via browser (bypass JS block)
        for row in bing_scan(niche, metro, 10):
            if not (row.get("phone") or row.get("website")): continue
            row["lane_key"] = lane_key
            if post(row): posted += 1
            if posted >= 40: break
    log("CYCLE_END", "b2b complete", posted=posted, lanes=len(lanes))

if __name__ == "__main__":
    print(f"[{datetime.now(timezone.utc).isoformat()}] b2b-scraper starting - {INTERVAL}s", flush=True)
    time.sleep(45)
    while True:
        try: cycle()
        except Exception as e: log("ERROR", "cycle", err=str(e)[:200])
        time.sleep(INTERVAL)
