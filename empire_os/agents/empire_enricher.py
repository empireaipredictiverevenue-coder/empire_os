"""
Empire OS — Ultimate Prospect Intelligence Engine
=================================================
Combines:
- Enrichment waterfall (multi-source, free + paid)
- Deep Research Agent (AGI + synthetic) for market signals
- Cortex Intelligence (predictive revenue, AI analysis)
- Outreach Runner (value-first nurture sequences)
- All free/no-key sources first; paid only as fallbacks

Usage:
    from empire_os.agents.empire_enricher import EmpireEnricher
    enricher = EmpireEnricher()
    result = enricher.deep_enrich(prospect_dict)  # full intel report
"""

from __future__ import annotations
import json
import os
import re
import time
import ssl
import socket
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import requests
import sqlite3

# Load .env
for _ln in (Path("/root/empire_os/.env").read_text(encoding="utf-8").splitlines()
            if Path("/root/empire_os/.env").exists() else ()):
    _ln = _ln.strip()
    if not _ln or _ln.startswith("#") or "=" not in _ln: continue
    _k, _, _v = _ln.partition("=")
    os.environ.setdefault(_k.strip(), _v.strip())

# ─── Config ──────────────────────────────────────────────────────────
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
HUB_URL = os.environ.get("HUB_URL", "http://127.0.0.1:8080")
DB_PATH = "/root/empire_os/empire_os.db"
FEEDBACK_DIR = Path("/root/feedback")
FEEDBACK_DIR.mkdir(parents=True, exist_ok=True)

# ─── Free Sources (no API key) ──────────────────────────────────────
FREE_SOURCES = [
    "website_scraper",      # biz website: email, phone, social, meta
    "ddg_search",           # DuckDuckGo HTML SERP (least blocking)
    "bing_search",          # Bing HTML SERP
    "google_search",        # Google HTML SERP (more blocking)
    "whois_lookup",         # RDAP domain data
    "bbb_lookup",           # BBB profile
    "email_pattern",        # guess info@/sales@/contact@
    "linkedin_guess",       # guess LinkedIn from name+domain
    "social_footprint",     # find FB/Twitter/IG/YT from site
    "tech_stack",           # detect CMS, analytics, ads pixels
    "permit_signals",       # check permits_nyc/permits_chi for contractor leads
    "reviews_mine",         # Google/Yelp/Angi review count + sentiment
    "news_signals",         # local news mentions (expansion, acquisition)
    "hiring_signals",       # job postings = growth intent
    "ad_intelligence",      # check FB Ad Library, Google Ads transparency
]

# ─── Paid Fallbacks (stubs) ─────────────────────────────────────────
PAID_SOURCES = [
    "hunter",               # Hunter.io (HUNTER_API_KEY, 25/mo free)
    "clearbit",             # Clearbit Enrichment
    "apollo",               # Apollo.io
    "people_data_labs",     # PDL
    "google_places",        # Google Places API
    "serper",               # Serper.dev (SERP API)
    "proxycurl",            # Proxycurl LinkedIn API
]

# ─── HTTP Helper ────────────────────────────────────────────────────
_http = requests.Session()
_http.trust_env = False  # bypass proxy

def _get(url: str, timeout: int = 10, **kwargs) -> Optional[str]:
    try:
        r = _http.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, **kwargs)
        r.raise_for_status()
        return r.text
    except Exception:
        return None

def _post(url: str, json: dict, timeout: int = 10) -> Optional[dict]:
    try:
        r = _http.post(url, json=json, headers={"User-Agent": USER_AGENT, "Content-Type": "application/json"}, timeout=timeout)
        if r.status_code < 300:
            return r.json()
    except Exception:
        pass
    return None

def _safe_domain(website: str) -> str:
    if not website: return ""
    w = website.strip().lower()
    if not w.startswith("http"): w = "https://" + w
    try:
        return urllib.parse.urlparse(w).netloc
    except Exception:
        return website

# ─── Core Enrichment Providers ──────────────────────────────────────

