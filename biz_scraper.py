#!/usr/bin/env python3
"""
Empire OS — Free Business Scraper (NO paid APIs, NO proxies).
Finds businesses that need leads, per vertical. Feeds the lead DB + AEO directory.
Sources: Mojeek (no-key, unlimited) + OpenStreetMap Overpass (free).
Output: JSON lines of prospects {name, domain, niche, city, source}.
"""
import json, urllib.parse, urllib.request, subprocess, sys, re

MOJEEK = "https://www.mojeek.com/search?q={q}"
OVERPASS = "https://overpass-api.de/api/interpreter"

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"}

def _get(url, timeout=15):
    req = urllib.request.Request(url, headers=UA)
    return urllib.request.urlopen(req, timeout=timeout).read().decode("utf-8", "ignore")

def mojeek_biz(query, limit=20):
    """Free no-key business search. Primary: DuckDuckGo HTML (reliable parse).
    Falls back to Mojeek if DDG fails."""
    out = []
    # DuckDuckGo HTML endpoint (no key, no proxy)
    ddg = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    html = ""
    try:
        html = _get(ddg)
    except Exception as e:
        sys.stderr.write(f"ddg: {e}\n")
        try:
            html = _get(MOJEEK.format(q=urllib.parse.quote(query)))
        except Exception as e2:
            sys.stderr.write(f"mojeek: {e2}\n")
            return out
    # DDG result links: class="result__a" href="..."
    # directory/aggregator domains to EXCLUDE — we want the actual business, not Yelp
    DIRS = ("facebook","twitter","instagram","linkedin","youtube","duckduckgo",
            "yelp","bbb.org","yellowpages","angieslist","homeadvisor","thumbtack",
            "angi","trustpilot","manta","localservices","google","bing","mojeek",
            "wikipedia","yahoo","merchantcircle","cylex","brownbook","hotfrog")
    # DDG result links: class="result__a" href="..."  (Mojeek fallback handled below)
    # If DDG failed and we fell back to Mojeek, parse Mojeek's own markup.
    if "mojeek.com" in html and 'class="result__a"' not in html:
        import re as _re
        for m in _re.finditer(r'class="title"[^>]*href="([^"]+)"[^>]*>([^<]+)<', html):
            url, title = m.group(1), m.group(2)
            dom = urllib.parse.urlparse(url).netloc.replace("www.", "")
            if not dom or any(b in dom for b in DIRS):
                continue
            if any(k in title.lower() for k in ("near me","best 10","search results","category")):
                continue
            if dom and title.strip():
                out.append({"name": title.strip(), "domain": dom, "url": url})
            if len(out) >= limit:
                break
        return out
    for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)<', html):
        url, title = m.group(1), m.group(2)
        if "duckduckgo.com" in url:
            try:
                url = urllib.parse.parse_qs(urllib.parse.urlparse(url).query).get("uddg", [url])[0]
            except Exception:
                pass
        dom = urllib.parse.urlparse(url).netloc.replace("www.", "")
        if not dom:
            continue
        if any(b in dom for b in DIRS):
            continue
        # skip directory-style titles
        if any(k in title.lower() for k in ("near me","best 10","contractors near","category","search results")):
            continue
        if dom and title.strip():
            out.append({"name": title.strip(), "domain": dom, "url": url})
        if len(out) >= limit:
            break
    return out

def overpass_biz(city, category, limit=20):
    out = []
    # proper Overpass area query
    q = f'[out:json][timeout:25];area["name"="{city}"]["admin_level"~"4|6|8"]->.a;(node["shop"~"{category}",i](area.a);way["shop"~"{category}",i](area.a););out center {limit};'
    try:
        data = urllib.parse.urlencode({"data": q}).encode()
        req = urllib.request.Request(OVERPASS, data=data,
                                      headers={**UA, "Accept": "application/json"})
        j = json.loads(urllib.request.urlopen(req, timeout=30).read())
        for el in j.get("elements", []):
            tags = el.get("tags", {})
            name = tags.get("name")
            if name:
                out.append({"name": name, "domain": "", "city": city, "category": category})
            if len(out) >= limit:
                break
    except Exception as e:
        sys.stderr.write(f"overpass: {e}\n")
    return out

def scrape(vertical, city="", limit=20):
    """Top-level: return prospects for a vertical + optional city."""
    vert_disp = vertical.replace("_", " ")
    q = f'{vert_disp} contractors near me' if not city else f'{vert_disp} {city}'
    res = mojeek_biz(q, limit)
    if city:
        res += overpass_biz(city, vert_disp, limit)
    # dedupe by domain/name
    seen, uniq = set(), []
    for r in res:
        k = r.get("domain") or r.get("name")
        if k and k not in seen:
            seen.add(k); uniq.append(r)
    for r in uniq:
        r["niche"] = vertical
    return uniq[:limit]

def save(rows, path="/root/feedback/prospects.jsonl"):
    """Persist scraped prospects (append, dedupe by domain/name)."""
    import os
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existing = set()
    if os.path.exists(path):
        for line in open(path):
            try:
                existing.add(json.loads(line).get("domain") or json.loads(line).get("name"))
            except Exception:
                pass
    added = 0
    with open(path, "a") as f:
        for r in rows:
            k = r.get("domain") or r.get("name")
            if k and k not in existing:
                f.write(json.dumps(r) + "\n")
                existing.add(k); added += 1
    return added


if __name__ == "__main__":
    v = sys.argv[1] if len(sys.argv) > 1 else "roofing"
    c = sys.argv[2] if len(sys.argv) > 2 else ""
    rows = scrape(v, c, 15)
    added = save(rows)
    for r in rows:
        print(json.dumps(r))
    print(f"# scraped {len(rows)} prospects ({added} new) for {v} -> /root/feedback/prospects.jsonl", file=sys.stderr)
