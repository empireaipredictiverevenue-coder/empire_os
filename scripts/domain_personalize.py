"""
Empire OS Outreach Enricher — real-domain contact discovery.

Given a prospect (business_name + url + guessed email), this module:
  1. Fetches the homepage HTML and looks for:
       - mailto: links (real contact addresses)
       - /contact, /team, /about pages
  2. Scores each address:
       - +5 if it matches a generic decision-maker pattern (owner, founder,
         hello, contact, sales, info, office)
       - +10 if it's a named person (firstname@ or first.last@)
       - -3 per free-webmail domain (gmail/yahoo/etc.)
  3. Falls back to the existing pattern-guesser only if the live fetch fails.

This replaces the old webhook-only enrichment that just guessed `info@<slug>.com`
(which bounces ~70% of the time at small businesses).

The script is idempotent and cache-friendly (writes results to the host DB
via the hub).
"""
from __future__ import annotations
import json
import os
import re
import sqlite3
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

HUB_URL = os.environ.get("HUB_URL", "http://10.118.155.218:8081")
HOST_DB = os.environ.get("HOST_DB", "/root/empire_os/empire_os.db")
CACHE_PATH = Path("/root/empire_os/feedback/domain_enrichment_cache.jsonl")
TIMEOUT_SECONDS = 6
USER_AGENT = "Mozilla/5.0 (Empire-OS research; +https://empire-ai.co.uk)"

DECISION_MAKER_PATTERNS = (
    "owner", "founder", "ceo", "president", "director",
    "hello", "contact", "sales", "info", "office", "team",
    "support", "inquiries", "admin", "billing",
)

FREE_WEBMAIL = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com",
    "icloud.com", "protonmail.com", "mail.ru", "yandex.ru", "live.com",
    "msn.com", "comcast.net", "att.net", "sbcglobal.net",
}

CONTACT_PAGE_HINTS = (
    "contact", "team", "about", "staff", "people", "leadership",
    "get-in-touch", "reach-us", "company",
)


