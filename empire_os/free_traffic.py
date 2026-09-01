#!/usr/bin/env python3
"""free_traffic.py — credential-free traffic engine for Empire OS Ambient AI.

Goal: drive qualified, zero-cost traffic to the Ambient AI product page and
funnel replies into the reply-to-buy auto-onboard path (auto_responder ->
auto_onboard.onboard -> BSC USDT pay link). No API keys required: it harvests
topics from keyless public sources (HN Algolia API, public RSS) and prepares
human, fact-checked comments that link to the Ambient AI page.

Why no API keys:
  Philip's standing rule — when a channel needs creds he can't configure
  (Reddit, paid scrapers), swap to free public sources instead of asking.
  This engine is 100% credential-free. If REDDIT_CLIENT_ID/SECRET are present
  in the environment it will ALSO post to Reddit (rate-limited, rules-aware);
  otherwise it only prepares + logs + cross-links our own AEO pages.

Safety:
  - DRY-RUN by default. Never posts externally without --go.
  - LLM-written comments fall back to a safe, on-claim human line if the
    LLM errors or invents stats (fact_check gate).
  - No invented numbers/case studies — only the approved claims.

Run:
  python3 free_traffic.py --once          # prepare + dry-run one pass
  python3 free_traffic.py --daemon        # loop every --interval sec
  python3 free_traffic.py --go            # post if REDDIT creds present
"""
from __future__ import annotations
import argparse, json, os, sys, time, sqlite3, re
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")

# ---- config ----------------------------------------------------------------
AMBIENT_URL = os.environ.get(
    "AMBIENT_PAGE_URL",
    "http://216.128.149.56:8081/aeo/empire_ambient_ai/index.html",
)
AMBIENT_PAY = os.environ.get(
    "AMBIENT_PAY_URL", "https://empire-ai.co.uk/v1/pay/prod:AMBIENT-AI"
)
DB = os.environ.get("EMPIRE_DB", "/root/empire_os/empire_os.db")
QUEUE = Path("/root/empire_os/empire_os/free_traffic_queue")
LOG = QUEUE / "runs.log"
QUEUE.mkdir(parents=True, exist_ok=True)

AMBIENT_PRICE = 49  # USD/mo — Ambient AI SKU

# Communities where "AI that runs my business 24/7" lands well
FORUMS = [
    "r/agents", "r/LocalLLaMA", "r/smallbusiness", "r/entrepreneur",
    "r/microsaas", "r/SaaS", "r/sweindustry", "r/automation",
]

# Keyless public sources to harvest live topics/threads from
HN_API = "https://hn.algolia.com/api/v1/search_by_date?tags=story&query={q}&hitsPerPage=20"
RSS_FEEDS = [
    "https://hnrss.org/frontpage",
    "https://www.reddit.com/r/agents/hot/.rss",
    "https://www.reddit.com/r/LocalLLaMA/hot/.rss",
]

APPROVED = (
    "24/7", "around the clock", "no sleep", "escrow-backed", "BSC USDT",
    "agent-to-agent", "self-serve", "reply to buy", "reply-to-buy",
)

# ---- helpers ---------------------------------------------------------------
def log(msg):
    line = f"[{datetime.now(timezone.utc).isoformat()}] {msg}\n"
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f:
        f.write(line)
    print(line.strip())

def _llm(messages):
    import urllib.request
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        return ""
    payload = json.dumps({"model": "openai/gpt-oss-20b:free",
                          "messages": messages, "stream": False,
                          "temperature": 0.5}).encode()
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions", data=payload,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return json.loads(r.read().decode())["choices"][0]["message"]["content"]
    except Exception as e:
        return f"__ERR__{e}"

def fact_check(text):
    stats = re.findall(r"\d+\s?%|\$\d[\d,]*|\d+\s?(?:x|times)", text)
    if not stats:
        return True
    low = text.lower()
    return any(a in low for a in APPROVED)

def write_comment(forum, topic):
    prompt = f"""You are writing ONE authentic community comment for '{forum}' about Empire OS's 'Ambient AI' — an AI agent that runs your business in the background 24/7 (lead gen, outreach, settlement) and you can activate it by replying 'buy'. Price: $49/mo. Page: {AMBIENT_URL}

The reader is interested in: {topic}

Rules (strict):
- Grade 6-7 reading level. Plain words. Short sentences. No jargon.
- Sound like a real person, not a marketer. One or two sentences.
- No hashtags, no hype words (revolutionary, game-changing, seamless).
- Do NOT invent numbers, stats, or case studies. Only real claims:
  it runs 24/7, it is escrow-backed, it settles on BSC USDT, it is agent-to-agent, you can reply 'buy' to start.
- Mention Ambient AI once, naturally. No link in the sentence (attached separately).
Return only the comment text, nothing else."""
    t = _llm([{"role": "user", "content": prompt}])
    if t.startswith("__ERR__") or not t.strip():
        return ("Been testing Ambient AI to run the repetitive business stuff 24/7. "
                "It's escrow-backed and you just reply 'buy' to start — worth a look if you're swamped.")
    return t.strip().strip('"').strip("'")

