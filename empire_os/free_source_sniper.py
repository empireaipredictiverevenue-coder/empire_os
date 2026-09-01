"""
free_source_sniper.py — credential-free B2B buying-intent scraper.

No API keys, no OAuth, no paid plans. Pulls from PUBLIC sources that work
from a datacenter IP:
  - Hacker News Algolia API   (https, no auth)
  - Lobsters RSS              (no auth)
  - IndieHackers RSS          (no auth)
  - Dev.to RSS                (no auth)
  - HN frontpage RSS          (news.ycombinator.com/rss)

Each item is scored across three vectors:
  1. engagement   (points/score + comment count)
  2. keyword intent (16 buying-signal regex patterns)
  3. recency boost  (posts < 6h old score 2x)

Qualified leads (score >= THRESHOLD) are written to SCOUT_OUTPUT_PATH and
optionally pushed into the funnel via /v1/leads/capture.

Run:
  python3 free_source_sniper.py [--push]   # --push sends to funnel
"""
from __future__ import annotations
import datetime, json, logging, os, re, sys, time
import urllib.request, urllib.error, urllib.parse
import xml.etree.ElementTree as ET

logger = logging.getLogger("free_source_sniper")

USER_AGENT = os.environ.get("SCOUT_UA", "Mozilla/5.0 (EmpireAI-Sniper/1.0)")
OUTPUT_PATH = os.environ.get("SCOUT_OUTPUT_PATH", ".scout_output.json")
THRESHOLD = int(os.environ.get("LEAD_SCORE_THRESHOLD", "50"))
CAPTURE_URL = "https://empire-ai.co.uk/v1/leads/capture"
# Cloudflare blocks urllib's default UA. Use a browser UA and prefer the
# localhost hub (127.0.0.1:8000) to skip the edge entirely.
CAPTURE_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Content-Type": "application/json",
}
CAPTURE_ENDPOINTS = [
    "http://127.0.0.1:8000/v1/leads/capture",   # hub local (no Cloudflare)
    "https://empire-ai.co.uk/v1/leads/capture",  # fallback via edge
]

# Intent queries for HN Algolia (high B2B buying signal)
HN_QUERIES = [
    "looking for agency", "need developer", "hiring freelancer",
    "request for proposal", "rfp", "outsource", "recommend crm",
    "automate workflow", "quote for", "buy saas", "integration platform",
]

# RSS feeds (no auth)
RSS_FEEDS = {
    "lobsters": "https://lobste.rs/rss",
    "indiehackers": "https://www.indiehackers.com/feed.xml",
    "devto": "https://dev.to/feed",
    "hn_frontpage": "https://news.ycombinator.com/rss",
}

INTENT_PATTERNS = [
    r"\bneed.{0,25}(developer|agency|consultant|solution|platform|software|tool|engineer)\b",
    r"\blooking for.{0,25}(developer|agency|consultant|automation|integration|freelancer)\b",
    r"\bhiring.{0,25}(freelancer|agency|developer|consultant|contractor)\b",
    r"\brfp\b", r"\brequest for proposal\b", r"\bquote\b",
    r"\boutsourc\w+\b", r"\b(scale|scaling|scaled)\b",
    r"\b(crm|erp|saas|api|integration|automation|pipeline)\b",
    r"\b(arr|mrr|revenue|churn|ltv|cac)\b", r"\bpain point\b",
    r"\b(recommend|suggestion|advice).{0,20}(tool|platform|software|service|stack)\b",
    r"\bstruggling with\b", r"\b(wasted?|losing?).{0,20}(hours?|time|money|revenue)\b",
    r"\bbudget.{0,20}(for|of|around|under|over)\b",
    r"\bhow do (you|we|i).{0,30}(automate|handle|manage|scale)\b",
]
COMPILED = [re.compile(p, re.IGNORECASE) for p in INTENT_PATTERNS]

RECENCY_HOURS = 6
MIN_POINTS = 1


def _kw_hits(text: str) -> int:
    return sum(1 for p in COMPILED if p.search(text))


def _recency_mult(age_h: float) -> float:
    return 2.0 if age_h < RECENCY_HOURS else 1.0


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


def _get_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8", "ignore")


def _score(title: str, body: str, points: int, comments: int, age_h: float) -> int:
    hits = _kw_hits(title + " " + body)
    if hits == 0:
        return 0
    return int((points + comments * 2 + hits * 10) * _recency_mult(age_h))


