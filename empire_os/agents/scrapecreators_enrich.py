#!/usr/bin/env python3
"""
scrapecreators_enrich.py — free lead-intent pull via ScrapeCreators (100 credits).

FREE TIER includes reddit/search (verified 200). Google Maps / Yelp / Twitter /
LinkedIn are PAID add-ons (404 on this key) — not used.

We pull Reddit threads where local-business owners / homeowners discuss our
niches ("roofing contractor leads", "hvac quote", etc.). These are REAL
high-intent leads: contractors asking where to buy leads = our buyer persona.
Each thread -> upsert into si_buyer_outreach (source=scrapecreators) so the
unified intake funnel + rent/rolling-stones strategies can route/monetize them.
Also doubles as article-topic fuel for article_writer.

Key: SCRAPECREATORS_API_KEY (container .env). Never logged.
Frugal: 1 query per niche = ~10 credits total across the board.
"""
import os, sys, json, time, sqlite3, logging, urllib.parse, urllib.request
sys.path.insert(0, os.path.dirname(__file__))

log = logging.getLogger("scrapecreators")
KEY = os.getenv("SCRAPECREATORS_API_KEY")
API = "https://api.scrapecreators.com/v1"
DB = os.getenv("EMPIRE_DB", "/root/empire_os/empire_os.db")

# niche -> reddit search query (high buyer intent)
QUERIES = [
    ("roofing", "roofing contractor looking for leads"),
    ("hvac", "hvac company needs more leads"),
    ("plumbing", "plumbing business lead generation"),
    ("solar", "solar installer finding customers"),
    ("landscaping", "landscaping company marketing leads"),
    ("pest_control", "pest control business leads"),
    ("electrical", "electrician getting more jobs"),
    ("painting", "painting contractor lead source"),
    ("windows", "window replacement company leads"),
    ("fencing", "fence contractor marketing"),
]


def _db():
    return sqlite3.connect(DB)


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"x-api-key": KEY})
    with urllib.request.urlopen(req, timeout=25) as r:
        return json.loads(r.read().decode())


def pull_one(niche: str, query: str) -> int:
    """Return #threads upserted for one niche query. -1 on error."""
    if not KEY:
        log.warning("no SCRAPECREATORS_API_KEY")
        return -1
    c = _db()
    n = 0
    try:
        q = urllib.parse.quote(query)
        url = f"{API}/reddit/search?query={q}&limit=10"
        data = _get(url)
        posts = (data.get("posts") or []) if data.get("success") else []
        for p in posts:
            author = p.get("author") or ""
            sub = p.get("subreddit") or ""
            title = (p.get("title") or "")[:200]
            thread = p.get("permalink") or p.get("url") or ""
            if not title:
                continue
            # contactable prospect: reddit u/author + thread url
            contact = f"reddit.com/{thread}" if thread else f"u/{author}"
            c.execute(
                "INSERT INTO si_buyer_outreach "
                "(business_name,email,metro,niche,score,url,source,first_touch_at,last_touch_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (f"reddit u/{author} ({sub})", "", sub, niche, 0.6,
                 contact, "scrapecreators", _now(), _now()))
            n += 1
        c.commit()
        log.info("niche=%s upserted=%d", niche, n)
    except Exception as e:
        log.warning("pull err %s: %s", niche, str(e)[:160])
        return -1
    return n


def run(dry_run: bool = False, cap: int = 10) -> dict:
    stats = {"queries": 0, "upserted": 0, "errors": 0, "credits_left": None}
    for niche, query in QUERIES[:cap]:
        if dry_run:
            stats["queries"] += 1
            continue
        r = pull_one(niche, query)
        stats["queries"] += 1
        if r < 0:
            stats["errors"] += 1
        else:
            stats["upserted"] += r
    # peek remaining credits (1 cheap call)
    if not dry_run and KEY:
        try:
            d = _get(f"{API}/reddit/search?query=ping&limit=1")
            stats["credits_left"] = d.get("credits_remaining")
        except Exception:
            pass
    return stats


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--cap", type=int, default=10)
    a = ap.parse_args()
    print(json.dumps(run(dry_run=a.dry, cap=a.cap), indent=2))