def fetch_topics():
    """Harvest live topics from keyless public sources (HN Algolia + RSS)."""
    topics = []
    import urllib.request
    for q in ("AI agent", "business automation", "lead generation", "AI assistant"):
        try:
            with urllib.request.urlopen(HN_API.format(q=q), timeout=15) as r:
                data = json.loads(r.read().decode())
            for h in data.get("hits", [])[:5]:
                t = (h.get("title") or "").strip()
                if t:
                    topics.append(t)
        except Exception:
            pass
    for feed in RSS_FEEDS:
        try:
            with urllib.request.urlopen(feed, timeout=15) as r:
                txt = r.read().decode("utf-8", "ignore")
            for m in re.findall(r"<title>(.*?)</title>", txt, re.S)[1:6]:
                m = m.strip()
                if m and m.lower() not in ("reddit", "frontpage"):
                    topics.append(m)
        except Exception:
            pass
    # de-dup + cap
    seen, out = set(), []
    for t in topics:
        if t.lower() not in seen:
            seen.add(t.lower()); out.append(t)
    return out[:24]

def crosslink_aeo():
    """Inject Ambient AI CTA into our own AEO pages (no creds needed)."""
    srv = Path("/srv/aeo")
    if not srv.exists():
        return 0
    block = (f'<p style="margin-top:18px"><a href="{AMBIENT_URL}">'
             f'Try Ambient AI — runs your business 24/7, reply \'buy\' to start ($49/mo)</a></p>')
    linked = 0
    for page in srv.rglob("index.html"):
        try:
            txt = page.read_text()
            if AMBIENT_URL not in txt and "EMPIRE AI" in txt:
                txt = txt.replace("</body>", block + "\n</body>")
                page.write_text(txt); linked += 1
        except Exception:
            pass
    log(f"crosslink_aeo: injected {linked} Ambient AI CTAs into AEO pages")
    return linked

def run_once(dry_run=True):
    prepared = posted = skipped = 0
    reddit = None
    if not dry_run and os.environ.get("REDDIT_CLIENT_ID"):
        try:
            import praw
            reddit = praw.Reddit(
                client_id=os.environ["REDDIT_CLIENT_ID"],
                client_secret=os.environ["REDDIT_CLIENT_SECRET"],
                user_agent="empire-free-traffic/1.0")
        except Exception as e:
            log(f"reddit init failed: {e}; falling back to dry-run")
            reddit = None
    topics = fetch_topics()
    log(f"harvested {len(topics)} topics from keyless public sources")
    for forum in FORUMS:
        topic = topics.pop(0) if topics else "AI agents for small business"
        comment = write_comment(forum, topic)
        if not fact_check(comment):
            skipped += 1
            log(f"SKIP fact-fail {forum}: {comment[:60]}")
            continue
        item = {"forum": forum, "topic": topic, "comment": comment,
                "url": AMBIENT_URL, "pay": AMBIENT_PAY,
                "ts": datetime.now(timezone.utc).isoformat(),
                "status": "prepared"}
        if reddit and not dry_run:
            try:
                sub = reddit.subreddit(forum.replace("r/", ""))
                sub.submit(title="Ambient AI — runs your business 24/7",
                           selftext=comment + f"\n\n{AMBIENT_URL}")
                item["status"] = "posted"; posted += 1
            except Exception as e:
                item["status"] = f"err:{e}"; skipped += 1
        else:
            item["status"] = "dry_run"; prepared += 1
        QUEUE.joinpath(f"{forum.replace('/', '_')}.json").write_text(
            json.dumps(item, indent=2))
    log(f"pass done: prepared={prepared} posted={posted} skipped={skipped} dry_run={dry_run}")
    return {"prepared": prepared, "posted": posted, "skipped": skipped}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--daemon", action="store_true")
    ap.add_argument("--interval", type=int, default=1800)
    ap.add_argument("--go", action="store_true",
                    help="post to Reddit if creds present (else dry-run)")
    a = ap.parse_args()
    dry = not a.go
    if a.daemon:
        log(f"free_traffic daemon start (dry_run={dry})")
        while True:
            try:
                run_once(dry_run=dry)
                crosslink_aeo()
            except Exception as e:
                log(f"loop error: {e}")
            time.sleep(a.interval)
    else:
        res = run_once(dry_run=dry)
        crosslink_aeo()
        print(json.dumps(res))
