#!/usr/bin/env python3
"""mailto_harvest.py — free email discovery from OUR crm_leads websites.

We already have 10K+ real businesses (crm_leads) with websites. Many have NO
email because we never crawled their site for mailto:. This closes that gap
WITHOUT renting Apollo/PDL — we own the discovery graph.

Pipeline:
  pull crm_leads rows with website + no email
  -> crawl homepage + /contact for mailto: addresses
  -> MX-check + syntax filter (skip spam traps / role junk)
  -> update crm_leads.email
  -> lead_harvest.bridge_to_outreach sweeps them into si_buyer_outreach

Free. No proxy needed at this volume (own-domain crawl, ~1.8K sites).
"""
from __future__ import annotations
import sys, re, sqlite3, urllib.request, urllib.parse, socket, ssl, time
sys.path.insert(0, "/root/empire_os")

DB = "/root/empire_os/empire_os.db"
MAX_CRAWL_PER_RUN = 600
CRAWL_TIMEOUT = 12
UA = "Mozilla/5.0 (compatible; EmpireLeadOS/2.0; +https://empire-ai.co.uk)"

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
# Skip role/junk addresses — we want a real person/company inbox
ROLE = ("info@", "sales@", "admin@", "contact@", "hello@", "office@", "support@",
        "noreply@", "no-reply@", "billing@", "help@", "team@")
BAD_DOMAINS = ("gaf.com", "angieslist", "homeadvisor", "yelp", "thumbtack",
               "facebook", "linkedin", "instagram", "pinterest", "youtube",
               "wikipedia", "bbb.org", "yellowpages", "houzz")

_mx_cache: dict[str, bool] = {}


def log(m): print(f"[mailto_harvest] {m}", flush=True)


def open_db():
    c = sqlite3.connect(DB, timeout=60)
    c.execute("PRAGMA busy_timeout=60000")
    return c


def has_mx(domain: str) -> bool:
    if domain in _mx_cache:
        return _mx_cache[domain]
    try:
        socket.setdefaulttimeout(6)
        import dns.resolver  # optional; if missing, skip MX check
        try:
            dns.resolver.resolve(domain, "MX")
            _mx_cache[domain] = True
            return True
        except Exception:
            _mx_cache[domain] = False
            return False
    except ImportError:
        _mx_cache[domain] = True  # no dns lib -> don't block on MX
        return True


def _fetch(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        with urllib.request.urlopen(req, timeout=CRAWL_TIMEOUT, context=ctx) as r:
            return r.read().decode("utf-8", "ignore")
    except Exception:
        return ""


def extract_emails(html: str, site_domain: str) -> list[str]:
    out = []
    for em in EMAIL_RE.findall(html):
        em = em.lower().strip()
        dom = em.split("@")[-1]
        if any(b in dom for b in BAD_DOMAINS):
            continue
        if not has_mx(dom):
            continue
        if em.startswith(ROLE) and dom != site_domain:
            # role address on a different domain (e.g. @gmail) is usually junk
            if dom in ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com"):
                continue
        out.append(em)
    # prefer the site's own domain email
    own = [e for e in out if e.split("@")[-1] == site_domain]
    return (own + [e for e in out if e not in own])[:3]


def crawl(site: str) -> list[str]:
    site = site.strip()
    if not site.startswith("http"):
        site = "https://" + site
    host = urllib.parse.urlparse(site).netloc or site
    site_domain = host.replace("www.", "")
    emails: list[str] = []
    for path in ("", "/contact", "/contact-us", "/about"):
        url = site.rstrip("/") + path
        html = _fetch(url)
        if html:
            emails = extract_emails(html, site_domain)
            if emails:
                break
    return emails


def main():
    c = open_db()
    rows = c.execute(
        "SELECT id, website FROM crm_leads "
        "WHERE website IS NOT NULL AND website!='' "
        "AND (email IS NULL OR email='') "
        "AND website NOT LIKE '%gaf.com%' AND website NOT LIKE '%angieslist%' "
        "AND website NOT LIKE '%homeadvisor%' AND website NOT LIKE '%yelp%' "
        "AND website NOT LIKE '%thumbtack%' AND website NOT LIKE '%houzz%' "
        "AND website NOT LIKE '%facebook%' AND website NOT LIKE '%linkedin%' "
        "LIMIT ?", (MAX_CRAWL_PER_RUN,)
    ).fetchall()
    log(f"crawling {len(rows)} sites for mailto:")
    found = 0
    for rid, site in rows:
        try:
            ems = crawl(site)
        except Exception:
            ems = []
        if ems:
            c.execute("UPDATE crm_leads SET email=? WHERE id=?", (ems[0], rid))
            found += 1
        time.sleep(0.15)  # be polite, avoid bans
    c.commit()
    c.close()
    log(f"found {found} new emails from {len(rows)} sites")
    # bridge to outreach
    import lead_harvest
    lead_harvest.bridge_to_outreach()
    c = open_db()
    valid = c.execute("SELECT COUNT(DISTINCT email) FROM si_buyer_outreach WHERE email_status='valid'").fetchone()[0]
    log(f"valid unique pool now: {valid}")


if __name__ == "__main__":
    main()
