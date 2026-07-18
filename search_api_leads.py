#!/usr/bin/env python3
"""
search_api_leads.py — scalable B2B lead crawler via Serper.dev (Google Search API).

Pipeline (Apify-method, free, owned):
  1. Serper.dev returns Google organic results (no CAPTCHA, structured).
  2. Extract real business DOMAINS from result links.
  3. Camoufox scrapes each domain's /contact /about for a real email.
  4. POST prospect to hub CRM (/v1/outreach/prospect/register).

Scales horizontally: run multiple verticals in parallel; Serper free tier = 2500/mo.
Fallback to Overpass (empire_lead_crawler.py) when Serper credits exhaust.

Usage:
  ./search_api_leads.py --verticals logistics warehouse --limit 40 --loop
"""
import argparse, hashlib, json, os, re, sys, time, socket
socket.setdefaulttimeout(8)
sys.path.insert(0, "/root/empire_os")
# load .env so SERPER_KEY is available
for _ln in open("/root/empire_os/.env"):
    _ln = _ln.strip()
    if _ln and "=" in _ln and not _ln.startswith("#"):
        _k, _v = _ln.split("=", 1)
        os.environ.setdefault(_k.strip(), _v.strip().strip('"').strip("'"))
try:
    from camoufox.sync_api import Camoufox  # noqa: F401 (optional, not used in fast path)
except Exception:
    Camoufox = None

HUB = "http://10.118.155.218:8000"
DOM_RE = re.compile(r'https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})')
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
BAD = ("google.com","bing.com","duckduckgo.com",".gov",".edu","wikipedia.org",
       "linkedin.com","facebook.com","youtube.com","yelp.com","scribd.com",
       "pinterest.com","instagram.com","twitter.com","reddit.com","datacaptive.com",
       "yellowpages.com","tripadvisor.com","pdf")

VERTICALS = {
    "logistics":  ("logistics trucking freight company contact email", "satellite_idle_watch,warehouse_asset"),
    "warehouse":  ("warehouse storage distribution company contact email", "warehouse_asset,satellite_wastage"),
    "ai_team":    ("ai machine learning startup company contact email", "skillspector_audit,hermes_framework"),
    "marketing":  ("marketing agency video production company contact email", "opencut_studio,marketingskills,empire_templates"),
    "agency":     ("lead generation agency company contact email", "empire_leads_engine,empire_templates"),
    "roofing":    ("roofing contractor company contact email", "empire_leads_engine"),
    "hvac":       ("hvac contractor company contact email", "empire_leads_engine"),
    "law":        ("law firm attorney practice contact email", "empire_leads_engine"),
    "dental":     ("dental practice clinic contact email", "empire_leads_engine"),
    "realestate": ("real estate brokerage agency contact email", "empire_leads_engine"),
    "plumbing":   ("plumbing contractor company contact email", "empire_leads_engine"),
    "solar":      ("solar installation company contact email", "empire_leads_engine"),
    "medspa":     ("med spa aesthetic clinic contact email", "empire_leads_engine"),
    "staffing":   ("staffing recruitment agency contact email", "empire_leads_engine"),
    "saas":       ("saas software company contact email", "skillspector_audit,hermes_framework"),
    "insurance":  ("insurance agency broker contact email", "empire_leads_engine"),
    "accounting": ("accounting firm cpa contact email", "empire_leads_engine"),
    "construction":("construction general contractor contact email", "empire_leads_engine"),
    "electrician":("electrician contractor company contact email", "empire_leads_engine"),
    "landscaping":("landscaping company contact email", "empire_leads_engine"),
    "cleaning":   ("commercial cleaning janitorial company contact email", "empire_leads_engine"),
    "security":   ("security guard company contact email", "empire_leads_engine"),
    "pest":       ("pest control company contact email", "empire_leads_engine"),
    "trucking":   ("trucking company owner operator contact email", "satellite_idle_watch"),
    "manufacturing":("manufacturing company factory contact email", "warehouse_asset"),
    "fintech":    ("fintech company contact email", "skillspector_audit"),
    "ecommerce":  ("ecommerce store company contact email", "empire_templates"),
    "chiropractic":("chiropractic clinic contact email", "empire_leads_engine"),
    "veterinary": ("veterinary clinic animal hospital contact email", "empire_leads_engine"),
    "physiotherapy":("physiotherapy clinic contact email", "empire_leads_engine"),
    "auto":       ("auto repair shop dealership contact email", "empire_leads_engine"),
    "tire":       ("tire shop company contact email", "empire_leads_engine"),
    "title":      ("title company real estate closing contact email", "empire_leads_engine"),
    "mortgage":   ("mortgage broker lender contact email", "empire_leads_engine"),
    "property_mgmt":("property management company contact email", "empire_leads_engine"),
    "restaurant": ("restaurant group franchise contact email", "empire_leads_engine"),
    "hotel":      ("hotel hospitality company contact email", "empire_leads_engine"),
    "retail":     ("retail store chain company contact email", "empire_leads_engine"),
    "fitness":    ("gym fitness studio contact email", "empire_leads_engine"),
    "photography":("photography studio company contact email", "opencut_studio"),
    "webdev":     ("web development agency contact email", "empire_templates"),
    "seo":        ("seo agency company contact email", "empire_leads_engine"),
    "consulting": ("business consulting firm contact email", "empire_leads_engine"),
    "recruiter":  ("executive recruiter search firm contact email", "empire_leads_engine"),
    "courier":    ("courier delivery service company contact email", "satellite_idle_watch"),
    "waste":      ("waste management junk removal company contact email", "empire_leads_engine"),
    "equipment":  ("heavy equipment rental company contact email", "warehouse_asset"),
    "flooring":   ("flooring company contact email", "empire_leads_engine"),
    "painting":   ("painting contractor company contact email", "empire_leads_engine"),
    "pool":       ("pool service company contact email", "empire_leads_engine"),
    "tree":       ("tree service company contact email", "empire_leads_engine"),
    "excavation": ("excavation landscaping company contact email", "empire_leads_engine"),
    "fencing":    ("fence company contact email", "empire_leads_engine"),
    "concrete":   ("concrete contractor company contact email", "empire_leads_engine"),
    "glass":      ("glass window company contact email", "empire_leads_engine"),
    "cabinet":    ("cabinet kitchen company contact email", "empire_leads_engine"),
    "countertop": ("countertop company contact email", "empire_leads_engine"),
}

