#!/usr/bin/env python3
"""
Empire OS — AEO Citation Checker (Phase 5 proof layer).
Measures whether LLMs/search engines actually CITE our published assets.
Feeds OKF O4-KR1 (20+ cited assets).

Method (free, no paid API):
- For each vertical we published an AEO asset for, run a probe query
  via the free search sources (Mojeek no-key + Serper/Parallel quota).
- Check if empire-ai.co.uk / our asset domains appear in the top results.
- Citation = our domain surfaced for the intent query we targeted.

Writes /root/feedback/aeo_citations.json
"""
import json, os, time, sys, subprocess

FEEDBACK = "/root/feedback"
OUT = f"{FEEDBACK}/aeo_citations.json"
INFLUENCE = f"{FEEDBACK}/influence.json"

VERTICAL_QUERIES = {
    "logistics": "best logistics b2b leads provider",
    "roofing": "roofing contractor lead generation service",
    "hvac": "hvac company qualified leads",
    "general_contractor": "general contractor project leads",
    "plumbing": "plumber local lead generation",
}
OUR_DOMAINS = ["empire-ai.co.uk", "empire_os", "empireaipredictiverevenue"]


def _search(query, limit=10):
    """Search: Serply (primary) → Serper → Tor/DDG."""
    import urllib.request, urllib.parse, re, time, os, json
    # 1) Serply
    serply_key = os.environ.get("SERPLY_KEY", os.environ.get("SERLY_KEY", ""))
    if serply_key:
        try:
            req = urllib.request.Request(
                "https://api.serply.io/v1/search/q=" + urllib.parse.quote(query),
                headers={"X-API-KEY": serply_key, "User-Agent": "EmpireOS/1.0"})
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read().decode())
            out = [{"url": r.get("link", ""), "title": r.get("title", "")}
                   for r in data.get("results", []) if r.get("link")]
            if out:
                return out[:limit]
        except Exception as e:
            return [{"error": f"serply: {str(e)[:50]}"}]

    # 2) Serper (fallback)
    api_key = os.environ.get("SERPER_KEY", "")
    if api_key:
        try:
            req = urllib.request.Request(
                "https://google.serper.dev/search",
                data=json.dumps({"q": query, "num": min(limit, 10)}).encode(),
                headers={"X-API-KEY": api_key, "Content-Type": "application/json"})
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read().decode())
            out = [{"url": r.get("link", ""), "title": r.get("title", "")}
                   for r in data.get("organic", []) if r.get("link")]
            if out:
                return out[:limit]
        except Exception as e:
            return [{"error": f"serper: {str(e)[:50]}"}]

    # 3) Tor/DDG (last resort)
    UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 " \
         "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    html = None
    for attempt in range(4):
        try:
            import requests as r2
            proxies = {"http": "socks5h://127.0.0.1:9050",
                        "https": "socks5h://127.0.0.1:9050"}
            resp = r2.get(url, headers={"User-Agent": UA}, proxies=proxies, timeout=25)
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
    out = []
    if html:
        for m in re.finditer(r'class="result__a"[^>]*href="([^"]+)"', html):
            l = m.group(1)
            if "duckduckgo.com" in l and "uddg" in l:
                try:
                    l = urllib.parse.parse_qs(
                        urllib.parse.urlparse(l).query).get("uddg", [l])[0]
                except Exception:
                    pass
            out.append({"url": l, "title": ""})
        return out[:limit]
    return [{"error": "all search sources exhausted"}]


def check_vertical(vertical, query):
    results = _search(query)
    cited = False
    cited_urls = []
    for r in results:
        u = r.get("url", "") + " " + r.get("title", "")
        if any(d in u.lower() for d in OUR_DOMAINS):
            cited = True
            cited_urls.append(r.get("url", ""))
    return {
        "vertical": vertical,
        "query": query,
        "results_seen": len([r for r in results if "error" not in r]),
        "cited": cited,
        "cited_urls": cited_urls,
    }


def run():
    # read which verticals we published assets for
    published = []
    try:
        inf = json.load(open(INFLUENCE))
        published = list(inf.get("aeo_assets", {}).keys())
    except Exception:
        published = list(VERTICAL_QUERIES.keys())
    # only check verticals we have queries for
    checks = []
    for v in published:
        q = VERTICAL_QUERIES.get(v)
        if q:
            checks.append(check_vertical(v, q))
    cited_count = sum(1 for c in checks if c["cited"])
    out = {
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "verticals_checked": len(checks),
        "cited_count": cited_count,
        "citation_rate": round(cited_count / len(checks), 3) if checks else 0.0,
        "checks": checks,
    }
    os.makedirs(FEEDBACK, exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2)
    print(f"[aeo] checked {len(checks)} verticals | cited {cited_count} | "
          f"rate {out['citation_rate']} | O4-KR1 progress {out['citation_rate']}")
    return out


if __name__ == "__main__":
    run()
