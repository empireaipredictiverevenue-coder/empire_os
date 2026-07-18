#!/usr/bin/env python3
"""
Empire OS — Market Sweep System
Finds contractors in a given niche + metro via web search and inserts into crm_leads.

Usage:
    python3 market_sweep.py --niche roofing --metro "Phoenix, AZ" --limit 5
    python3 market_sweep.py --niche roofing --metro "Phoenix, AZ" --limit 5 --dry-run
    python3 market_sweep.py --niche construction --metro "Dallas, TX" --limit 10
"""

import argparse
import json
import os
import random
import re
import subprocess
import sys
import time
import uuid as uuid_mod
from datetime import datetime
from urllib.parse import quote, unquote, urlparse

import requests
from bs4 import BeautifulSoup

# ── Config ───────────────────────────────────────────────────────────────────
CONTAINER = "empire-hub"
DB_PATH = "/root/empire_os/empire_os.db"
# Inside container: direct SQLite. From host: use incus exec.
DIRECT_DB = "empire-hub" in os.uname().nodename
SOURCE_NAME = "market_sweep"
REQUEST_TIMEOUT = 15

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
]

AGGREGATOR_DOMAINS = {
    "angi.com", "thumbtack.com", "homedepot.com", "lowes.com",
    "yelp.com", "yellowpages.com", "bbb.org", "cybo.com",
    "manta.com", "porch.com", "homeadvisor.com", "buildzoom.com",
    "networx.com", "contractor.com", "findacontractor.com",
    "angieslist.com", "nextdoor.com", "facebook.com", "linkedin.com",
    "instagram.com", "pinterest.com", "twitter.com", "x.com",
    "youtube.com", "tiktok.com", "houzz.com", "modernize.com",
    "instantroofer.com", "bestpickreports.com", "arizonaroofers.com",
    "chamberofcommerce.com", "thespruce.com", "forbes.com",
    "wikipedia.org", "tripadvisor.com", "travel.usnews.com",
    "skyharbor.com", "visitphoenix.com", "phoenix.gov",
    "merriam-webster.com", "redfin.com", "residential.com",
    "fsresidential.com", "midwestresidential.org",
    "britannica.com", "mythosanthology.com",
}


def log(msg):
    print(f"[market_sweep] {msg}", flush=True)


def eprint(msg):
    print(f"[market_sweep] ERROR: {msg}", file=sys.stderr, flush=True)


def get_headers():
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


# ── DB Helpers ───────────────────────────────────────────────────────────────

def run_db(sql, params=None):
    """Execute SQL via direct SQLite (inside container) or via db_helper."""
    import sqlite3
    if DIRECT_DB:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        try:
            if params:
                cur = conn.execute(sql, params)
            else:
                cur = conn.execute(sql)
            conn.commit()
            # Return all rows as dicts
            rows = [dict(r) for r in cur.fetchall()] if cur.description else []
            return rows
        except Exception as e:
            eprint(f"DB exec error: {e}")
            return []
        finally:
            conn.close()
    else:
        payload = {"sql": sql, "params": params}
        payload_json = json.dumps(payload)
        cmd = ["incus", "exec", CONTAINER, "--", "python3", "/tmp/db_helper.py", payload_json]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                eprint(f"DB exec failed: {result.stderr.strip()}")
                return []
            out = result.stdout.strip()
            if out:
                return json.loads(out)
            return []
        except Exception as e:
            eprint(f"DB exec error: {e}")
            return []


def get_existing_business_names():
    """Return a set of business_names already in crm_leads."""
    rows = run_db("SELECT business_name FROM crm_leads WHERE business_name != ''")
    return set(r["business_name"].strip().lower() for r in rows if r.get("business_name"))