def website_scraper(lead: dict) -> dict:
    """Scrape business website for contact, social, meta, tech stack."""
    out = {}
    domain = _safe_domain(lead.get("website", "") or (lead.get("business_name", "").lower().replace(" ", "").replace(".", "") + ".com"))
    if not domain: return out
    
    html = _get(f"https://{domain}")
    if not html: return out
    
    # Title & meta
    m = re.search(r'<title>(.*?)</title>', html, re.I | re.S)
    if m: out["site_title"] = re.sub(r"<.*?>", "", m.group(1)).strip()[:120]
    
    # Emails
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
    biz_emails = [e for e in emails if not any(x in e for x in ["@", "noreply", "no-reply", "donotreply", "example", "test", "domain", "localhost", "sentry", "wix", "squarespace", "wordpress", "shopify"])]
    if biz_emails:
        # prefer info@, contact@, sales@, hello@, team@
        for pref in ["info", "contact", "sales", "hello", "team", "support", "office", "admin"]:
            for e in biz_emails:
                if e.lower().startswith(pref + "@"):
                    out["email"] = e
                    break
            if "email" in out: break
        if "email" not in out:
            out["email"] = biz_emails[0]
    
    # Phones
    phones = re.findall(r'(?:(?:\+?1[\s.-]?)?(?:\(?[2-9]\d{2}\)?[\s.-]?\d{3}[\s.-]?\d{4}))', html)
    if phones:
        out["phone"] = phones[0]
    
    # Social links
    social = {}
    patterns = {
        "facebook": r'facebook\.com/([^"\'>\s]+)',
        "linkedin": r'linkedin\.com/(?:company|in)/([^"\'>\s]+)',
        "instagram": r'instagram\.com/([^"\'>\s]+)',
        "twitter": r'twitter\.com/([^"\'>\s]+)',
        "youtube": r'youtube\.com/(?:c/|channel/|user/)?([^"\'>\s]+)',
        "tiktok": r'tiktok\.com/@([^"\'>\s]+)',
    }
    for k, pat in patterns.items():
        m = re.search(pat, html, re.I)
        if m: social[k] = m.group(1)
    if social: out["social_links"] = social
    
    # Tech stack hints
    tech = {}
    if "wp-content" in html or "wordpress" in html.lower(): tech["cms"] = "WordPress"
    if "shopify" in html.lower(): tech["ecommerce"] = "Shopify"
    if "wix" in html.lower(): tech["builder"] = "Wix"
    if "squarespace" in html.lower(): tech["builder"] = "Squarespace"
    if "gtag(" in html or "ga(" in html: tech["analytics"] = "Google Analytics"
    if "fbq(" in html: tech["ads"] = "Facebook Pixel"
    if "gtm" in html: tech["tag_manager"] = "GTM"
    if "hubspot" in html.lower(): tech["crm"] = "HubSpot"
    if "intercom" in html.lower(): tech["chat"] = "Intercom"
    if tech: out["tech_stack"] = tech
    
    return out

def ddg_search(lead: dict) -> dict:
    """DuckDuckGo HTML SERP scrape for email/contact."""
    out = {}
    name = lead.get("business_name", "") or ""
    domain = _safe_domain(lead.get("website", ""))
    q = f'{name} {domain} email contact'.strip()
    if not q: return out
    html = _get("https://html.duckduckgo.com/html/", params={"q": q})
    if not html: return out
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
    biz = [e for e in emails if not any(x in e for x in ["@", "noreply", "no-reply", "donotreply", "example", "test", "domain", "localhost", "sentry", "wix", "squarespace", "wordpress", "shopify", "duckduckgo", "bing", "google"])]
    if biz: out["email"] = biz[0]
    return out

def bing_search(lead: dict) -> dict:
    """Bing HTML SERP scrape."""
    out = {}
    name = lead.get("business_name", "") or ""
    domain = _safe_domain(lead.get("website", ""))
    q = f'{name} {domain} email contact'.strip()
    if not q: return out
    html = _get("https://www.bing.com/search", params={"q": q})
    if not html: return out
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
    biz = [e for e in emails if not any(x in e for x in ["@", "noreply", "no-reply", "donotreply", "example", "test", "domain", "localhost", "sentry", "wix", "squarespace", "wordpress", "shopify", "bing", "microsoft"])]
    if biz: out["email"] = biz[0]
    return out

def google_search(lead: dict) -> dict:
    """Google HTML SERP scrape (more blocking)."""
    out = {}
    name = lead.get("business_name", "") or ""
    domain = _safe_domain(lead.get("website", ""))
    q = f'{name} {domain} email contact'.strip()
    if not q: return out
    html = _get("https://www.google.com/search", params={"q": q, "num": 10})
    if not html: return out
    emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)
    biz = [e for e in emails if not any(x in e for x in ["@", "noreply", "no-reply", "donotreply", "example", "test", "domain", "localhost", "sentry", "wix", "squarespace", "wordpress", "shopify", "google", "gmail"])]
    if biz: out["email"] = biz[0]
    return out

