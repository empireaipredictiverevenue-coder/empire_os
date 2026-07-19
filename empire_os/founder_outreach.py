#!/usr/bin/env python3
"""founder_outreach — queue founder-discount emails to REAL prospects.

Reads from si_buyer_outreach (the 29k real scraper output), enriches any
missing emails via the waterfall (website_scraper -> pattern -> Hunter),
and queues personalized founder emails into si_outbox (Brevo sends them).

No fabrication: every recipient is a real business from si_buyer_outreach.
Only queues rows that have a real email (no @example, no empty).

Usage:
  founder_outreach.py --batch 50        # process 50 prospects this run
  founder_outreach.py --watch           # loop forever, 50/cycle, sleep 60s
  founder_outreach.py --niche roofing   # only this niche
"""
import sys, os, json, time, argparse, sqlite3
sys.path.insert(0, "/root/empire_os")
for ln in open("/root/empire_os/.env"):
    ln = ln.strip()
    if ln and "=" in ln and not ln.startswith("#"):
        k, v = ln.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

import importlib.util
spec = importlib.util.spec_from_file_location("en", "/root/empire_os/empire_os/enrichment.py")
en = importlib.util.module_from_spec(spec); spec.loader.exec_module(en)

DB = "/root/empire_os/empire_os.db"
HUB = os.environ.get("HUB_URL", "http://127.0.0.1:8081")

FOUNDER_COPY = {
    "roofing": ("Empire OS — Founder Pricing for Roofing Contractors",
        "Hi {name},<br><br>We're opening Empire OS to our first 20 roofing "
        "contractors at founder pricing: <b>$299/mo + $25/lead</b> (reg $599 + $49). "
        "You only pay when seated. Real exclusive leads, your metro, USDC or card.<br><br>"
        "Reply FOUNDER or book: https://empire-ai.co.uk/buy-leads<br><br>"
        "— Empire OS team"),
    "hvac": ("Empire OS — Founder Pricing for HVAC Contractors",
        "Hi {name},<br><br>Founder pricing for our first 20 HVAC contractors: "
        "<b>$299/mo + $25/lead</b> (reg $599 + $49). Exclusive leads in your metro, "
        "pay only when seated.<br><br>Reply FOUNDER or book: https://empire-ai.co.uk/buy-leads<br><br>"
        "— Empire OS team"),
    "b2b": ("Empire OS — Founder Pricing for B2B Lead Buyers",
        "Hi {name},<br><br>Founder pricing for our first 20 lead buyers: "
        "<b>$299/mo + $25/lead</b>. Exclusive verified leads, pay when seated.<br><br>"
        "Reply FOUNDER or book: https://empire-ai.co.uk/buy-leads<br><br>— Empire OS team"),
}

def _mint_pay_url(name, niche, to_email, tier="silver"):
    """Mint a per-prospect Solana Pay link via hub /v1/buyer_apply.

    Returns (pay_url, memo) or ("", "") on failure. Non-fatal: a prospect
    still gets the pitch even if pay-link minting fails (loop_closure alerts
    on the S2->S3 stall if pay_urls stop generating).
    """
    import urllib.request
    try:
        payload = json.dumps({
            "name": name or to_email.split("@")[0],
            "niche": niche, "tier": tier,
            "email": to_email, "source": "founder_outreach",
        }).encode()
        req = urllib.request.Request(
            f"{HUB}/v1/buyers/apply", data=payload,
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=12) as r:
            res = json.loads(r.read())
        pay = res.get("payment", {}) or {}
        return pay.get("pay_url", ""), pay.get("memo", "")
    except Exception:
        return "", ""


def queue_email(cur, to_email, name, niche):
    subj, body = FOUNDER_COPY.get(niche, FOUNDER_COPY["b2b"])
    body = body.format(name=name or "there")
    # Insert + COMMIT first so the founder-outreach transaction is NOT open
    # during the HTTP round-trip to the hub (otherwise we deadlock the shared
    # SQLite db: this proc holds the lock, hub's onboard() can't write -> 504).
    cur.execute(
        "INSERT INTO si_outbox (to_email, subject, body, lane, tier, source, status, recipient_kind, created_at) "
        "VALUES (?,?,?,?,?,?, 'pending', 'prospect', datetime('now'))",
        (to_email, subj, body, niche, "founder", "founder_outreach"),
    )
    cur.commit()
    outbox_id = cur.execute(
        "SELECT id FROM si_outbox WHERE rowid=last_insert_rowid()").fetchone()[0]
    # Now mint a personal pay link (no open transaction) and patch the row.
    pay_url, memo = _mint_pay_url(name, niche, to_email)
    if pay_url:
        body = body.replace(
            "https://empire-ai.co.uk/buy-leads",
            f'<a href="{pay_url}">Claim your founder seat (pay USDC)</a>')
        body += f'<br><br><small>Seat ref: {memo}</small>'
        cur.execute("UPDATE si_outbox SET body=? WHERE id=?",
                    (body, outbox_id))
        cur.commit()

import signal

class _Timeout(Exception):
    pass