def insert_lead(lead, dry_run=False):
    """Insert a single lead into crm_leads."""
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f")
    lead_uid = f"ms_{uuid_mod.uuid4().hex[:12]}"

    sql = """
        INSERT INTO crm_leads (
            lead_uid, source, business_name, contact_name, email, phone,
            metro, niche, street, city, state, zip, website,
            status, created_at, updated_at
        ) VALUES (
            :lead_uid, :source, :business_name, :contact_name, :email, :phone,
            :metro, :niche, :street, :city, :state, :zip, :website,
            'raw', :created_at, :updated_at
        )
    """
    params = {
        "lead_uid": lead_uid,
        "source": SOURCE_NAME,
        "business_name": lead.get("business_name", ""),
        "contact_name": lead.get("contact_name", ""),
        "email": lead.get("email", ""),
        "phone": lead.get("phone", ""),
        "metro": lead.get("metro", ""),
        "niche": lead.get("niche", ""),
        "street": lead.get("street", ""),
        "city": lead.get("city", ""),
        "state": lead.get("state", ""),
        "zip": lead.get("zip", ""),
        "website": lead.get("website", ""),
        "created_at": now,
        "updated_at": now,
    }

    if dry_run:
        biz = lead.get("business_name", "")
        loc = ", ".join(filter(None, [lead.get("city"), lead.get("state")]))
        site = lead.get("website", "") or ""
        phone = lead.get("phone", "") or ""
        print(f"  [DRY-RUN] {biz} | {loc} | {site} | {phone}")
        return True

    run_db(sql, params)
    return True


# ── HTTP Fetch ───────────────────────────────────────────────────────────────