def whois_lookup(lead: dict) -> dict:
    """RDAP WHOIS for domain registration info."""
    out = {}
    domain = _safe_domain(lead.get("website", ""))
    if not domain: return out
    html = _get(f"https://rdap.org/domain/{domain}")
    if not html: return out
    try:
        data = json.loads(html)
        if "entities" in data:
            for ent in data["entities"]:
                if ent.get("roles") and "registrant" in ent.get("roles", []):
                    vcard = ent.get("vcardArray", [[], []])[1]
                    for field in vcard:
                        if field[0] == "fn": out["registrant_name"] = field[3]
                        if field[0] == "email": out["registrant_email"] = field[3]
                        if field[0] == "tel": out["registrant_phone"] = field[3]
                        if field[0] == "adr":
                            addr = field[3]
                            out["registrant_address"] = f"{addr.get('street','')}, {addr.get('locality','')}, {addr.get('region','')} {addr.get('postalCode','')}".strip(", ")
        if "events" in data:
            for evt in data["events"]:
                if evt.get("eventAction") == "registration":
                    out["domain_created"] = evt.get("eventDate")
    except Exception:
        pass
    return out

def bbb_lookup(lead: dict) -> dict:
    """BBB profile lookup by name + state."""
    out = {}
    name = lead.get("business_name", "") or ""
    state = lead.get("state", "") or lead.get("metro", "")[:2].upper()
    if not name: return out
    q = urllib.parse.quote(f"{name} {state}")
    html = _get(f"https://www.bbb.org/search?find_text={q}")
    if not html: return out
    # Extract rating, years in business, accreditation
    m = re.search(r'rating[^>]*>([A-F][+-]?)<', html, re.I)
    if m: out["bbb_rating"] = m.group(1)
    m = re.search(r'years? in business[^>]*>(\d+)<', html, re.I)
    if m: out["bbb_years"] = int(m.group(1))
    m = re.search(r'accredited[^>]*>(yes|no)<', html, re.I)
    if m: out["bbb_accredited"] = m.group(1).lower() == "yes"
    return out

def email_pattern(lead: dict) -> dict:
    """Guess standard business emails from domain."""
    out = {}
    domain = _safe_domain(lead.get("website", ""))
    if not domain: return out
    name = (lead.get("business_name", "") or "").lower().replace(" ", "").replace(".", "").replace(",", "").replace("'", "")
    patterns = [
        f"info@{domain}", f"contact@{domain}", f"sales@{domain}",
        f"hello@{domain}", f"team@{domain}", f"support@{domain}",
        f"office@{domain}", f"admin@{domain}", f"inquiries@{domain}",
        f"billing@{domain}", f"accounts@{domain}",
    ]
    if name and len(name) > 3:
        patterns = [f"{name}@{domain}", f"{name[:8]}@{domain}"] + patterns
    out["email_patterns"] = patterns
    return out

def linkedin_guess(lead: dict) -> dict:
    """Guess LinkedIn company page from name."""
    out = {}
    name = lead.get("business_name", "") or ""
    if not name: return out
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    out["linkedin_guess"] = f"https://linkedin.com/company/{slug}"
    return out

def social_footprint(lead: dict) -> dict:
    """Find social profiles from website + name search."""
    out = {}
    domain = _safe_domain(lead.get("website", ""))
    name = lead.get("business_name", "") or ""
    if not domain and not name: return out
    
    # Check website for social links
    if domain:
        html = _get(f"https://{domain}")
        if html:
            social = {}
            patterns = {
                "facebook": r'facebook\.com/([^"\'>\s]+)',
                "linkedin": r'linkedin\.com/(?:company|in)/([^"\'>\s]+)',
                "instagram": r'instagram\.com/([^"\'>\s]+)',
                "twitter": r'twitter\.com/([^"\'>\s]+)',
                "youtube": r'youtube\.com/(?:c/|channel/|user/)?([^"\'>\s]+)',
                "tiktok": r'tiktok\.com/@([^"\'>\s]+)',
            }
            for k, pat in patterns.items():
                m = re.search(pat, html, re.I)
                if m: social[k] = m.group(1)
            if social: out["social_from_site"] = social
    
    return out

def tech_stack(lead: dict) -> dict:
    """Detect technology stack from website."""
    out = {}
    domain = _safe_domain(lead.get("website", ""))
    if not domain: return out
    html = _get(f"https://{domain}")
    if not html: return out
    tech = {}
    if "wp-content" in html or "wordpress" in html.lower(): tech["cms"] = "WordPress"
    if "shopify" in html.lower(): tech["ecommerce"] = "Shopify"
    if "wix" in html.lower(): tech["builder"] = "Wix"
    if "squarespace" in html.lower(): tech["builder"] = "Squarespace"
    if "webflow" in html.lower(): tech["builder"] = "Webflow"
    if "gtag(" in html or "ga(" in html: tech["analytics"] = "Google Analytics"
    if "fbq(" in html: tech["ads"] = "Facebook Pixel"
    if "gtm" in html: tech["tag_manager"] = "GTM"
    if "hubspot" in html.lower(): tech["crm"] = "HubSpot"
    if "intercom" in html.lower(): tech["chat"] = "Intercom"
    if "zendesk" in html.lower(): tech["support"] = "Zendesk"
    if "hotjar" in html.lower(): tech["heatmap"] = "Hotjar"
    if "clarity" in html.lower(): tech["heatmap"] = "Microsoft Clarity"
    if tech: out["tech_stack"] = tech
    return out