def _push_to_funnel(lead: dict) -> bool:
    payload = json.dumps({
        "email": f"{lead['id']}@free-scout.empire-ai.co.uk",
        "niche": "b2b_services",
        "source": f"free_source:{lead['source']}",
        "name": lead["author"],
    }).encode()
    for endpoint in CAPTURE_ENDPOINTS:
        req = urllib.request.Request(endpoint, data=payload,
                                     headers=CAPTURE_HEADERS, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                if r.status == 200:
                    return True
        except Exception as e:
            logger.warning("funnel push to %s failed: %s", endpoint, e)
    return False


def scrape_hn() -> list:
    out = []
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    for q in HN_QUERIES:
        try:
            url = f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(q)}&tags=story&numericFilters=points>{MIN_POINTS}"
            data = _get_json(url)
            for h in data.get("hits", []):
                title = h.get("title") or h.get("story_title") or ""
                body = h.get("story_text") or h.get("comment_text") or ""
                pts = int(h.get("points") or 0)
                cmts = int(h.get("num_comments") or 0)
                created = h.get("created_at_i") or now
                age_h = (now - created) / 3600
                ls = _score(title, body, pts, cmts, age_h)
                if ls == 0:
                    continue
                obj_id = h.get("objectID", "")
                out.append({
                    "id": f"hn_{obj_id}", "title": title.strip(),
                    "source": "hackernews", "url": h.get("url") or f"https://news.ycombinator.com/item?id={obj_id}",
                    "score": pts, "comments": cmts, "kw_hits": _kw_hits(title + " " + body),
                    "lead_score": ls, "author": h.get("author", "[unknown]"),
                    "created_utc": datetime.datetime.fromtimestamp(created, tz=datetime.timezone.utc).isoformat() + "Z",
                    "qualified": ls >= THRESHOLD,
                    "preview": (body[:400] + "…") if len(body) > 400 else body,
                })
            time.sleep(1)
        except Exception as e:
            logger.warning("hn query '%s' failed: %s", q, e)
    return out


def _parse_rss(name: str, url: str) -> list:
    out = []
    now = datetime.datetime.now(datetime.timezone.utc).timestamp()
    try:
        xml = _get_text(url)
        # strip namespaces + processing instructions so flat parsing works
        clean = re.sub(r'\sxmlns(:\w+)?="[^"]+"', "", xml, flags=re.MULTILINE)
        clean = re.sub(r'<\?xml[^>]*\?>', "", clean)
        clean = re.sub(r'<\?[^>]*\?>', "", clean)
        root = ET.fromstring(clean)
        items = list(root.iter("item")) + list(root.iter("entry"))
        for it in items:
            title = (it.findtext("title") or "").strip()
            link = it.findtext("link") or ""
            if not link:
                le = it.find("link")
                if le is not None:
                    link = le.get("href", "")
            desc = (it.findtext("description") or it.findtext("summary")
                    or it.findtext("content") or it.findtext("encoded") or "")
            if not desc:
                ce = it.find("encoded")
                if ce is not None:
                    desc = ce.text or ""
            ls = _score(title, desc, 1, 0, 12)
            if ls == 0:
                continue
            gid = abs(hash(title + link)) % 10**9
            out.append({
                "id": f"{name}_{gid}", "title": title, "source": name,
                "url": link, "score": 1, "comments": 0,
                "kw_hits": _kw_hits(title + " " + desc), "lead_score": ls,
                "author": name, "created_utc": "", "qualified": ls >= THRESHOLD,
                "preview": (desc[:400] + "…") if len(desc) > 400 else desc,
            })
    except Exception as e:
        logger.warning("%s rss failed: %s", name, e)
    return out


def scrape_rss() -> list:
    out = []
    for name, url in RSS_FEEDS.items():
        out.extend(_parse_rss(name, url))
        time.sleep(1)
    return out


def run(push: bool = False) -> dict:
    leads = scrape_hn() + scrape_rss()
    leads.sort(key=lambda x: x["lead_score"], reverse=True)
    qualified = [l for l in leads if l["qualified"]]
    if push:
        pushed = sum(1 for l in qualified if _push_to_funnel(l))
    else:
        pushed = 0
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)
    logger.info("free_source_sniper: %d leads, %d qualified, %d pushed",
                len(leads), len(qualified), pushed)
    return {"total": len(leads), "qualified": len(qualified), "pushed": pushed}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--push", action="store_true", help="push qualified leads to funnel")
    a = ap.parse_args()
    res = run(push=a.push)
    print(json.dumps(res))