def serper_domains(query, key, n=20):
    import urllib.request
    req = urllib.request.Request(
        "https://google.serper.dev/search",
        data=json.dumps({"q": query, "num": n}).encode(),
        headers={"X-API-KEY": key, "Content-Type": "application/json"}, method="POST")
    d = {}
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=20).read())
    except Exception as e:
        print(f"    [serper err] {str(e)[:60]}")
        return [], None
    doms = _extract(d.get("organic", []))
    return doms, d.get("credits_left")

def serpapi_domains(query, key, n=20):
    """SerpAPI fallback (Google engine)."""
    import urllib.request, urllib.parse
    url = (f"https://serpapi.com/search.json?engine=google"
           f"&q={urllib.parse.quote(query)}&num={n}&api_key={key}")
    try:
        d = json.loads(urllib.request.urlopen(url, timeout=20).read())
    except Exception as e:
        print(f"    [serpapi err] {str(e)[:60]}")
        return []
    return _extract(d.get("organic_results", []))

def serpstack_search(query, key, n=20):
    """Serpstack — Google SERP JSON via access_key param."""
    import urllib.request, urllib.parse
    url = (f"https://api.serpstack.com/search?access_key={key}"
           f"&query={urllib.parse.quote(query)}&num={n}")
    try:
        d = json.loads(urllib.request.urlopen(url, timeout=20).read())
    except Exception as e:
        print(f"    [serpstack err] {str(e)[:60]}")
        return []
    return _extract(d.get("organic_results", []))

def serply_search(query, key, n=20):
    """Serply.io — Google SERP JSON via X-API-KEY header."""
    import urllib.request, urllib.parse
    req = urllib.request.Request(
        f"https://api.serply.io/v1/search?q={urllib.parse.quote(query)}&num={n}",
        headers={"X-API-KEY": key, "Content-Type": "application/json"}, method="GET")
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=20).read())
    except Exception as e:
        print(f"    [serply err] {str(e)[:60]}")
        return []
    out = []
    for r in d.get("results", []) if isinstance(d.get("results"), list) else []:
        link = r.get("link") or r.get("url") or ""
        m = DOM_RE.search(link)
        if m:
            dm = m.group(1).lower()
            if not dm.endswith(BAD) and dm not in out:
                out.append(dm)
    return out

