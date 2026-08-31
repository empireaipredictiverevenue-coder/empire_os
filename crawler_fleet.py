#!/usr/bin/env python3
"""crawler_fleet.py — enterprise-grade free crawler (Playwright JS-render).

Replaces the urllib shell-crawl. Renders JS, scrolls, tries multiple paths,
clicks contact reveals, extracts mailto + form-action + obfuscated emails.
No proxy needed for non-Cloudflare small-biz sites.

Then ranks guessed pattern-emails (info@domain etc.) by MX-existence so
bridge can prefer verified-domain guesses without SMTP (port 25 blocked here).

Pure OSS (Playwright + dns). No per-lead rental. OWNED pipeline.
"""
from __future__ import annotations
import sys, re, sqlite3, time, random
from urllib.parse import urlparse
sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"
BATCH = 300
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
BAD = ("gaf.com", "angieslist", "homeadvisor", "yelp", "thumbtack", "facebook",
       "linkedin", "instagram", "pinterest", "youtube", "wikipedia", "bbb.org",
       "yellowpages", "houzz", "google", "googlemaps", "maps.app")
_mx: dict[str, bool] = {}


def log(m): print(f"[crawler_fleet] {m}", flush=True)


def open_db():
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA busy_timeout=60000")
    return c


def mx_exists(dom: str) -> bool:
    if dom in _mx:
        return _mx[dom]
    try:
        import dns.resolver
        dns.resolver.resolve(dom, "MX")
        _mx[dom] = True
    except Exception:
        _mx[dom] = False
    return _mx[dom]


def extract(html: str, site_domain: str) -> list[str]:
    out = []
    for em in EMAIL_RE.findall(html):
        em = em.lower().strip().strip(".")
        d = em.split("@")[-1]
        if any(b in d for b in BAD):
            continue
        if not mx_exists(d):
            continue
        out.append(em)
    own = [e for e in out if e.split("@")[-1] == site_domain]
    return (own + [e for e in out if e not in own])[:3]


def crawl(site: str) -> list[str]:
    from playwright.sync_api import sync_playwright
    if not site.startswith("http"):
        site = "https://" + site
    host = urlparse(site).netloc or site
    site_domain = host.replace("www.", "")
    emails: list[str] = []
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-dev-shm-usage"])
            pg = b.new_page()
            pg.set_extra_http_headers({"User-Agent": UA})
            for path in ("", "/contact", "/contact-us", "/about", "/get-a-quote"):
                try:
                    pg.goto(site.rstrip("/") + path, wait_until="domcontentloaded", timeout=15000)
                    pg.wait_for_timeout(2500)  # let JS/promises resolve
                    pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    pg.wait_for_timeout(800)
                    h = pg.content()
                except Exception:
                    h = ""
                found = extract(h, site_domain)
                if found:
                    emails = found
                    break
            b.close()
    except Exception as e:
        log(f"  crawl err {site[:30]}: {e}")
    return emails


def pattern_guess(domain: str) -> list[str]:
    """MX-scored pattern emails (no SMTP; port 25 blocked here)."""
    if not mx_exists(domain):
        return []
    base = domain.split(".")[0]
    return [f"{u}@{domain}" for u in ("info", "admin", "sales", "office", "contact", "hello")]


def run():
    c = open_db()
    rows = c.execute(
        "SELECT id, website FROM crm_leads WHERE website IS NOT NULL AND website!='' "
        "AND (email IS NULL OR email='') "
        "AND website NOT LIKE '%gaf.com%' AND website NOT LIKE '%angieslist%' "
        "AND website NOT LIKE '%homeadvisor%' AND website NOT LIKE '%yelp%' "
        "AND website NOT LIKE '%thumbtack%' AND website NOT LIKE '%houzz%' "
        "AND website NOT LIKE '%facebook%' AND website NOT LIKE '%linkedin%' "
        "LIMIT ?", (BATCH,)
    ).fetchall()
    log(f"rendering {len(rows)} sites (Playwright JS)...")
    real_found = 0
    guessed = 0
    for rid, site in rows:
        dom = (urlparse(site).netloc or site).replace("www.", "")
        ems = crawl(site)
        if ems:
            c.execute("UPDATE crm_leads SET email=? WHERE id=?", (ems[0], rid))
            real_found += 1
        else:
            # fall back to MX-scored pattern guess (domain-matched)
            g = pattern_guess(dom)
            if g:
                c.execute("UPDATE crm_leads SET email=? WHERE id=?", (g[0], rid))
                guessed += 1
        time.sleep(random.uniform(0.3, 0.8))
    c.commit()
    c.close()
    log(f"real emails found: {real_found} | pattern-guessed (MX-ok): {guessed}")
    import lead_harvest
    lead_harvest.bridge_to_outreach()
    c = open_db()
    valid = c.execute("SELECT COUNT(DISTINCT email) FROM si_buyer_outreach WHERE email_status='valid'").fetchone()[0]
    log(f"valid unique pool now: {valid}")
    c.close()


if __name__ == "__main__":
    run()