def permit_signals(lead: dict) -> dict:
    """Check permits_nyc/permits_chi for contractor activity signals."""
    out = {}
    niche = (lead.get("niche", "") or lead.get("sub_niche", "") or "").lower()
    metro = (lead.get("metro", "") or "").lower()
    if "roof" not in niche and "plumb" not in niche and "hvac" not in niche and "general" not in niche and "contract" not in niche:
        return out
    if "nyc" not in metro and "new york" not in metro and "chi" not in metro and "chicago" not in metro:
        return out
    
    try:
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        cur = con.cursor()
        if "nyc" in metro or "new york" in metro:
            rows = cur.execute("SELECT COUNT(*) as c, MAX(created_at) as latest FROM lane_leads WHERE source='permits_nyc' AND metro='NYC'").fetchone()
            if rows and rows["c"] > 0:
                out["nyc_permits_recent"] = rows["c"]
                out["nyc_permits_latest"] = rows["latest"]
        if "chi" in metro or "chicago" in metro:
            rows = cur.execute("SELECT COUNT(*) as c, MAX(created_at) as latest FROM lane_leads WHERE source='permits_chi' AND metro='CHI'").fetchone()
            if rows and rows["c"] > 0:
                out["chi_permits_recent"] = rows["c"]
                out["chi_permits_latest"] = rows["latest"]
        con.close()
    except Exception:
        pass
    return out

def reviews_mine(lead: dict) -> dict:
    """Estimate review volume/sentiment from public sources."""
    out = {}
    name = lead.get("business_name", "") or ""
    if not name: return out
    q = urllib.parse.quote(f'"{name}" reviews')
    html = _get(f"https://html.duckduckgo.com/html/", params={"q": q})
    if not html: return out
    # Rough extraction of review counts
    m = re.search(r'(\d+(?:,\d+)*)\s*reviews?', html, re.I)
    if m: out["review_count_est"] = int(m.group(1).replace(",", ""))
    m = re.search(r'(\d\.\d)\s*(?:out of|/)\s*5', html, re.I)
    if m: out["review_rating_est"] = float(m.group(1))
    return out

def news_signals(lead: dict) -> dict:
    """Local news mentions for expansion/acquisition signals."""
    out = {}
    name = lead.get("business_name", "") or ""
    metro = lead.get("metro", "") or ""
    if not name: return out
    q = urllib.parse.quote(f'"{name}" {metro} news')
    html = _get(f"https://html.duckduckgo.com/html/", params={"q": q})
    if not html: return out
    signals = []
    for kw in ["expansion", "acquired", "merger", "funding", "investment", "new location", "hiring", "growth", "award", "partnership"]:
        if kw in html.lower():
            signals.append(kw)
    if signals: out["news_signals"] = signals
    return out

def hiring_signals(lead: dict) -> dict:
    """Job postings = growth intent."""
    out = {}
    name = lead.get("business_name", "") or ""
    if not name: return out
    q = urllib.parse.quote(f'"{name}" hiring jobs')
    html = _get(f"https://html.duckduckgo.com/html/", params={"q": q})
    if not html: return out
    count = len(re.findall(r'(hiring|job|career|position|opening)', html, re.I))
    if count > 3: out["hiring_signal_strength"] = min(count, 50)
    return out

def ad_intelligence(lead: dict) -> dict:
    """Check FB Ad Library / Google Ads transparency for active campaigns."""
    out = {}
    name = lead.get("business_name", "") or ""
    domain = _safe_domain(lead.get("website", ""))
    if not name and not domain: return out
    
    # FB Ad Library (public, no auth for basic search)
    q = urllib.parse.quote(name)
    html = _get(f"https://www.facebook.com/ads/library/?active_status=all&ad_type=all&q={q}")
    if html and "ads" in html.lower():
        out["fb_ads_active"] = True
        # Rough count
        m = re.search(r'(\d+(?:,\d+)*)\s*ads?', html, re.I)
        if m: out["fb_ads_count"] = int(m.group(1).replace(",", ""))
    
    # Google Ads Transparency
    if domain:
        html = _get(f"https://adstransparency.google.com/?region=US&domain={domain}")
        if html and "ads" in html.lower():
            out["google_ads_active"] = True
    
    return out