def mojeek_domains(query, n=20):
    """Search: Serply (primary) → Serper → Tor/DDG."""
    import time, re, urllib.request, urllib.parse, json
    API = "https://api.serply.io/v1/search/q="
    KEY = os.environ.get("SERPLY_KEY", os.environ.get("SERLY_KEY", ""))
    out = []

    # 1) Serply
    if KEY:
        try:
            req = urllib.request.Request(API + urllib.parse.quote(query),
                headers={"X-API-KEY": KEY, "User-Agent": "EmpireOS/1.0"})
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read().decode())
            for r in data.get("results", []):
                dm = DOM_RE.search(r.get("link", ""))
                if dm:
                    d = dm.group(1).lower()
                    if not any(d.endswith(b) for b in BAD) and d not in out:
                        out.append(d)
            if out:
                return out[:n]
        except Exception as e:
            print(f"    [serply err] {str(e)[:50]}")

    # 2) Fallback: Serper API
    api_key = os.environ.get("SERPER_KEY", "")
    if api_key:
        try:
            req = urllib.request.Request(
                "https://google.serper.dev/search",
                data=json.dumps({"q": query, "num": min(n, 10)}).encode(),
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read().decode())
            for r in data.get("organic", []):
                dm = DOM_RE.search(r.get("link", ""))
                if dm:
                    d = dm.group(1).lower()
                    if not any(d.endswith(b) for b in BAD) and d not in out:
                        out.append(d)
            if out:
                return out[:n]
        except Exception as e:
            print(f"    [serper err] {str(e)[:50]}")

    # 3) Last resort: Tor/DDG with retry
    UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " \
         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    html = None
    for attempt in range(4):
        try:
            import requests as _req
            proxies = {"http": "socks5h://127.0.0.1:9050",
                        "https": "socks5h://127.0.0.1:9050"}
            resp = _req.get(url, headers={"User-Agent": UA}, proxies=proxies, timeout=25)
            if len(resp.text) > 8000 and 'class="result__a"' in resp.text:
                html = resp.text
                break
        except Exception:
            pass
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            raw = urllib.request.urlopen(req, timeout=15).read().decode("utf-8", "ignore")
            if len(raw) > 5000 and 'class="result__a"' in raw:
                html = raw
                break
        except Exception:
            pass
        time.sleep(3)
    if html:
        for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"', html):
            l = m.group(1)
            if "duckduckgo.com" in l and "uddg" in l:
                try:
                    l = urllib.parse.parse_qs(
                        urllib.parse.urlparse(l).query).get("uddg", [l])[0]
                except Exception:
                    pass
            dm = DOM_RE.search(l)
            if dm:
                d = dm.group(1).lower()
                if not any(d.endswith(b) for b in BAD) and d not in out:
                    out.append(d)
            if len(out) >= int(n):
                break
    time.sleep(0.3)
    return out[:n]

def _extract(results):
    doms = []
    for r in results if isinstance(results, list) else []:
        link = r.get("link", "")
        m = DOM_RE.search(link)
        if m:
            dm = m.group(1).lower()
            if not dm.endswith(BAD) and dm not in doms:
                doms.append(dm)
    return doms

def parallel_search(query, key, n=15):
    """Parallel.ai — returns (domains, {domain:email}) from URLs + inline excerpts."""
    import urllib.request
    req = urllib.request.Request(
        "https://api.parallel.ai/v1beta/search",
        data=json.dumps({"objective": query, "search_queries": [query],
                         "max_results": n}).encode(),
        headers={"x-api-key": key, "Content-Type": "application/json"}, method="POST")
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=30).read())
    except Exception as e:
        print(f"    [parallel err] {str(e)[:60]}")
        return [], {}
    doms, direct = [], {}
    for r in d.get("results", []):
        url = r.get("url", "")
        m = DOM_RE.search(url)
        if not m:
            continue
        dm = m.group(1).lower()
        if dm.endswith(BAD):
            continue
        if dm not in doms:
            doms.append(dm)
        # mine excerpts for an inline email on that domain (skip scrape)
        blob = " ".join(r.get("excerpts", [])) + " " + r.get("title", "")
        for e in EMAIL_RE.findall(blob):
            el = e.lower()
            if el.endswith((".png",".jpg",".svg",".webp",".gif")):
                continue
            # prefer emails matching the result domain root
            root = dm.replace("www.", "")
            if root.split(".")[0] in el or dm in direct and False:
                direct.setdefault(dm, e)
    return doms, direct

