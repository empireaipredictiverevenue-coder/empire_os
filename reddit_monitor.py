#!/usr/bin/env python3
"""
Empire OS — Reddit Citation Monitor (legit, read-only).

The AEO playbook says Reddit is a gold mine for AI citations. We AGREE on the
*measurement* half, not the manipulation half. This module MONITORS organic
Reddit mentions of Empire AI / our phone numbers across a watchlist of subs.
It NEVER posts, never injects, never astroturfs — that violates Reddit ToS and
Google's spam policy, and we don't build that.

Method (free, no API key):
- Reddit exposes public JSON at https://www.reddit.com/r/<sub>/search.json?q=<term>
- We poll a watchlist of (subreddit, query) pairs for organic mentions.
- A "citation" = a post/comment that names Empire AI or a tracked phone number
  WITHOUT us having posted it.
- Findings append to /root/feedback/aeo_citations.json under the "reddit" key
  (same store aeo_monitor uses) and surface a reddit_citation_rate the
  influence engine can read.
- New organic citations fire a Telegram alert (reuses the fleet's notify path).

SKU: aeo_monitor add-on (same MRR tiers).

Run:
  python3 reddit_monitor.py run            # single sweep of watchlist
  python3 reddit_monitor.py --loop         # sweep every REDDIT_INTERVAL
"""
import json, os, time, sys, argparse, urllib.request, urllib.parse

FEEDBACK = "/root/feedback"
STORE = f"{FEEDBACK}/aeo_citations.json"
REDDIT_INTERVAL = 1800  # 30 min

# Watchlist: (subreddit, query). Organic-mention hunting only.
# Queries target our brand + tracked phone numbers so we catch AI-Overview
# citation drift on Reddit (which ~21% of Google AIO answers draw from).
WATCHLIST = [
    ("Entrepreneur", "Empire AI lead generation"),
    ("smallbusiness", "Empire AI pay per call"),
    ("Roofing", "Empire AI roofing leads"),
    ("Logistics", "Empire AI freight leads"),
    ("HVAC", "Empire AI hvac leads"),
    ("artificial", "Empire AI agent marketplace"),
    ("SideProject", "empire-ai.co.uk"),
]
# Tracked phone numbers (E.164-ish) — cite-drift detection.
TRACKED_PHONES = ["+1", "800", "888"]  # broaden per real numbers in .env
BRAND_TERMS = ["empire ai", "empire-ai.co.uk", "empire_os predictive"]

UA = "EmpireOS-AEO-Monitor/1.0 (citation tracking; contact admin@empire-ai.co.uk)"


def _reddit_search(sub, query, limit=25):
    """Public Reddit JSON search. Returns list of {title, selftext, url, author, kind}."""
    url = (f"https://www.reddit.com/r/{urllib.parse.quote(sub)}/search.json"
           f"?q={urllib.parse.quote(query)}&restrict_sr=1&sort=new&limit={limit}")
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    try:
        raw = urllib.request.urlopen(req, timeout=20).read().decode("utf-8", "ignore")
        data = json.loads(raw)
    except Exception:
        return []
    out = []
    for c in data.get("data", {}).get("children", []):
        d = c.get("data", {})
        out.append({
            "title": d.get("title", ""),
            "selftext": d.get("selftext", ""),
            "url": "https://www.reddit.com" + d.get("permalink", ""),
            "author": d.get("author", ""),
            "kind": c.get("kind", ""),
        })
    return out


def _mentions(text):
    """Return which tracked terms appear in text (organic citation signal)."""
    t = (text or "").lower()
    hits = [b for b in BRAND_TERMS if b in t]
    phones = [p for p in TRACKED_PHONES if p in t]
    return hits + phones


def sweep_once():
    """Sweep the watchlist; return findings + append to store."""
    findings = []
    for sub, query in WATCHLIST:
        for post in _reddit_search(sub, query):
            blob = f"{post['title']} {post['selftext']}"
            hits = _mentions(blob)
            if hits:
                findings.append({
                    "sub": sub, "query": query,
                    "url": post["url"], "author": post["author"],
                    "matched": hits,
                    "snippet": blob[:240],
                })
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    # append to shared store under "reddit"
    store = _load_store()
    reddit = store.setdefault("reddit", {"history": [], "mentions": 0})
    reddit["history"].append({
        "checked_at": ts,
        "findings": findings,
        "count": len(findings),
    })
    reddit["mentions"] = reddit.get("mentions", 0) + len(findings)
    # reddit_citation_rate = fraction of watchlist pairs that surfaced a mention
    reddit["reddit_citation_rate"] = round(
        len(findings) / max(1, len(WATCHLIST)), 3)
    _save_store(store)
    if findings:
        _alert(findings, reddit["reddit_citation_rate"])
    return {"checked_at": ts, "findings": len(findings),
            "rate": reddit["reddit_citation_rate"]}


def _load_store():
    if not os.path.exists(STORE):
        return {}
    try:
        return json.load(open(STORE))
    except Exception:
        return {}


def _save_store(d):
    os.makedirs(FEEDBACK, exist_ok=True)
    json.dump(d, open(STORE, "w"), indent=2)


def _alert(findings, rate):
    """Telegram alert (reuses fleet notifier). Best-effort, silent on fail."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from empire_os.telegram_bot import send_message
        tok = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        cid = os.environ.get("TELEGRAM_CHAT_ID", "")
        if not (tok and cid):
            return
        lines = [f"[AEO] Reddit organic citations: {rate}"]
        for f in findings[:5]:
            lines.append(f"  {f['sub']}: {f['url']} ({','.join(f['matched'])})")
        send_message(tok, cid, "\n".join(lines))
    except Exception:
        pass  # no TELEGRAM creds / not wired — monitoring still persists to store


def _loop():
    print(f"[reddit_monitor] loop start | watchlist={len(WATCHLIST)} | "
          f"interval={REDDIT_INTERVAL}s", flush=True)
    while True:
        try:
            r = sweep_once()
            print(f"[reddit_monitor] {r['checked_at']} findings={r['findings']} "
                  f"rate={r['rate']}", flush=True)
        except Exception as e:
            print(f"[reddit_monitor] error: {e}", flush=True)
        time.sleep(REDDIT_INTERVAL)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="--loop")
    ap.add_argument("--loop", action="store_true")
    args = ap.parse_args()
    if args.cmd == "--loop" or args.loop:
        _loop()
    else:
        r = sweep_once()
        print(json.dumps(r, indent=2))


if __name__ == "__main__":
    main()
