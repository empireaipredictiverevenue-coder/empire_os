"""Lead Enrichment Engine — Multi-source data enrichment with waterfall logic.

Enrichment providers are modular. Each takes a lead dict and returns
fields it discovered. The waterfall runs providers in priority order;
once a field is set by a higher-priority source, lower sources don't
overwrite it.

Built-in providers (free / no API key):
  1. website_scraper    — scrape lead's website for business info
  2. google_search      — scrape Google for social/business data
  3. bbb_lookup         — BBB profile lookup by business name+state
  4. whois_lookup       — WHOIS domain data
  5. email_pattern      — guess email from business name + domain

External providers (stubs — drop in API keys):
  6. clearbit           — Clearbit Enrichment API
  7. hunter             — Hunter.io email finder
  8. people_data_labs   — PeopleDataLabs enrichment
  9. google_places      — Google Places API business data
"""
from __future__ import annotations

import json
import logging
import os
import re
import socket
import time
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Optional

import requests

logger = logging.getLogger("enrichment")

# ── Priority-ordered provider list ──────────────────────────────────
# Higher priority = runs first. Falls back through the list.
PRIORITY = [
    "website_scraper",   # free: scrape biz site for email/phone
    "bbb_lookup",        # free: BBB rating/years
    "whois_lookup",      # free: domain RDAP
    "email_pattern",     # free: guess info@domain
    "google_search",      # free: SERP scrape phone/site
    "ddg_search",        # free: DuckDuckGo HTML SERP email scrape (no key)
    "bing_search",       # free: Bing SERP email scrape (no key)
    # External (verify-only, free tiers):
    "hunter",            # Hunter.io verified emails (HUNTER_API_KEY, 25/mo)
    # "prospeo",          # Prospeo API fully deprecated (all endpoints 404)
    # "apollo",           # Apollo free plan 403s all search APIs (paid only)
    # "clearbit",
    # "people_data_labs",
    # "google_places",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0.0.0 Safari/537.36"
)


def _http_get(url: str, timeout: int = 10) -> Optional[str]:
    try:
        r = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        logger.debug("HTTP error %s: %s", url, e)
        return None


def _safe_domain(website: str) -> str:
    if not website:
        return ""
    website = website.strip().lower()
    if not website.startswith("http"):
        website = "https://" + website
    try:
        return urllib.parse.urlparse(website).netloc
    except Exception:
        return website


# ── Providers ───────────────────────────────────────────────────────