def scrape_email(domain):
    # urllib-only, hard timeout; skip Camoufox (too slow for volume)
    import urllib.request, socket
    UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}
    for path in ("/contact", "/contact-us", ""):
        try:
            req = urllib.request.Request(f"https://{domain}{path}", headers=UA)
            html = urllib.request.urlopen(req, timeout=6).read(500000).decode("utf-8", "ignore")
            ems = [e for e in EMAIL_RE.findall(html)
                   if not e.lower().endswith((".png",".jpg",".svg",".webp",".gif"))
                   and not e.lower().startswith(("example@","email@","name@","you@","your@"))]
            if ems:
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

def hunt(vertical, skus, limit, key, serpapi_key="", parallel_key="",
         serply_key="", serpstack_key="", use_free=True):
    query, _ = VERTICALS[vertical]
    print(f"[hunt] {vertical}: searching (5 APIs + Mojeek)...")
    doms, credits, src = ([], None, {})
    def _add(lst, tag):
        for dm in lst:
            if dm not in doms:
                doms.append(dm); src[dm] = tag
    if key:
        d, credits = serper_domains(query, key)
        _add(d, "serper")
        if credits is not None:
            print(f"    serper credits left: {credits}")
    direct = {}
    if parallel_key:
        pdoms, direct = parallel_search(query, key=parallel_key)
        _add(pdoms, "parallel")
    if serpapi_key and len(doms) < limit * 2:
        _add(serpapi_domains(query, serpapi_key), "serpapi")
    if serply_key:
        _add(serply_search(query, serply_key), "serply")
    if serpstack_key:
        _add(serpstack_search(query, serpstack_key), "serpstack")
    if use_free:
        _add(mojeek_domains(query), "mojeek")
    print(f"    -> {len(doms)} domains ({len(direct)} with inline email)")
    pushed = 0
    for dm in doms:
        if pushed >= limit:
            break
        email = direct.get(dm) or scrape_email(dm)
        if not email:
            continue
        pid = "b2b_" + hashlib.sha1(dm.encode()).hexdigest()[:12]
        prospect = {
            "prospect_id": pid,
            "business_name": dm,
            "email": email,
            "metro": "",
            "niche": "b2b",
            "phone": "",
            "source": f"{src.get(dm, 'serper')}:{vertical}",
            "score": 85,
            "url": f"skus:{skus}",
            "reply_state": "cold",
        }
        if register(prospect):
            pushed += 1
            print(f"  + {dm:32} {email}")
        time.sleep(0.8)
    print(f"[hunt] {vertical}: pushed {pushed} real prospects")
    return pushed

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--verticals", nargs="*", default=list(VERTICALS))
    ap.add_argument("--limit", type=int, default=40)
    ap.add_argument("--loop", action="store_true")
    a = ap.parse_args()
    key = os.environ.get("SERPER_KEY", "")
    serpapi_key = os.environ.get("SERPAPI_KEY", "")
    parallel_key = os.environ.get("PARALLEL_KEY", "")
    serply_key = os.environ.get("SERPLY_KEY", "")
    serpstack_key = os.environ.get("SERPSTACK_KEY", "")
    if not (key or serpapi_key or parallel_key or serply_key or serpstack_key):
        print("no search API key set"); return
    cycle = 0
    while True:
        cycle += 1
        total = 0
        for v in a.verticals:
            if v not in VERTICALS:
                continue
            total += hunt(v, VERTICALS[v][1], a.limit, key, serpapi_key,
                          parallel_key, serply_key, serpstack_key)
        print(f"[cycle {cycle}] {total} leads this pass @ {time.strftime('%H:%M:%S')}")
        if not a.loop:
            break
        time.sleep(60)

if __name__ == "__main__":
    main()