# ─── Waterfall Engine ───────────────────────────────────────────────

def enrich_waterfall(lead: dict, max_sources: int = None) -> dict:
    """Run enrichment waterfall. Returns all discovered fields.
    Optimized for speed: reduced timeouts, no polite delay, priority to fast sources."""
    # Fast sources only - prioritize those that don't make external HTTP calls
    FAST_SOURCES = [
        "email_pattern",      # instant - local regex
        "linkedin_guess",     # instant - local regex
        "website_scraper",    # 1 HTTP call
        "whois_lookup",       # 1 HTTP call
    ]
    
    results = {}
    sources_run = 0
    source_list = FAST_SOURCES + [s for s in FREE_SOURCES + PAID_SOURCES if s not in FAST_SOURCES]
    
    for src_name in source_list:
        if max_sources and sources_run >= max_sources:
            break
        fn = globals().get(src_name)
        if not fn:
            continue
        try:
            res = fn(lead)
            if res:
                # Waterfall: only add fields not already found
                for k, v in res.items():
                    if k not in results:
                        results[k] = v
                sources_run += 1
        except Exception:
            pass
        # No polite delay - speed is critical
    return results

# ─── Deep Research (AGI + Synthetic) ────────────────────────────────

def deep_research_prospect(prospect: dict, llm_client=None) -> dict:
    """
    Run Deep Research Agent on a prospect.
    Returns strategic intelligence: market position, triggers, intent, habits, discovery opportunities.
    """
    niche = prospect.get("niche", "") or prospect.get("sub_niche", "") or "business"
    metro = prospect.get("metro", "") or "their area"
    name = prospect.get("business_name", "") or "this business"
    
    # Gather signals from free sources
    signals = {}
    for src in ["news_signals", "hiring_signals", "ad_intelligence", "reviews_mine", "tech_stack", "permit_signals"]:
        fn = globals().get(src)
        if fn:
            try:
                signals[src] = fn(prospect)
            except Exception:
                signals[src] = {}
    
    # AGI synthesis if LLM available
    agi_brief = ""
    if llm_client:
        try:
            prompt = f"""Research brief on {name} ({niche} in {metro}) for B2B lead-gen business.
Signals found:
{json.dumps(signals, indent=2)}

In 4 bullet points:
1. Trigger events (what changed recently that creates urgency)
2. Intent signals (what they're actively looking for)
3. Habit patterns (how they buy, what channels they trust)
4. Discovery opportunity (how we should reach them - NOT funnel language)

Under 100 words total. No fluff."""
            if hasattr(llm_client, "chat"):
                agi_brief = llm_client.chat(prompt)
            else:
                agi_brief = llm_client(prompt)
        except Exception:
            pass
    
    # Synthetic fallback (rule-based)
    if not agi_brief:
        bullets = []
        if signals.get("news_signals"): bullets.append(f"Trigger: {', '.join(signals['news_signals'])}")
        if signals.get("hiring_signals", {}).get("hiring_signal_strength", 0) > 5: bullets.append(f"Intent: Active hiring ({signals['hiring_signals']['hiring_signal_strength']} postings)")
        if signals.get("ad_intelligence", {}).get("fb_ads_active"): bullets.append("Intent: Running paid ads (FB/Google)")
        if signals.get("tech_stack", {}).get("crm"): bullets.append(f"Habit: Uses {signals['tech_stack']['crm']} CRM")
        if signals.get("reviews_mine", {}).get("review_count_est", 0) > 50: bullets.append(f"Discovery: High review volume ({signals['reviews_mine']['review_count_est']})")
        if not bullets: bullets.append("Signal: Low external visibility - cold outreach needed")
        agi_brief = "\n".join(f"- {b}" for b in bullets[:4])
    
    return {
        "signals": signals,
        "agi_brief": agi_brief,
        "researched_at": datetime.now(timezone.utc).isoformat(),
    }

# ─── Cortex Intelligence Integration ────────────────────────────────

def cortex_predict_revenue(prospect: dict) -> dict:
    """Use Cortex predictive revenue engine."""
    try:
        from empire_os.ai_intelligence import predict_revenue, process_lead
        content = f"{prospect.get('niche', '')} {prospect.get('sub_niche', '')} {prospect.get('metro', '')} score:{prospect.get('score', 0)}"
        result = process_lead(
            domain=prospect.get("niche", "unknown"),
            metro=prospect.get("metro", "UNKNOWN"),
            content=content,
            buyers=[],
            market_context={},
        )
        return {
            "predicted_revenue": result.get("revenue_prediction", {}).get("expected_revenue", 0),
            "p_close": result.get("revenue_prediction", {}).get("p_close", 0),
            "tier": result.get("omega_tier", {}).get("tier", "D"),
            "strategy": result.get("revenue_prediction", {}).get("recommended_strategy", "ignore"),
            "priority_score": result.get("revenue_prediction", {}).get("priority_score", 0),
        }
    except Exception:
        return {}