def _timeout_sig(signum, frame):
    raise _Timeout()

def _call_with_timeout(fn, lead, seconds=8):
    old = signal.signal(signal.SIGALRM, _timeout_sig)
    signal.alarm(seconds)
    try:
        return fn(lead)
    except _Timeout:
        return {}
    except Exception:
        return {}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

# Free SERP scrapers (no key) + Hunter (25/mo verified). All bounded by
# 15s signal timeout in _call_with_timeout. website_scraper skipped (slow
# on junk URLs); ddg/bing cover the SERP gap for free.
API_PROVIDERS = ["ddg_search", "bing_search", "hunter"]

def enrich_one(cur, pid):
    """Enrich a single si_buyer_outreach row via API providers only (fast).
    website_scraper skipped in watch loop (too slow on junk URLs).
    """
    row = cur.execute("SELECT * FROM si_buyer_outreach WHERE prospect_id=?", (pid,)).fetchone()
    if not row:
        return
    lead = dict(row)
    # derive domain from url if it looks like a real domain
    url = lead.get("url") or ""
    domain = ""
    if "." in url and " " not in url and not url.startswith("skus:"):
        domain = url.split("//")[-1].split("/")[0] if "//" in url else url
    found = {}
    for prov in API_PROVIDERS:
        fn = getattr(en, prov, None)
        if not fn:
            continue
        try:
            res = _call_with_timeout(fn, {"website": domain, "business_name": lead.get("business_name")}, 15)
        except Exception:
            continue
        if not res:
            continue
        for k, v in res.items():
            if k not in found and not lead.get(k):
                found[k] = v
        if found:
            lead.update(found)
    if not found:
        return
    setters, params = [], []
    for src, col in {"email": "email", "phone": "phone", "business_name": "business_name"}.items():
        if src in found:
            setters.append(f"{col}=?")
            params.append(found[src])
    if setters:
        params.append(pid)
        cur.execute(f"UPDATE si_buyer_outreach SET {','.join(setters)} WHERE prospect_id=?", tuple(params))
        cur.commit()

def run_batch(cur, batch, niche=None):
    # Queue prospects that ALREADY have a valid email first (instant win),
    # then try to enrich + queue the missing-email ones.
    clauses = ("email IS NOT NULL AND email != '' AND email NOT LIKE '%@example%' "
               "AND email NOT LIKE '%invalid%'")
    q = f"SELECT prospect_id FROM si_buyer_outreach WHERE {clauses}"
    if niche:
        q += f" AND niche='{niche}'"
    q += f" ORDER BY prospect_id ASC LIMIT {batch}"
    rows = cur.execute(q).fetchall()
    queued = 0
    for r in rows:
        pid = r["prospect_id"]
        fresh = cur.execute("SELECT business_name, email, niche FROM si_buyer_outreach WHERE prospect_id=?", (pid,)).fetchone()
        email = fresh["email"]
        name = (fresh["business_name"] or "").split("|")[0].split(" - ")[0].strip()
        queue_email(cur, email, name, fresh["niche"] if fresh["niche"] else "b2b")
        queued += 1
    cur.commit()  # commit valid-email rows immediately so Brevo sends them
    # Now enrich a slice of missing-email rows
    q2 = ("SELECT prospect_id FROM si_buyer_outreach "
          "WHERE (email IS NULL OR email='' OR email LIKE '%@example%' OR email LIKE '%invalid%')")
    if niche:
        q2 += f" AND niche='{niche}'"
    q2 += f" ORDER BY prospect_id ASC LIMIT {batch}"
    for r in cur.execute(q2).fetchall():
        pid = r["prospect_id"]
        enrich_one(cur, pid)
        fresh = cur.execute("SELECT business_name, email, niche FROM si_buyer_outreach WHERE prospect_id=?", (pid,)).fetchone()
        email = fresh["email"] if fresh else None
        if not email or "@example" in email or "invalid" in email:
            continue
        name = (fresh["business_name"] or "").split("|")[0].split(" - ")[0].strip()
        queue_email(cur, email, name, fresh["niche"] if fresh["niche"] else "b2b")
        queued += 1
        cur.commit()  # commit per enriched row so it doesn't pile up
    return queued

def reload_env():
    """Reload .env each cycle so keys added later are picked up live."""
    for ln in open("/root/empire_os/.env"):
        ln = ln.strip()
        if ln and "=" in ln and not ln.startswith("#"):
            k, v = ln.split("=", 1)
            os.environ[k.strip()] = v.strip().strip('"').strip("'")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--niche", default=None)
    ap.add_argument("--watch", action="store_true")
    a = ap.parse_args()
    c = sqlite3.connect(DB, timeout=30); c.row_factory = sqlite3.Row
    if a.watch:
        while True:
            reload_env()
            n = run_batch(c, a.batch, a.niche)
            print(f"[{time.strftime('%H:%M:%S')}] queued {n} founder emails")
            time.sleep(60)
    else:
        reload_env()
        n = run_batch(c, a.batch, a.niche)
        print(f"queued {n} founder emails into si_outbox (Brevo sends)")

if __name__ == "__main__":
    main()