def fetch_url(url, retries=2):
    """Fetch a URL with retries and return (soup, status_code)."""
    for attempt in range(1, retries + 2):
        try:
            resp = requests.get(url, headers=get_headers(), timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                try:
                    return BeautifulSoup(resp.text, "html.parser"), 200
                except Exception:
                    return None, 200
            elif resp.status_code == 429:
                wait = attempt * 4
                log(f"Rate limited (429), waiting {wait}s...")
                time.sleep(wait)
            elif resp.status_code in (403, 401):
                time.sleep(1)
                return None, resp.status_code
            else:
                return None, resp.status_code
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt <= retries:
                time.sleep(attempt * 2)
        except Exception as e:
            eprint(f"Request error: {e}")
            if attempt <= retries:
                time.sleep(attempt * 2)
    return None, None


def is_aggregator(url):
    """Check if a URL points to an aggregator/platform site."""
    if not url:
        return True  # Can't verify, treat as aggregator
    url_lower = url.lower()
    for domain in AGGREGATOR_DOMAINS:
        if domain in url_lower:
            return True
    return False


def clean_business_name(name):
    """Clean up a business name string."""
    if not name:
        return ""
    name = re.sub(r'^(Top\s+\d+|Best\s+|The\s+\d+|Find\s+a\s+|Hire\s+(the\s+)?)', '', name, flags=re.I)
    name = re.sub(r'\s*(Reviews?|Ratings?|Near\s+Me|LLC|Inc|Corp|Co\s*\.?)\s*$', '', name, flags=re.I)
    name = name.strip(" -–—,|:;/")
    return name


def is_valid_contractor_name(name):
    """Heuristic check if a name looks like an actual contractor business."""
    if not name or len(name) < 4:
        return False
    name_lower = name.lower().strip()
    skip = [
        r'^(find|top|best|the|\d+)',
        r'(near me|reviews?|ratings?)$',
        r'^\d+$',
        r'^home$', r'^services$', r'^contact',
        r'^about', r'^search',
    ]
    for p in skip:
        if re.search(p, name_lower):
            return False
    return True


# ── Structured Data Extraction ──────────────────────────────────────────────

def extract_ldjson_address(soup):
    """Extract structured address from schema.org LD+JSON data."""
    result = {"street": "", "city": "", "state": "", "zip": ""}
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                addr = item.get("address") or {}
                if "@graph" in item:
                    for g in item["@graph"]:
                        if "address" in g:
                            addr = g["address"]
                            break
                if isinstance(addr, dict):
                    result["street"] = addr.get("streetAddress", "") or ""
                    result["city"] = addr.get("addressLocality", "") or ""
                    result["state"] = addr.get("addressRegion", "") or ""
                    result["zip"] = addr.get("postalCode", "") or ""
                    if any(v for v in result.values()):
                        return result
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
    return result


def extract_phones(soup):
    """Extract phone numbers from page."""
    phones = set()
    for a in soup.find_all("a", href=True):
        m = re.search(r'tel:(1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', a["href"])
        if m:
            phones.add(re.sub(r'^tel:', '', a["href"]).strip())
    # Schema.org
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            items = data if isinstance(data, list) else [data]
            for item in items:
                tel = str(item.get("telephone", ""))
                if re.search(r'\d{3}', tel):
                    phones.add(tel.strip())
        except (json.JSONDecodeError, AttributeError, TypeError):
            continue
    return list(phones)


def extract_emails(soup):
    """Extract email addresses from page."""
    emails = set()
    email_re = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
    for a in soup.find_all("a", href=True):
        m = re.search(r'mailto:([^?]+)', a["href"])
        if m:
            e = m.group(1).strip()
            if email_re.match(e):
                emails.add(e)
    text = soup.get_text(" ")
    for m in email_re.finditer(text):
        e = m.group(0)
        if not any(s in e for s in (".example.com", ".test.com", "noreply@", "no-reply@", "@domain.com", "{}[]")):
            emails.add(e)
    return list(emails)


def extract_address_from_text(text):
    """Extract address components from free text."""
    result = {"street": "", "city": "", "state": "", "zip": ""}

    # Full street address
    addr_re = re.compile(
        r'(\d+\s+[^,]{2,80}'
        r'(?:St(?:reet)?|Ave(?:nue)?|Rd(?:oad)?|Blvd(?:oulevard)?|'
        r'Dr(?:ive)?|Ln(?:ane)?|Ct(?:ourt)?|Way|Pkwy(?:arkway)?|'
        r'Hwy(?:ighway)?|Cir(?:cle)?|Ter(?:race)?|Pl(?:ace)?|'
        r'Run|Row|Sq(?:uare)?|Loop|Trail|Dr|Rd|Ave|St)'
        r'[^,.]{0,30}),?\s+'
        r'([A-Za-z\s.\']{1,60}?),?\s+'
        r'([A-Z]{2})\s+'
        r'(\d{5}(?:-\d{4})?)'
    )
    m = addr_re.search(text)
    if m:
        result["street"] = m.group(1).strip()
        result["city"] = m.group(2).strip()
        result["state"] = m.group(3).strip()
        result["zip"] = m.group(4).strip()
        return result

    # City, ST ZIP only
    cs_re = re.compile(r'([A-Za-z\s.\']{2,50}?),?\s+([A-Z]{2})\s+(\d{5}(?:-\d{4})?)')
    m = cs_re.search(text)
    if m:
        c = m.group(1).strip()
        if len(c) < 40 and c:
            result["city"] = c
            result["state"] = m.group(2).strip()
            result["zip"] = m.group(3).strip()
    return result


def enrich_from_website(lead):
    """Fetch the lead's website and extract richer data."""
    url = lead.get("website")
    if not url or is_aggregator(url) or not url.startswith("http"):
        return lead

    parsed = urlparse(url)
    if not parsed.netloc:
        return lead

    time.sleep(0.8 + random.random() * 0.5)
    soup, status = fetch_url(url)
    if not soup:
        return lead

    # Extract address (if missing)
    if not lead.get("street"):
        addr = extract_ldjson_address(soup)
        lead.update(addr)

    # Extract phone (if missing)
    if not lead.get("phone"):
        phones = extract_phones(soup)
        if phones:
            lead["phone"] = phones[0]

    # Extract email (if missing)
    if not lead.get("email"):
        emails = extract_emails(soup)
        if emails:
            lead["email"] = emails[0]

    # Improve name from page title
    if len(lead.get("business_name", "")) < 6:
        title = soup.find("title")
        if title:
            t = title.get_text(strip=True)
            for sep in [" | ", " — ", " – ", " - ", " // ", " :: "]:
                if sep in t:
                    t = t.split(sep)[0].strip()
                    break
            if t and 3 < len(t) < 80:
                lead["business_name"] = t

    return lead


# ── Search Sources ───────────────────────────────────────────────────────────

def _load_env():
    """Load .env if available."""
    for p in ["/root/empire_os/.env", "/root/.env"]:
        try:
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
            return
        except FileNotFoundError:
            continue

def search_serply(niche, metro, limit):
    """Search via Serply API, return lead dicts matching pipeline shape."""
    _load_env()
    import json as _json, urllib.request, urllib.parse
    KEY = os.environ.get("SERPLY_KEY", os.environ.get("SERLY_KEY", ""))
    if not KEY:
        return [], 0

    metro_parts = [p.strip() for p in metro.split(",")]
    metro_city = metro_parts[0] if metro_parts else metro
    metro_state = metro_parts[1] if len(metro_parts) > 1 else ""
    queries = [
        f"{niche} contractors {metro_city} {metro_state}",
        f"{niche} {metro_city} {metro_state}",
        f'{niche} company {metro_city}',
    ]

    leads = []
    seen_urls = set()
    seen_names = set()
    status = 0

    for query in queries:
        if len(leads) >= limit:
            break
        try:
            req = urllib.request.Request(
                "https://api.serply.io/v1/search/q=" + urllib.parse.quote(query),
                headers={"X-API-KEY": KEY, "User-Agent": "EmpireOS/1.0"})
            resp = urllib.request.urlopen(req, timeout=15)
            data = _json.loads(resp.read().decode())
            status = resp.status
            for r in data.get("results", []):
                if len(leads) >= limit:
                    break
                link = r.get("link", "").strip()
                title = r.get("title", "").strip()
                if not link or not title or link in seen_urls:
                    continue
                seen_urls.add(link)
                if is_aggregator(link):
                    continue
                name = clean_business_name(title)
                if not is_valid_contractor_name(name):
                    continue
                nk = name.lower().strip()
                if nk in seen_names:
                    continue
                seen_names.add(nk)
                leads.append({
                    "business_name": name,
                    "website": link,
                    "phone": "",
                    "email": "",
                    "street": "",
                    "city": "",
                    "state": "",
                    "zip": "",
                    "metro": metro,
                    "niche": niche,
                })
        except Exception as e:
            log(f"    [serply err] {str(e)[:50]}")
            continue

    return leads, status

def search_duckduckgo_lite(niche, metro, limit):
    """Search DuckDuckGo Lite (no-JS version) for contractor listings."""
    target_metro = metro
    # Parse city, state from metro
    metro_parts = [p.strip() for p in metro.split(",")]
    metro_city = metro_parts[0] if metro_parts else metro
    metro_state = metro_parts[1] if len(metro_parts) > 1 else ""

    # Try multiple query formulations for better coverage
    queries = [
        f"{niche} contractors {metro_city} {metro_state}",
        f"{niche} {metro_city} {metro_state}",
        f'{niche} company {metro_city}',
        f'{metro_city} {niche}',
    ]

    leads = []
    seen_urls = set()
    seen_names = set()
    status = None

    for query in queries:
        if len(leads) >= limit:
            break
        try:
            resp = requests.post(
                "https://lite.duckduckgo.com/lite/",
                data={"q": query},
                headers=get_headers(),
                timeout=REQUEST_TIMEOUT,
            )
            status = resp.status_code
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # DDG Lite results: <a class="result-link"> for each result
            result_links = soup.find_all("a", class_="result-link")
            if not result_links:
                # Fallback: any external link in the page
                result_links = [
                    a for a in soup.find_all("a", href=True)
                    if a.get("href", "").startswith("http")
                    and "duckduckgo" not in a["href"]
                ]

            for a in result_links:
                if len(leads) >= limit:
                    break

                href = a.get("href", "").strip()
                text = a.get_text(strip=True) or ""

                if not href or not text or href in seen_urls:
                    continue
                seen_urls.add(href)

                if is_aggregator(href):
                    continue

                name = clean_business_name(text)
                if not is_valid_contractor_name(name):
                    continue

                nk = name.lower().strip()
                if nk in seen_names:
                    continue
                seen_names.add(nk)

                lead = {
                    "business_name": name,
                    "website": href,
                    "phone": "",
                    "email": "",
                    "street": "",
                    "city": "",
                    "state": "",
                    "zip": "",
                    "metro": metro,
                    "niche": niche,
                }

                leads.append(lead)

            if result_links:
                log(f"  Query '{query[:50]}' -> {len(result_links)} raw, {len(leads)} kept (cumulative)")

        except Exception as e:
            eprint(f"DDG Lite error on '{query[:30]}': {e}")

    return leads, status or 0


def search_bing_rss(niche, metro, limit):
    """Search Bing RSS feed for contractor listings."""
    metro_parts = [p.strip() for p in metro.split(",")]
    metro_city = metro_parts[0] if metro_parts else metro
    queries = [
        f"{niche} contractors {metro_city}",
        f"{niche} company {metro_city} {metro_parts[1] if len(metro_parts) > 1 else ''}",
    ]

    leads = []
    seen_urls = set()
    seen_names = set()

    for query in queries:
        if len(leads) >= limit:
            break
        query = query.strip()
        if not query:
            continue

        url = f"https://www.bing.com/search?q={quote(query)}&count={limit * 2 + 3}&format=rss"
        resp = requests.get(url, headers=get_headers(), timeout=REQUEST_TIMEOUT)
        if resp.status_code != 200:
            continue

        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(resp.text)
            items = root.findall(".//item")
        except Exception:
            continue

        for item in items:
            if len(leads) >= limit:
                break

            link = (item.findtext("link") or "").strip()
            title = (item.findtext("title") or "").strip()

            if not link or not title or link in seen_urls:
                continue
            seen_urls.add(link)

            if is_aggregator(link):
                continue

            name = clean_business_name(title)
            if not is_valid_contractor_name(name):
                continue

            nk = name.lower().strip()
            if nk in seen_names:
                continue
            seen_names.add(nk)

            lead = {
                "business_name": name,
                "website": link,
                "phone": "",
                "email": "",
                "street": "",
                "city": "",
                "state": "",
                "zip": "",
                "metro": metro,
                "niche": niche,
            }

            # Try to extract address from description
            desc = item.findtext("description") or ""
            if desc:
                addr = extract_address_from_text(desc)
                lead.update(addr)

            leads.append(lead)

    return leads, resp.status_code if 'resp' in dir() else 0


# ── Core Logic ───────────────────────────────────────────────────────────────

def deduplicate_leads(leads, existing_names):
    """Remove leads whose business_name already exists or don't look like contractors."""
    new_leads = []
    dup_count = 0
    skip_count = 0
    for lead in leads:
        name = (lead.get("business_name") or "").strip().lower()
        if not name or len(name) < 4:
            skip_count += 1
            continue
        if name in existing_names:
            dup_count += 1
        else:
            new_leads.append(lead)
    return new_leads, dup_count, skip_count


def run_sweep(niche, metro, limit, dry_run=False):
    """Main sweep function."""
    log(f"Starting sweep: niche='{niche}', metro='{metro}', limit={limit}, dry_run={dry_run}")

    existing_names = get_existing_business_names()
    total_existing = len(existing_names)
    log(f"Existing leads in DB: {total_existing}")

    all_leads = []
    source_statuses = []

    # Source 1: Serply (primary)
    results, status = search_serply(niche, metro, limit + 3)
    all_leads.extend(results)
    source_statuses.append(f"Serply={status}")
    log(f"Serply -> {len(results)} leads (status={status})")

    # Source 2: Bing RSS (fallback)
    if len(all_leads) < limit:
        results, status = search_bing_rss(niche, metro, limit - len(all_leads) + 3)
        all_leads.extend(results)
        source_statuses.append(f"Bing={status}")
        log(f"Bing RSS -> {len(results)} leads (status={status})")

    # Dedup against DB
    new_leads, dup_count, skip_count = deduplicate_leads(all_leads, existing_names)
    log(f"After DB dedup: {len(new_leads)} new, {dup_count} dupes, {skip_count} filtered")

    # Cross-source dedup
    seen_names = set()
    unique = []
    for lead in new_leads:
        nk = (lead.get("business_name") or "").strip().lower()
        if nk in seen_names:
            continue
        seen_names.add(nk)
        unique.append(lead)
    new_leads = unique[:limit]

    # Enrich: fetch websites for phone/email/address
    log("Enriching leads from their websites...")
    enriched = []
    for lead in new_leads:
        e = enrich_from_website(lead)
        enriched.append(e)

    new_leads = enriched

    # Output / Insert
    inserted = 0
    if dry_run:
        print(f"\n{'=' * 70}")
        print(f"  DRY RUN — Would insert {len(new_leads)} leads for {niche} in {metro}")
        print(f"  Sources: {', '.join(source_statuses)}")
        print(f"{'=' * 70}")
        for i, lead in enumerate(new_leads, 1):
            loc = ", ".join(filter(None, [lead.get("street"), lead.get("city"), lead.get("state"), lead.get("zip")]))
            print(f"\n  [{i}] {lead.get('business_name', '')}")
            if lead.get("phone"):   print(f"      Phone:   {lead['phone']}")
            if lead.get("email"):   print(f"      Email:   {lead['email']}")
            if lead.get("website"): print(f"      Web:     {lead['website']}")
            if loc:                 print(f"      Address: {loc}")
        print(f"\n{'—' * 70}")
        print(f"  Summary: {len(new_leads)} new | {dup_count} dupes | {skip_count} filtered")
        print(f"  Total existing in DB: {total_existing}")
        print(f"{'=' * 70}")
    else:
        for lead in new_leads:
            insert_lead(lead, dry_run=False)
            inserted += 1
        total_now = total_existing + inserted
        print(f"\n{'=' * 70}")
        print(f"  SWEEP COMPLETE — {niche} in {metro}")
        print(f"  Sources: {', '.join(source_statuses)}")
        print(f"{'=' * 70}")
        print(f"  New leads found:           {len(new_leads)}")
        print(f"  Leads inserted:            {inserted}")
        print(f"  Duplicates skipped:        {dup_count}")
        print(f"  Non-contractor filtered:   {skip_count}")
        print(f"  Total in DB:               {total_now}")
        print(f"{'=' * 70}")

    return {
        "niche": niche,
        "metro": metro,
        "new_leads": len(new_leads),
        "inserted": inserted if not dry_run else 0,
        "duplicates_skipped": dup_count,
        "filtered_non_contractor": skip_count,
        "total_in_db": total_existing + (inserted if not dry_run else 0),
        "sources": source_statuses,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Empire OS Market Sweep — find and import contractor leads"
    )
    parser.add_argument("--niche", required=True, help="Niche (e.g. roofing, construction)")
    parser.add_argument("--metro", required=True, help="Metro area (e.g. 'Phoenix, AZ')")
    parser.add_argument("--limit", type=int, default=20, help="Max leads to find (default: 20)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be inserted without inserting")
    args = parser.parse_args()

    # When running via incus exec (not direct), verify db helper exists
    if not DIRECT_DB:
        ret = subprocess.run(
            ["incus", "exec", CONTAINER, "--", "test", "-f", "/tmp/db_helper.py"],
            capture_output=True, text=True
        )
        if ret.returncode != 0:
            eprint("DB helper not found in container at /tmp/db_helper.py!")
            eprint("Please ensure /tmp/db_helper.py exists inside the empire-hub container")
            sys.exit(1)

    result = run_sweep(
        niche=args.niche.strip(),
        metro=args.metro.strip(),
        limit=args.limit,
        dry_run=args.dry_run,
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