# ─── Outreach Integration ───────────────────────────────────────────

def draft_nurture_email(prospect: dict, intelligence: dict, step: int = 0) -> tuple[str, str]:
    """Draft value-first audit email using all intelligence - BRANDED TEMPLATE."""
    # _render_branded_email is defined in this same module
    pass
    
    name = prospect.get("business_name", "there")
    raw_niche = prospect.get("niche", "your specialty") or "your specialty"
    niche = raw_niche.replace("_", " ") if raw_niche != "b2b" else "your business"
    metro = prospect.get("metro", "your area") or "your area"
    
    # Extract insights
    agi = intelligence.get("agi_brief", "")
    signals = intelligence.get("signals", {})
    cortex = intelligence.get("cortex", {})
    
    # Audit-specific links
    audit_portal = prospect.get("audit_portal_url", f"https://empire-ai.co.uk/audit/{prospect.get('prospect_id', '')}")
    trial_url = "https://empire-ai.co.uk/audit/trial"
    
    if step == 0:
        subject = f"Your {niche.title()} Efficiency Audit — Confidential"
        body_text = (
            f"Hi {name},\n\n"
            f"Quick one - I've analyzed {prospect.get('business_name', 'your company')}'s {niche} operations in {metro}.\n\n"
            f"Found significant revenue leak from inefficient lead handling and missed opportunities.\n\n"
            f"Your personalized audit is ready: {audit_portal}\n\n"
            f"It shows:\n"
            f"  • Daily revenue leak estimate\n"
            f"  • Fleet/crew utilization gaps\n"
            f"  • Competitor comparison\n"
            f"  • 90-day recovery roadmap\n\n"
            f"Ready to fix these issues? Start a $10 trial — we'll implement the top fixes and monitor weekly.\n"
            f"Get Started: {trial_url}\n\n"
            f"Done-for-you implementation · Weekly monitoring · USDT (BSC) accepted\n\n- Empire OS"
        )
    elif step == 1:
        insight = agi.split("\n")[0] if agi else f"We track {niche} demand across {metro} daily."
        subject = f"{niche.title()} in {metro}: Your Revenue Leak Analysis"
        body_text = (
            f"Hi {name},\n\n"
            f"Following up with your audit insight, no ask.\n\n"
            f"One pattern we're seeing:\n  {insight}\n\n"
            f"Your full audit with recovery roadmap: {audit_portal}\n\n"
            f"Start a $10 trial to fix the top issues: {trial_url}\n\n"
            f"Done-for-you implementation · Weekly monitoring · USDT (BSC) accepted\n\n- Empire OS"
        )
    else:
        subject = f"Your {niche} Audit — Still Available for 48 Hours"
        body_text = (
            f"Hi {name},\n\n"
            f"Last one - your {niche} efficiency audit for {metro} is still available.\n\n"
            f"View it here: {audit_portal}\n\n"
            f"Start $10 trial: {trial_url}\n\n"
            f"If the timing's off, just reply 'later' and I'll close your file. No hard feelings.\n\n- Empire OS"
        )
    
    # Render with branded template
    html_body = _render_branded_email(subject, body_text, prospect, intelligence)
    return subject, html_body


