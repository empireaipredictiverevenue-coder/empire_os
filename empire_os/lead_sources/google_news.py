"""
Empire OS v3 — Google News RSS lead source (REAL, no key)
=========================================================
Multi-niche business-intent leads from Google News RSS.
Free, no API key, server-rendered XML. Keyword-driven per niche.
Companies mentioned in trade/news articles = warm B2B leads.

VERIFY-GATE: probe() hits one RSS query, expects >=1 <item>.
"""
import xml.etree.ElementTree as ET
import datetime, time, re
from empire_os.lead_sources.models import LeadCandidate, SourceInfo

NICHE_QUERIES = {
    "roofing":      "roofing company OR roofing contractor",
    "hvac":         "HVAC contractor OR heating cooling company",
    "plumbing":     "plumbing company OR plumber",
    "solar":        "solar installer OR solar company",
    "construction": "construction company OR general contractor",
    "landscaping":  "landscaping company OR lawn care",
    "electrician":  "electrician company OR electrical contractor",
    "cleaning":     "cleaning company OR janitorial services",
}

RSS = "https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"

def _fetch(q, timeout=25):
    import requests
    ua = {"User-Agent": "Mozilla/5.0 (EmpireOS-Crawler/1.0)"}
    r = requests.get(RSS.format(q=requests.utils.quote(q)), headers=ua, timeout=timeout)
    r.raise_for_status()
    return ET.fromstring(r.text)

def _niche_from_query(q):
    for k in NICHE_QUERIES:
        if k in q.lower():
            return k
    return "business"

def run(metro=None, limit=200):
    out = []
    for niche, q in NICHE_QUERIES.items():
        try:
            root = _fetch(q)
        except Exception:
            continue
        for it in root.findall(".//item")[:limit // len(NICHE_QUERIES) + 2]:
            title = (it.findtext("title") or "").strip()
            pub = it.findtext("pubDate") or ""
            src = it.findtext("{http://news.google.com}source" if False else "source") or ""
            link = it.findtext("link") or ""
            if not title:
                continue
            out.append(LeadCandidate(
                name=title[:120],
                niche=niche,
                metro=metro or "",
                details=f"News mention: {title} (src={src}, {pub})",
                source="google_news",
                lead_score=42,
                url=link,
            ))
        time.sleep(1)
    return out

def _probe():
    from empire_os.lead_sources.models import http_probe
    # reuse http_probe against the RSS endpoint (expects rows via item count)
    try:
        root = _fetch("roofing company")
        return len(root.findall(".//item")) >= 1
    except Exception:
        return False

def register_source(reg):
    reg(SourceInfo(
        name="google_news",
        tier="real",
        requires=[],
        description="Google News RSS — multi-niche business-intent leads, free, no key",
        run_fn=run,
        probe=_probe,
    ))
