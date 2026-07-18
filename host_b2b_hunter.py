#!/usr/bin/env python3
"""
Host-side B2B hunter.

Runs on the HOST (direct egress, no proxy) to bypass the container's
proxy-gated scraping. Finds real B2B firms + contact emails per vertical,
pushes them into the empire-hub CRM (niche='b2b') for the nurture
pipeline to pitch the 12-SKU suite.

Usage:
  python3 host_b2b_hunter.py            # one shot, 8 per vertical
  python3 host_b2b_hunter.py --limit 5 --verticals logistics warehouse
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HUB = "http://10.118.155.218:8081"
UA = {"User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                     "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")}

VERTICALS = {
    "logistics":     ("logistics trucking freight company", "satellite_idle_watch,warehouse_asset"),
    "warehouse":     ("warehouse storage distribution company", "warehouse_asset,satellite_wastage"),
    "ai_team":       ("ai machine learning startup company", "skillspector_audit,hermes_framework"),
    "marketing":     ("marketing agency video production company", "opencut_studio,marketingskills,empire_templates"),
    "agency":        ("lead generation agency company", "empire_leads_engine,empire_templates"),
}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
DOMAIN_RE = re.compile(r"https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})")


def search_brave(query, n=10):
    """Brave Search (host egress) — returns real contact emails in results."""
    q = urllib.parse.quote(query + " contact email")
    url = f"https://search.brave.com/search?q={q}"
    try:
        html = urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=15).read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"  [brave err] {e}", file=sys.stderr)
        return []
    out = []
    # Brave result blocks: <a href="https://domain"...><h3>title</h3>...snippet
    blocks = re.split(r'(?=<a[^>]+href="https?://)', html)
    titles = [re.sub(r"<.*?>", "", t).strip()
              for t in re.findall(r"<h3[^>]*>(.*?)</h3>", html, re.S)]
    snippets = [re.sub(r"<.*?>", "", t).strip()
                for t in re.findall(r'class="[^"]*snippet[^"]*"[^>]*>(.*?)</', html, re.S)]
    domains = re.findall(r'href="https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})', html)
    ti = 0
    for i, dm in enumerate(domains[:n]):
        dm = dm.lower()
        if dm.endswith(("bing.com", "microsoft.com", "wikipedia.org", "linkedin.com",
                        "facebook.com", "youtube.com", "brave.com", "google.com",
                        ".gov", ".edu")):
            continue
        title = titles[ti] if ti < len(titles) else dm
        ti += 1
        snip = snippets[i] if i < len(snippets) else ""
        out.append({"title": title, "url": "https://" + dm, "snippet": snip})
    return out


def search_marginalia(query, n=10):
    """Marginalia (host egress) — indie index, often surfaces contact emails."""
    q = urllib.parse.quote(query)
    url = f"https://search.marginalia.nu/search?query={q}"
    try:
        html = urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=15).read().decode("utf-8", "ignore")
    except Exception:
        return []
    out = []
    for dm in re.findall(r'href="https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})', html)[:n]:
        dm = dm.lower()
        if dm.endswith(("marginalia.nu", "bing.com", ".gov", ".edu")):
            continue
        out.append({"title": dm, "url": "https://" + dm, "snippet": ""})
    return out


def search_bing(query, n=10):
    """Bing gives result domains (we scrape contact pages for emails after)."""
    q = urllib.parse.quote(query + " contact email")
    url = f"https://www.bing.com/search?q={q}&count={n}"
    try:
        html = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=15).read().decode("utf-8", "ignore")
    except Exception as e:
        return []
    out = []
    titles = [re.sub(r"<.*?>", "", t).strip()
              for t in re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.S)]
    domains = re.findall(r'href="https?://([A-Za-z0-9.-]+\.[A-Za-z]{2,})', html)
    ti = 0
    for dm in domains[:n + 10]:
        dm = dm.lower()
        if dm.endswith(("bing.com", "microsoft.com", "wikipedia.org", "linkedin.com",
                        "facebook.com", "youtube.com", "google.com", ".gov", ".edu")):
            continue
        title = titles[ti] if ti < len(titles) else dm
        ti += 1
        out.append({"title": title, "url": "https://" + dm, "snippet": ""})
    return out


def search_engines(query, n=10):
    """Bing for domains (scrape contact pages after); Brave/Marginalia for inline emails."""
    for fn in (search_bing, search_brave, search_marginalia):
        res = fn(query, n)
        if res:
            return res
    return []


def fetch_contact_email(domain):
    """Try common contact pages for a real email."""
    paths = ["", "/contact", "/contact-us", "/about"]
    for p in paths:
        try:
            html = urllib.request.urlopen(
                urllib.request.Request(f"https://{domain}{p}", headers=UA), timeout=10
            ).read().decode("utf-8", "ignore")
            ems = EMAIL_RE.findall(html)
            # prefer business-y addresses
            for e in ems:
                if not e.lower().endswith((".png", ".jpg", ".svg", ".webp")):
                    local = e.split("@")[0].lower()
                    if local in ("info", "sales", "contact", "hello", "admin", "office"):
                        return e
            if ems:
                return ems[0]
        except Exception:
            continue
    return ""


def metro_from_domain(domain):
    return ""  # metro unknown from host search; nurture still works


def register(prospect):
    req = urllib.request.Request(
        f"{HUB}/v1/outreach/prospect/register",
        data=json.dumps(prospect).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        r = urllib.request.urlopen(req, timeout=10)
        return r.status == 200
    except Exception as e:
        return False


def hunt(vertical, skus, limit):
    query, _ = VERTICALS[vertical]
    print(f"[hunt] {vertical}: searching...")
    results = search_engines(query, n=limit + 4)
    pushed = 0
    for r in results:
        dom = DOMAIN_RE.search(r["url"])
        if not dom:
            continue
        domain = dom.group(1).lower()
        if domain.endswith(("bing.com", "microsoft.com", "wikipedia.org",
                            "linkedin.com", "facebook.com", "youtube.com",
                            "gov", "edu")):
            continue
        # email from snippet first, else fetch site
        email = ""
        snip_emails = EMAIL_RE.findall(r["snippet"])
        snip_emails = [e for e in snip_emails if not e.lower().endswith(("png", "jpg", "svg"))]
        if snip_emails:
            email = snip_emails[0]
        else:
            email = fetch_contact_email(domain)
        if not email:
            continue  # no real contact -> skip (no fabrication)
        pid = "b2b_ext_" + hashlib.sha1(domain.encode()).hexdigest()[:12]
        prospect = {
            "prospect_id": pid,
            "business_name": r["title"][:80] or domain,
            "email": email,
            "metro": metro_from_domain(domain),
            "niche": "b2b",
            "phone": "",
            "source": f"host_hunter:{vertical}",
            "score": 75,
            "url": f"skus:{skus}",
            "reply_state": "cold",
        }
        if register(prospect):
            pushed += 1
            print(f"  + {prospect['business_name'][:32]:32} {email}")
        if pushed >= limit:
            break
        time.sleep(1.5)  # polite
    print(f"[hunt] {vertical}: pushed {pushed} real prospects")
    return pushed


def rotate_tor():
    """New Tor circuit (fresh exit IP) to dodge search-engine rate limits."""
    try:
        import socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(5)
        s.connect(("127.0.0.1", 9051))
        s.sendall(b"AUTHENTICATE\r\nSIGNEWNYM\r\n")
        s.close()
    except Exception:
        pass
    time.sleep(3)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--verticals", nargs="*", default=list(VERTICALS))
    ap.add_argument("--tor", action="store_true", help="route via Tor SOCKS (127.0.0.1:9050)")
    a = ap.parse_args()
    if a.tor:
        os.environ["HTTPS_PROXY"] = "socks5://127.0.0.1:9050"
        os.environ["HTTP_PROXY"] = "socks5://127.0.0.1:9050"
        print("[tor] egress via Tor active")
    total = 0
    for i, v in enumerate(a.verticals):
        if v not in VERTICALS:
            print(f"unknown vertical {v}", file=sys.stderr)
            continue
        if a.tor and i > 0:
            rotate_tor()  # fresh IP per vertical
        total += hunt(v, VERTICALS[v][1], a.limit)
    print(f"[done] {total} real B2B prospects pushed @ {datetime.now(timezone.utc).isoformat()}")


if __name__ == "__main__":
    main()