def _render_branded_email(subject: str, body_text: str, prospect: dict, intelligence: dict) -> str:
    """Render email with Empire OS branded HTML template."""
    # Convert plain text to HTML paragraphs
    paragraphs = [p.strip() for p in body_text.split('\n\n') if p.strip()]
    html_paragraphs = ''.join(f'<p style="margin: 0 0 16px 0; line-height: 1.6;">{p.replace(chr(10), "<br>")}</p>' for p in paragraphs)
    
    # Extract key metrics for the sidebar
    niche = (prospect.get("niche", "") or "").replace("_", " ").title()
    metro = prospect.get("metro", "") or ""
    cortex = intelligence.get("cortex", {})
    predicted_rev = cortex.get("predicted_revenue", 0)
    tier = cortex.get("tier", "—")
    
    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #0b0e14; color: #e6e6e6; line-height: 1.6;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; margin: 0 auto; padding: 24px 16px;">
        <!-- Header -->
        <tr>
            <td style="padding: 0 0 24px 0; border-bottom: 1px solid #232a36;">
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                    <tr>
                        <td style="width: 40px; height: 40px; background: linear-gradient(135deg, #7c5cff 0%, #22d3ee 100%); border-radius: 8px; text-align: center; vertical-align: middle;">
                            <span style="font-size: 18px; font-weight: 700; color: #0b0e14;">E</span>
                        </td>
                        <td style="padding-left: 12px; vertical-align: middle;">
                            <span style="font-size: 16px; font-weight: 600; background: linear-gradient(90deg, #7c5cff, #22d3ee); -webkit-background-clip: text; background-clip: text; color: transparent;">Empire OS</span>
                            <div style="font-size: 11px; color: #7c5cff; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px;">Lead Intelligence</div>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
        
        <!-- Main Content -->
        <tr>
            <td style="padding: 24px 0;">
                {html_paragraphs}
                
                <!-- CTA Button -->
                <table role="presentation" cellpadding="0" cellspacing="0" style="margin: 24px 0;">
                    <tr>
                        <td style="background: linear-gradient(135deg, #7c5cff 0%, #22d3ee 100%); border-radius: 8px;">
                            <a href="https://empire-ai.co.uk/buy-leads" style="display: inline-block; padding: 14px 28px; color: #0b0e14; text-decoration: none; font-weight: 600; font-size: 14px; border-radius: 8px;">Claim Your Lane</a>
                        </td>
                    </tr>
                </table>
                
                <p style="margin: 24px 0 0 0; font-size: 12px; color: #9aa0aa;">
                    Vault: <code style="background: #151a23; padding: 2px 6px; border-radius: 4px; font-size: 11px;">egJ1t9NZkDs8FvMbfnQTqXzC4KNuhAc9XSfpG9y9AZM</code>
                </p>
            </td>
        </tr>
        
        <!-- Intelligence Sidebar -->
        <tr>
            <td style="padding: 20px; background: #151a23; border: 1px solid #232a36; border-radius: 12px; margin-top: 24px;">
                <h3 style="margin: 0 0 16px 0; font-size: 13px; color: #22d3ee; text-transform: uppercase; letter-spacing: 0.5px;">Intelligence Snapshot</h3>
                <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size: 12px;">
                    <tr>
                        <td style="color: #9aa0aa; padding: 4px 0; width: 50%;">Vertical</td>
                        <td style="color: #e6e6e6; padding: 4px 0; font-weight: 500;">{niche}</td>
                    </tr>
                    <tr>
                        <td style="color: #9aa0aa; padding: 4px 0;">Metro</td>
                        <td style="color: #e6e6e6; font-weight: 500;">{metro or '—'}</td>
                    </tr>
                    <tr>
                        <td style="color: #9aa0aa; padding: 4px 0;">Cortex Tier</td>
                        <td style="color: #7c5cff; font-weight: 600;">{tier}</td>
                    </tr>
                    <tr>
                        <td style="color: #9aa0aa; padding: 4px 0;">Predicted Rev/Lead</td>
                        <td style="color: #22d3ee; font-weight: 600;">${predicted_rev:.0f}</td>
                    </tr>
                </table>
            </td>
        </tr>
        
        <!-- Footer -->
        <tr>
            <td style="padding: 24px 0 0 0; border-top: 1px solid #232a36;">
                <p style="margin: 0; font-size: 11px; color: #5c6370; text-align: center;">
                    Empire OS · Lead Intelligence Platform · <a href="https://empire-ai.co.uk" style="color: #7c5cff;">empire-ai.co.uk</a><br>
                    You received this because you operate in {niche.lower()} in {metro.lower()}. 
                    <a href="https://empire-ai.co.uk/unsubscribe?email={{email}}" style="color: #5c6370;">Unsubscribe</a>
                </p>
            </td>
        </tr>
    </table>