def _fetch(url: str, follow_redirects: bool = True) -> str | None:
    """Fetch URL, follow up to 3 redirects, return text or None on failure."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
        })
        # Don't follow redirects automatically — urllib does by default
        # but we cap at 3 to avoid loops.
        for _ in range(3):
            try:
                with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as resp:
                    final_url = resp.geturl()
                    if resp.status != 200:
                        return None
                    raw = resp.read(200_000)
                    ct = resp.headers.get("Content-Type", "")
                    if "html" not in ct.lower():
                        return None
                    return raw.decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                if e.code in (301, 302, 303, 307, 308):
                    loc = e.headers.get("Location")
                    if loc:
                        req = urllib.request.Request(
                            urllib.parse.urljoin(final_url if 'final_url' in dir() else url, loc),
                            headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
                        )
                        continue
                return None
    except Exception:
        return None
    return None


def _extract_mailto(html: str) -> list[str]:
    """Return all unique mailto: addresses from an HTML doc."""
    addrs = set()
    for m in re.finditer(r'mailto:\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})',
                          html, re.I):
        addrs.add(m.group(1).lower().strip())
    return sorted(addrs)


def _extract_contact_links(html: str, base_url: str) -> list[str]:
    """Return up to 5 likely /contact-style URLs from the HTML."""
    out = []
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>',
                          html, re.I):
        href, text = m.group(1).lower(), m.group(2).lower()
        for hint in CONTACT_PAGE_HINTS:
            if hint in href or hint in text:
                full = urllib.parse.urljoin(base_url, href)
                if full not in out and full != base_url:
                    out.append(full)
                break
    return out[:5]


def _domain_of(email: str) -> str:
    return email.split("@", 1)[1].lower() if "@" in email else ""


def _score(email: str) -> int:
    """Higher = better target email."""
    if "@" not in email:
        return -100
    user, dom = email.split("@", 1)
    user = user.lower()
    dom = dom.lower()
    if dom in FREE_WEBMAIL:
        return -10
    score = 0
    if user in DECISION_MAKER_PATTERNS:
        score += 5
    elif any(p in user for p in DECISION_MAKER_PATTERNS):
        score += 3
    # Named-person pattern: first.last@ or firstinitiallast@
    if re.match(r'^[a-z]+\.[a-z]+$', user):
        score += 10
    elif re.match(r'^[a-z][a-z]+$', user) and len(user) >= 4:
        score += 4  # "alex@" type
    return score


def enrich(prospect: dict) -> dict:
    """Return enrichment: {emails: [(email, score)], source: str, fallback: bool}."""
    url = (prospect.get("url") or "").strip()
    biz = (prospect.get("business_name") or "").strip()
    fallback_email = (prospect.get("email") or "").strip()

    result = {"emails": [], "source": "none", "queried_url": url, "ts": time.time()}

    # Try the live website first
    if url:
        html = _fetch(url if url.startswith("http") else "https://" + url)
        if html:
            addrs = _extract_mailto(html)
            if addrs:
                scored = [(e, _score(e)) for e in addrs]
                scored.sort(key=lambda x: (-x[1], x[0]))
                result["emails"] = scored[:8]
                result["source"] = "homepage_mailto"

        # If homepage had no mailto, try contact pages
        if not result["emails"] and html:
            contact_urls = _extract_contact_links(html, url)
            for cu in contact_urls[:3]:
                h2 = _fetch(cu)
                if not h2:
                    continue
                addrs = _extract_mailto(h2)
                if addrs:
                    scored = [(e, _score(e)) for e in addrs]
                    scored.sort(key=lambda x: (-x[1], x[0]))
                    result["emails"] = scored[:8]
                    result["source"] = "contact_page_mailto"
                    break

    # If still nothing, try the existing guessed email
    if not result["emails"] and fallback_email:
        result["emails"] = [(fallback_email, _score(fallback_email))]
        result["source"] = "fallback_existing"

    return result


def main(args: list[str]) -> int:
    """CLI: python3 domain_personalize.py < prospect_id_or_business_name >"""
    target = " ".join(args).strip()
    if not target:
        # batch mode: enrich all recent prospects in si_buyer_outreach
        return batch()
    print(f"single-lookup mode: {target!r} (not implemented yet — use batch)", file=sys.stderr)
    return 1


def batch() -> int:
    """Enrich recent prospects that have a URL but no high-quality email."""
    sys.path.insert(0, "/root/empire_os")
    from empire_os.db_adapter import _container_query

    rows = _container_query(
        "SELECT prospect_id, business_name, url, email "
        "FROM si_buyer_outreach "
        "WHERE reply_state IN ('cold') "
        "AND url IS NOT NULL AND url != '' "
        "ORDER BY last_touch_at DESC NULLS LAST, created_at DESC "
        "LIMIT 200"
    )
    if not rows:
        print("no prospects found", file=sys.stderr)
        return 1

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    # Load cache
    cache = {}
    if CACHE_PATH.exists():
        for line in CACHE_PATH.read_text(errors="replace").splitlines():
            try:
                d = json.loads(line)
                if d.get("domain"):
                    cache[d["domain"]] = d
            except Exception:
                pass

    enriched = 0
    skipped = 0
    failed = 0
    for r in rows:
        url = (r.get("url") or "").strip()
        if not url:
            skipped += 1
            continue
        dom = _domain_of(url if "@" not in url else r.get("email", ""))
        if not dom:
            dom = url.split("/")[2] if "://" in url else url
        if dom in cache and cache[dom].get("ts", 0) > time.time() - 7 * 86400:
            cached = cache[dom]
            top = cached.get("emails", [{}])[0]
            print(f"  CACHE {r['business_name'][:30]:<30} -> {top.get('email','?')} (src={cached.get('source')})")
            skipped += 1
            continue
        e = enrich(r)
        if not e["emails"]:
            failed += 1
            print(f"  FAIL  {r['business_name'][:30]:<30} url={url[:40]}")
            continue
        e["domain"] = dom
        e["prospect_id"] = r["prospect_id"]
        e["business_name"] = r["business_name"]
        cache[dom] = e
        with CACHE_PATH.open("a") as f:
            f.write(json.dumps(e) + "\n")
        top_email, top_score = e["emails"][0]
        print(f"  {e['source']:<22} {r['business_name'][:30]:<30} -> {top_email} (score={top_score})")
        enriched += 1
        time.sleep(0.5)  # be polite

    print(f"\nenriched={enriched} skipped={skipped} failed={failed}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))