def website_scraper(lead: dict) -> dict:
    """Scrape lead's website for meta data, contact info, social links."""
    result = {}
    website = lead.get("website", "")
    if not website and lead.get("business_name"):
        # Try guess domain
        name = lead["business_name"].lower().replace(" ", "").replace(".", "")
        website = f"https://{name}.com"

    domain = _safe_domain(website)
    if not domain:
        return result

    html = _http_get(f"https://{domain}")
    if not html:
        return result

    # Title
    m = re.search(r'<title>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
    if m:
        title = m.group(1).strip()
        if not result.get("business_name"):
            result["business_name"] = title.split("|")[0].split(" - ")[0].strip()

    # Meta description
    m = re.search(r'<meta\s+name="description"\s+content="([^"]*)"', html, re.IGNORECASE)
    if m:
        result["meta_description"] = m.group(1).strip()[:500]

    # Social links
    socials = []
    for pattern, platform in [
        (r'facebook\.com/[a-zA-Z0-9.]+', "facebook"),
        (r'linkedin\.com/(company|in)/[a-zA-Z0-9-]+', "linkedin"),
        (r'twitter\.com/[a-zA-Z0-9_]+', "twitter"),
        (r'instagram\.com/[a-zA-Z0-9_.]+', "instagram"),
        (r'youtube\.com/@?[a-zA-Z0-9_-]+', "youtube"),
    ]:
        found = re.findall(pattern, html, re.IGNORECASE)
        for f in found[:2]:
            url = f"https://{f}" if not f.startswith("http") else f
            if url not in socials:
                socials.append(url)
    if socials:
        result["social_links"] = json.dumps(socials)

    # Phone
    phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', html)
    if phones and not lead.get("phone"):
        result["phone"] = phones[0]

    # Email
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
    biz_emails = [e for e in emails if not e.endswith((".png", ".jpg", ".gif", ".svg")) and domain in e]
    if biz_emails and not lead.get("email"):
        result["email"] = biz_emails[0]

    return result


def bbb_lookup(lead: dict) -> dict:
    """Scrape BBB profile for rating, accreditation, years in business."""
    result = {}
    name = lead.get("business_name", "")
    state = lead.get("state", "") or lead.get("metro", "")[-2:]
    if not name or len(name) < 3:
        return result

    query = urllib.parse.quote(f"{name} {state}")
    html = _http_get(f"https://www.bbb.org/search?find_text={query}&find_loc={state}")
    if not html:
        return result

    # Rating
    m = re.search(r'BBB Rating[^<]*<[^>]*>([A-F][+]?)</', html, re.IGNORECASE | re.DOTALL)
    if m:
        result["bbb_rating"] = m.group(1).strip()

    # Years in business
    m = re.search(r'Years in Business[^<]*<[^>]*>(\d+)', html, re.IGNORECASE)
    if m:
        try:
            founded = datetime.now().year - int(m.group(1))
            result["year_founded"] = founded
        except ValueError:
            pass

    # Accredited
    if "Accredited Business" in html:
        result["bbb_accredited"] = True

    return result


def whois_lookup(lead: dict) -> dict:
    """Look up domain WHOIS for creation date, registrar info."""
    result = {}
    website = lead.get("website", "")
    domain = _safe_domain(website)
    if not domain:
        return result

    try:
        info = socket.gethostbyname_ex(domain)
        result["domain_ip"] = info[2][0] if info[2] else ""
    except socket.gaierror:
        pass

    # WHOIS via rdap (free, no key)
    try:
        r = requests.get(
            f"https://rdap.verisign.com/com/v1/domain/{domain}",
            headers={"Accept": "application/json"},
            timeout=8,
        )
        if r.status_code == 200:
            data = r.json()
            for ev in data.get("events", []):
                if ev.get("eventAction") == "registration":
                    result["domain_created"] = ev.get("eventDate", "")[:10]
                    break
    except Exception:
        pass

    return result


def email_pattern(lead: dict) -> dict:
    """Guess email from business name and domain if not already set."""
    result = {}
    if lead.get("email"):
        return result
    website = lead.get("website", "")
    name = lead.get("business_name", "")
    domain = _safe_domain(website)
    if not domain:
        return result
    if not name:
        return result

    patterns = [
        f"info@{domain}",
        f"contact@{domain}",
        f"hello@{domain}",
    ]
    # Common pattern: firstname@domain
    for p in patterns:
        result["email"] = p
        break  # just suggest info@
    return result


def google_search(lead: dict) -> dict:
    """Search Google for business info (no API key — scrapes SERP)."""
    result = {}
    name = lead.get("business_name", "")
    city = lead.get("city", "") or lead.get("metro", "")
    if not name:
        return result
    q = urllib.parse.quote(f"{name} {city} roofing contractor")
    html = _http_get(f"https://www.google.com/search?q={q}&hl=en")
    if not html:
        return result

    # Try extract phone
    phones = re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', html)
    if phones and not lead.get("phone"):
        # Filter out obvious fake numbers
        real = [p for p in phones if not any(x in p for x in ["555-", "000-"])]
        if real:
            result["phone"] = real[0]

    # Try extract website
    ws = re.findall(rf'{re.escape(name.split()[0] if name.split() else "")}[^"]*\.com', html, re.IGNORECASE)
    if ws and not lead.get("website"):
        result["website"] = ws[0]

    return result


def hunter(domain: str = "", email_or_domain: str = "") -> dict:
    """Hunter.io email finder/verifier (free tier: 25 requests/mo).
    Reads HUNTER_API_KEY from env. Verified emails only — no guessing.
    Falls back silently if no key / quota exhausted.
    """
    result = {}
    key = os.environ.get("HUNTER_API_KEY", "")
    if not key:
        return result
    d = domain or _safe_domain(email_or_domain)
    if not d:
        return result
    try:
        r = requests.get(
            "https://api.hunter.io/v2/domain-search",
            params={"domain": d, "api_key": key, "limit": 1},
            timeout=12,
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            ems = data.get("emails") or []
            if ems:
                e = ems[0].get("value", "")
                if e and "@" in e:
                    result["email"] = e
                    if ems[0].get("phone") and not result.get("phone"):
                        result["phone"] = ems[0]["phone"]
        # 401/403/429 -> key bad or quota gone; return empty, don't crash
    except Exception:
        pass
    return result


def apollo(domain: str = "", email_or_domain: str = "") -> dict:
    """Apollo.io email finder (free tier: 100 requests/mo, no card).
    Reads APOLLO_API_KEY from env. Returns verified work emails.
    Falls back silently if no key / quota exhausted.
    """
    result = {}
    key = os.environ.get("APOLLO_API_KEY", "")
    if not key:
        return result
    d = domain or _safe_domain(email_or_domain)
    if not d:
        return result
    try:
        # Apollo org people search by domain
        r = requests.post(
            "https://api.apollo.io/v1/mixed_people/search",
            headers={"Content-Type": "application/json", "X-Api-Key": key},
            json={"q_organization_domains": [d], "page": 1, "per_page": 5},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json().get("people", []) or []
            for p in data:
                e = p.get("email") or p.get("personal_emails", [None])[0] if p.get("personal_emails") else None
                if not e and p.get("email"):
                    e = p["email"]
                if e and "@" in e and "users" not in e and "apollo" not in e:
                    result["email"] = e
                    # grab a phone if present
                    phone = p.get("phone") or p.get("sanitized_phone")
                    if phone and not result.get("phone"):
                        result["phone"] = phone
                    break
        # 401/403/429 -> key bad or quota gone; return empty, don't crash
    except Exception:
        pass
    return result


def prospeo(domain: str = "", email_or_domain: str = "") -> dict:
    """Prospeo.io email finder (free tier: 50 requests/mo, no card).
    Reads PROSPEO_API_KEY from env. Returns verified work emails.
    Falls back silently if no key / quota exhausted.
    """
    result = {}
    key = os.environ.get("PROSPEO_API_KEY", "")
    if not key:
        return result
    d = domain or _safe_domain(email_or_domain)
    if not d:
        return result
    try:
        r = requests.post(
            "https://api.prospeo.io/api/v1/domain-search",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={"domain": d, "limit": 1},
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json().get("data", {}) or {}
            ems = data.get("emails") or data.get("results") or []
            if ems:
                e = ems[0].get("email") or ems[0].get("value") or (ems[0] if isinstance(ems[0], str) else "")
                if e and "@" in e:
                    result["email"] = e
        # 401/403/429 -> key bad or quota gone; return empty, don't crash
    except Exception:
        pass
    return result


def _extract_emails(text: str, domain: str = "") -> list:
    """Extract plausible business emails from raw HTML/text."""
    if not text:
        return []
    found = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
    out = []
    for e in found:
        el = e.lower()
        if el.endswith((".png", ".jpg", ".gif", ".svg", ".webp")):
            continue
        if "example" in el or "invalid" in el or "sentry" in el:
            continue
        if domain and domain not in el:
            continue  # only keep domain-matching emails
        if el not in out:
            out.append(el)
    return out


def ddg_search(lead: dict) -> dict:
    """DuckDuckGo HTML SERP scrape for business email (free, no key).
    DuckDuckGo's html endpoint blocks bots less than Google.
    """
    result = {}
    name = lead.get("business_name", "") or ""
    domain = _safe_domain(lead.get("website", ""))
    if not name and not domain:
        return result
    q = f"{name} {domain}" if domain else name
    try:
        r = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": f'{q} email contact'},
            headers={"User-Agent": USER_AGENT},
            timeout=12,
        )
        if r.status_code == 200:
            ems = _extract_emails(r.text, domain)
            if ems:
                result["email"] = ems[0]
    except Exception:
        pass
    return result


def bing_search(lead: dict) -> dict:
    """Bing SERP scrape for business email (free, no key).
    Bing rate-limits less aggressively than Google for HTML scraping.
    """
    result = {}
    name = lead.get("business_name", "") or ""
    domain = _safe_domain(lead.get("website", ""))
    if not name and not domain:
        return result
    q = f"{name} {domain}" if domain else name
    try:
        r = requests.get(
            "https://www.bing.com/search",
            params={"q": f'{q} email contact'},
            headers={"User-Agent": USER_AGENT},
            timeout=12,
        )
        if r.status_code == 200:
            ems = _extract_emails(r.text, domain)
            if ems:
                result["email"] = ems[0]
    except Exception:
        pass
    return result


# ── Waterfall Engine ────────────────────────────────────────────────


def get_enrichment_score(lead: dict) -> float:
    """Calculate data completeness score (0-100)."""
    score = 0.0
    fields = [
        ("business_name", 15),
        ("contact_name", 10),
        ("email", 15),
        ("phone", 15),
        ("website", 10),
        ("street", 5),
        ("city", 5),
        ("state", 5),
        ("zip", 5),
        ("nico", 5),  # niche / industry
        ("license_no", 5),
        ("social_links", 5),
    ]
    for field, weight in fields:
        val = lead.get(field)
        if val and str(val).strip() and str(val) not in ("[]", "{}", '""'):
            score += weight
    return min(score, 100.0)


async def enrich_lead(backend, lead_id: int) -> dict:
    """Run the enrichment waterfall for a single lead. Returns what was found."""
    row = backend.execute("SELECT * FROM crm_leads WHERE id = ?", (lead_id,)).fetchone()
    if not row:
        raise ValueError(f"Lead id={lead_id} not found")

    lead = dict(row)
    found_fields = {}
    total_new = 0

    for provider_name in PRIORITY:
        try:
            provider_fn = globals().get(provider_name)
            if not provider_fn:
                continue
            result = provider_fn(lead)
            if not result:
                continue

            # Apply waterfall: only set fields not already set
            new_for_source = 0
            for k, v in result.items():
                if k not in found_fields and k not in lead or not lead.get(k):
                    found_fields[k] = v
                    new_for_source += 1

            total_new += new_for_source
            status = "success" if new_for_source > 0 else "skipped"

            # Log enrichment attempt
            backend.execute(
                "INSERT INTO crm_enrichment_log (lead_id, source, status, fields_found) VALUES (?, ?, ?, ?)",
                (lead_id, provider_name, status, new_for_source),
            )

            # Merge found fields into lead dict so next provider sees them
            if new_for_source > 0:
                lead.update(found_fields)

        except Exception as e:
            logger.warning("Enrichment %s failed for lead %s: %s", provider_name, lead_id, e)
            backend.execute(
                "INSERT INTO crm_enrichment_log (lead_id, source, status, fields_found, detail) VALUES (?, ?, 'failed', 0, ?)",
                (lead_id, provider_name, str(e)[:500]),
            )

    # Update lead in DB
    if found_fields:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%f")
        setters = ["updated_at = ?"]
        params = [now]
        field_map = {
            "business_name": "business_name",
            "phone": "phone",
            "email": "email",
            "website": "website",
            "social_links": "social_links",
            "bbb_rating": "bbb_rating",
            "year_founded": "year_founded",
            "meta_description": "notes",
        }
        for src_key, db_col in field_map.items():
            if src_key in found_fields:
                setters.append(f"{db_col} = ?")
                val = found_fields[src_key]
                if isinstance(val, (dict, list)):
                    val = json.dumps(val)
                params.append(val)

        # Recalculate enrichment score
        lead.update(found_fields)
        enrich_score = get_enrichment_score(lead)
        setters.append("enrichment_score = ?")
        params.append(enrich_score)

        params.append(lead_id)
        backend.execute(
            f"UPDATE crm_leads SET {', '.join(setters)} WHERE id = ?",
            tuple(params),
        )
        backend.commit()

        # Log activity
        backend.execute(
            "INSERT INTO crm_activities (lead_id, act_type, summary, detail, actor) VALUES (?, 'enrichment', ?, ?, 'enrichment_engine')",
            (lead_id,
             f"Enriched: {total_new} new field(s) from {len([p for p in PRIORITY if p in globals()])} sources",
             json.dumps(found_fields, default=str)[:1000]),
        )
        backend.commit()

    return {
        "lead_id": lead_id,
        "new_fields": total_new,
        "enrichment_score": get_enrichment_score(
            {**lead, **found_fields}
        ),
        "fields_found": {k: str(v)[:100] for k, v in found_fields.items()},
    }


def batch_enrich(backend, limit: int = 50) -> dict:
    """Enrich leads with lowest enrichment scores first."""
    rows = backend.execute(
        "SELECT id FROM crm_leads WHERE enrichment_score < 50 ORDER BY enrichment_score ASC LIMIT ?",
        (limit,),
    ).fetchall()
    if not rows:
        return {"enriched": 0, "message": "No leads need enrichment"}
    results = []
    for r in rows:
        import asyncio
        try:
            result = asyncio.run(enrich_lead(backend, r["id"]))
            results.append(result)
        except Exception as e:
            logger.error("Batch enrich lead %s failed: %s", r["id"], e)
    return {"enriched": len(results), "results": results}


def get_enrichment_stats(backend) -> dict:
    """Return enrichment coverage stats."""
    total = backend.execute("SELECT COUNT(*) AS cnt FROM crm_leads").fetchone()["cnt"]
    enriched_gt_50 = backend.execute(
        "SELECT COUNT(*) AS cnt FROM crm_leads WHERE enrichment_score >= 50"
    ).fetchone()["cnt"]
    avg_score = backend.execute(
        "SELECT AVG(enrichment_score) AS avg FROM crm_leads"
    ).fetchone()["avg"]
    by_source = [
        dict(r) for r in backend.execute(
            "SELECT source, COUNT(*) AS cnt, SUM(fields_found) AS total_fields "
            "FROM crm_enrichment_log GROUP BY source ORDER BY cnt DESC"
        ).fetchall()
    ]
    return {
        "total_leads": total,
        "enriched_above_50": enriched_gt_50,
        "enrichment_pct": round(enriched_gt_50 / total * 100, 1) if total else 0,
        "avg_enrichment_score": round(avg_score, 1) if avg_score else 0,
        "by_source": by_source,
    }


def enrich_prospects(backend, limit: int = 200, only_missing_email: bool = True) -> dict:
    """Run the enrichment waterfall over si_buyer_outreach (real prospects).

    The 29k prospects in si_buyer_outreach are the actual scraper output.
    enrich_lead/batch_enrich only touch crm_leads (a sliver). This fills
    emails/phones there so the outreach mailer has real addresses to send to.

    Returns {processed, enriched, failed}.
    """
    q = "SELECT rowid, * FROM si_buyer_outreach"
    if only_missing_email:
        q += " WHERE (email IS NULL OR email = '' OR email LIKE '%@example%' OR email LIKE '%invalid%')"
    q += f" ORDER BY rowid ASC LIMIT {int(limit)}"
    rows = backend.execute(q).fetchall()
    processed = enriched = 0
    for row in rows:
        lead = dict(row)
        rid = lead.get("rowid") or lead.get("id")
        if not rid:
            continue
        # normalise url -> website so providers (_safe_domain) can use it
        url = lead.get("url", "") or ""
        if url and not url.startswith("skus:"):
            lead["website"] = url
        else:
            # derive a guess domain from business_name (website_scraper does this too)
            name = (lead.get("business_name") or "").lower().replace(" ", "").replace(".", "")
            if name:
                lead["website"] = f"https://{name}.com"
        processed += 1
        found = {}
        for prov in PRIORITY:
            fn = globals().get(prov)
            if not fn:
                continue
            try:
                res = fn(lead)
            except Exception:
                continue
            if not res:
                continue
            for k, v in res.items():
                if k not in found and (not lead.get(k)):
                    found[k] = v
            if found:
                lead.update(found)
        if not found:
            continue
        # guard: reject implausible guessed emails (junk name->domain guesses)
        em = found.get("email", "")
        if em:
            dom = em.split("@")[-1].lower()
            bad = ("&" in em or " " in em or len(dom) > 40
                   or dom.count(".") == 0 or dom.startswith("www.")
                   or any(ch in dom for ch in "&'\" \x00"))
            if bad:
                found.pop("email", None)
        setters = []
        params = []
        fmap = {"email": "email", "phone": "phone", "website": "url",
                "business_name": "business_name", "city": "metro", "state": "metro"}
        for src, col in fmap.items():
            if src in found:
                setters.append(f"{col} = ?")
                params.append(found[src])
        if setters:
            params.append(rid)
            backend.execute(
                f"UPDATE si_buyer_outreach SET {', '.join(setters)} WHERE rowid = ?",
                tuple(params),
            )
            backend.commit()
            enriched += 1
    return {"processed": processed, "enriched": enriched, "failed": processed - enriched}