</body>
</html>'''
# ─── Main Class ─────────────────────────────────────────────────────

class EmpireEnricher:
    """
    Ultimate prospect intelligence engine.
    One call: deep_enrich(prospect) -> complete intelligence report
    """
    
    def __init__(self, llm_client=None):
        self.llm = llm_client
        self.cache = {}  # simple in-memory cache
    
    def deep_enrich(self, prospect: dict, use_cache: bool = True, max_sources: int = 5) -> dict:
        """
        Full enrichment + intelligence pipeline.
        Returns prospect with all discovered fields + intelligence.
        max_sources limits the waterfall to the fastest sources (default 5).
        """
        pid = prospect.get("prospect_id") or prospect.get("business_name", "")[:32]
        
        if use_cache and pid in self.cache:
            return self.cache[pid]
        
        # Start with prospect copy
        enriched = dict(prospect)
        
        # 1. Enrichment waterfall (contact, social, tech, signals)
        waterfall = enrich_waterfall(enriched, max_sources=max_sources)
        enriched.update(waterfall)
        
        # 2. Deep Research (AGI + synthetic)
        research = deep_research_prospect(enriched, self.llm)
        enriched["deep_research"] = research
        
        # 3. Cortex Predictive Revenue
        cortex = cortex_predict_revenue(enriched)
        enriched["cortex"] = cortex
        
        # 4. Scoring
        enriched["enrichment_score"] = self._calc_score(enriched)
        enriched["enriched_at"] = datetime.now(timezone.utc).isoformat()
        
        # 5. Draft nurture sequence (ready to send)
        enriched["nurture_sequence"] = [
            draft_nurture_email(enriched, {"agi_brief": research["agi_brief"], "signals": research["signals"], "cortex": cortex}, step=i)
            for i in range(3)
        ]
        
        if use_cache:
            self.cache[pid] = enriched
        
        return enriched
    
    def _calc_score(self, enriched: dict) -> float:
        """Calculate data completeness score 0-100."""
        score = 0.0
        fields = [
            ("email", 20), ("phone", 15), ("website", 10),
            ("social_links", 10), ("tech_stack", 5),
            ("registrant_email", 10), ("bbb_rating", 5),
            ("review_count_est", 5), ("news_signals", 5),
            ("hiring_signal_strength", 5), ("ad_intelligence", 5),
            ("deep_research", 10), ("cortex", 10),
        ]
        for field, weight in fields:
            if enriched.get(field) or (isinstance(enriched.get(field), dict) and enriched[field]):
                score += weight
        return min(score, 100.0)
    
    def batch_enrich(self, prospects: list[dict]) -> list[dict]:
        """Enrich multiple prospects."""
        return [self.deep_enrich(p) for p in prospects]
    
    def get_nurture_ready(self, prospect: dict, lightweight: bool = False) -> dict:
        """Get prospect with nurture emails ready to send.
        If lightweight=True, skip heavy website scraping/deep-research, use template emails."""
        if lightweight:
            # Fast path: minimal enrichment, template nurture emails (for outreach runner)
            enriched = dict(prospect)
            # Only run fast sources: email_pattern + linkedin_guess
            fast_sources = ["email_pattern", "linkedin_guess"]
            results = {}
            for src_name in fast_sources:
                fn = globals().get(src_name)
                if fn:
                    try:
                        res = fn(enriched)
                        if res:
                            for k, v in res.items():
                                if k not in results:
                                    results[k] = v
                    except Exception:
                        pass
            enriched.update(results)
            enriched["enrichment_score"] = self._calc_score(enriched)
            enriched["enriched_at"] = datetime.now(timezone.utc).isoformat()
            # Minimal intelligence for email drafting
            intelligence = {"agi_brief": "", "signals": {}, "cortex": {}}
            enriched["nurture_sequence"] = [
                draft_nurture_email(enriched, intelligence, step=i)
                for i in range(3)
            ]
        else:
            enriched = self.deep_enrich(prospect)
            intelligence = {"agi_brief": enriched["deep_research"]["agi_brief"],
                          "signals": enriched["deep_research"]["signals"],
                          "cortex": enriched["cortex"]}
        return {
            "prospect": enriched,
            "emails": [
                {"step": i, "subject": subj, "body": body}
                for i, (subj, body) in enumerate(enriched["nurture_sequence"])
            ],
        }

# ─── CLI / Test ─────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        # Test with a sample prospect
        test_prospect = {
            "prospect_id": "test_roofing_nyc",
            "business_name": "ABC Roofing & Construction",
            "niche": "roofing",
            "sub_niche": "residential_roofing",
            "metro": "NYC",
            "website": "abcroofingnyc.com",
        }
        enricher = EmpireEnricher()
        result = enricher.deep_enrich(test_prospect)
        print(json.dumps(result, indent=2, default=str))
    
    elif len(sys.argv) > 1 and sys.argv[1] == "batch":
        # Batch enrich from DB
        enricher = EmpireEnricher()
        con = sqlite3.connect(DB_PATH)
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT prospect_id, business_name, niche, metro, website FROM si_buyer_outreach WHERE email = '' OR email IS NULL LIMIT 10").fetchall()
        con.close()
        for r in rows:
            p = dict(r)
            result = enricher.deep_enrich(p)
            print(f"{p['business_name']}: score={result['enrichment_score']:.1f}, email={result.get('email', 'NONE')}")
    
    else:
        print("Usage:")
        print("  python empire_enricher.py test          # test with sample prospect")
        print("  python empire_enricher.py batch         # enrich 10 prospects from DB")