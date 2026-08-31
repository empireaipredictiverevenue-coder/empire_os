"""serp_discovery.py v2 — Serper-powered lead discovery → Omega pipeline.

v2 upgrade (Empire OS integrated):
  - discover(niche, metro, limit): multi-intent SERP sweep (hiring/expansion/
    new-location signals), dedupes vs crm_leads, returns stats dict.
  - discover_and_score(): discovery + Omega scoring (omega_scoring.score_lead)
    so leads land lane-ready with omega_score set (sellable in lead packs).
  - Runs entirely off hub /v1/web/search (serper backend) — no direct key use,
    no scraping bans, Google coverage.
"""
from __future__ import annotations
import json
import os
import sqlite3
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HUB = os.environ.get("HUB_URL", "http://127.0.0.1:8081")
DB = "/root/empire_os/empire_os.db"

NICHE_KW = {
    "roofing": "roofing contractor", "hvac": "hvac contractor",
    "plumbing": "plumbing contractor", "electrical": "electrical contractor",
    "solar": "solar installer", "landscaping": "landscaping company",
    "concrete": "concrete contractor", "fencing": "fence company",
    "pest_control": "pest control company", "painting": "painting contractor",
    "auto_repair": "auto repair shop", "dental": "dental clinic",
    "med_spa": "med spa", "law_firm": "law firm",
    "mass_tort": "mass tort law firm", "legal_services": "legal services",
    "real_estate": "real estate agent", "general_contractor": "general contractor",
    "construction": "construction company", "residential_roofing": "residential roofing",
}
INTENT = ["hiring", "now hiring", "careers", "expansion", "opened new location"]

# Purpose modes — the Serper product now serves ANY purpose, not just lead-gen
PURPOSES = {
    "lead_gen": '"{kw}" {metro} {intent}',
    "expired_domains": "expired domain {kw} authority backlinks",
    "trigger_words": "{kw} buy intent keyword long-tail",
    "ad_intel": "{kw} {metro} best services near me",
    "competitor": "{kw} {metro} competitors reviews",
}


def _serp_for_purpose(purpose: str, niche: str, metro: str = "", limit: int = 10) -> list[dict]:
    """Generic SERP call for any purpose mode. Returns raw result rows."""
    kw = NICHE_KW.get(niche, niche)
    tmpl = PURPOSES.get(purpose, PURPOSES["lead_gen"])
    q = tmpl.format(kw=kw, metro=metro, intent="").strip()
    return _search(q, num=limit)


def multi_niche_sweep(niches: list = None, metros: list = None, limit: int = 10) -> dict:
    """Run a lead-gen SERP sweep across ALL given niches (or every niche in DB).

    Multi-niche conscious: one call fans out per niche+metro, dedupes, scores,
    returns per-niche added counts. Powers the predictive-cloud Layer 20 brain.
    """
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA busy_timeout=30000")
    if not niches:
        niches = [r[0] for r in c.execute(
            "SELECT DISTINCT niche FROM crm_leads WHERE niche IS NOT NULL").fetchall()]
    if not metros:
        metros = [r[0] for r in c.execute(
            "SELECT DISTINCT metro FROM crm_leads WHERE metro IS NOT NULL AND metro != '' LIMIT 5").fetchall()]
        if not metros:
            metros = [""]
    c.close()
    totals = {}
    for nic in niches:
        added = 0
        for metro in metros:
            try:
                stats = discover(nic, metro, limit=min(limit, 10))
                added += stats.get("added", 0)
            except Exception as e:
                print(f"[serp_discovery] sweep {nic}/{metro}: {e}")
        totals[nic] = added
    return {"swept_niches": len(niches), "swept_metros": len(metros), "added_by_niche": totals,
            "total_added": sum(totals.values())}


def _search(q: str, num: int = 10) -> list[dict]:
    url = f"{HUB}/v1/web/search?q={urllib.parse.quote(q)}&num={num}&backend=serper"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EmpireLeadOS/2.0"})
        raw = urllib.request.urlopen(req, timeout=12).read()
        return json.loads(raw).get("results", [])
    except Exception as e:
        print(f"[serp_discovery] search err: {e}")
        return []


def discover(niche: str, metro: str, limit: int = 20) -> dict:
    """Multi-intent SERP sweep. Returns {added, seen, domains}."""
    kw = NICHE_KW.get(niche, niche)
    metro = metro.strip()
    seen = {}
    for intent in ("", *INTENT):
        q = f'"{kw}" {metro} {intent}'.strip()
        for r in _search(q, num=min(limit, 10)):
            link = r.get("url") or r.get("link", "")
            if not link or "http" not in link:
                continue
            try:
                domain = link.split("/")[2].replace("www.", "")
            except IndexError:
                continue
            title = (r.get("title") or "")[:120]
            snippet = r.get("snippet") or ""
            if domain not in seen:
                seen[domain] = {
                    "business_name": title or domain,
                    "website": domain,
                    "snippet": snippet[:400],
                    "intent_signal": intent or "general",
                }
            elif intent and seen[domain]["intent_signal"] == "general":
                seen[domain]["intent_signal"] = intent

    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA busy_timeout=30000")
    added = 0
    for domain, info in seen.items():
        cur = c.execute(
            "INSERT OR IGNORE INTO crm_leads "
            "(business_name, website, niche, metro, source, status, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (info["business_name"], info["website"], niche, metro,
             "serp_discovery", "raw",
             datetime.now(timezone.utc).isoformat()),
        )
        if cur.rowcount:
            added += 1
    c.commit()
    c.close()
    return {"added": added, "seen": len(seen), "niche": niche, "metro": metro}


def discover_and_score(niche: str, metro: str, limit: int = 20) -> dict:
    """Discovery + Omega score the new leads (only unscored serp_discovery rows)."""
    stats = discover(niche, metro, limit)
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA busy_timeout=30000")
    c.row_factory = sqlite3.Row
    rows = c.execute(
        "SELECT lead_uid, business_name, website, niche, metro FROM crm_leads "
        "WHERE source='serp_discovery' AND niche=? AND metro=? "
        "AND (omega_score IS NULL OR omega_score=0) LIMIT ?",
        (niche, metro, max(stats["added"], 1) * 3),
    ).fetchall()
    scored = 0
    try:
        from empire_os.omega_scoring import score_lead
        for row in rows:
            try:
                res = score_lead({
                    "business_name": row["business_name"],
                    "website": row["website"],
                    "industry": row["niche"],
                    "city": row["metro"],
                    "location": row["metro"],
                })
                c.execute(
                    "UPDATE crm_leads SET omega_score=?, omega_tier=?, status='scored' "
                    "WHERE lead_uid=?",
                    (res.get("omega_score", 0), res.get("omega_tier", ""), row["lead_uid"]))
                scored += 1
            except Exception as e:
                print(f"[serp_discovery] score err uid={row['lead_uid']}: {e}")
    except ImportError:
        print("[serp_discovery] omega_scoring unavailable — leads stored unscored")
    c.commit()
    c.close()
    stats["scored"] = scored
    return stats


def enrich_pending(niche: str, metro: str, limit: int = 25) -> dict:
    """Enrichment pass over unscored-contact serp_discovery leads.

    Runs agents.empire_enricher.enrich_waterfall (email_pattern, linkedin_guess,
    website_scraper via SiteCrawler, whois) — all free, zero API keys.
    Writes email/phone/socials back to crm_leads. Returns {enriched, with_email}.
    """
    from empire_os.agents.empire_enricher import enrich_waterfall
    c = sqlite3.connect(DB, timeout=30)
    c.execute("PRAGMA busy_timeout=30000")
    c.row_factory = sqlite3.Row
    rows = c.execute(
        "SELECT lead_uid, business_name, website, niche, metro FROM crm_leads "
        "WHERE source='serp_discovery' AND (?='' OR niche=?) AND (?='' OR metro=?) "
        "AND (email IS NULL OR email='') "
        "AND website NOT LIKE '%facebook.com' AND website NOT LIKE '%google.com' "
        "AND website NOT LIKE '%yelp.com' AND website NOT LIKE '%angi.com' "
        "AND website NOT LIKE '%thumbtack.com' AND website NOT LIKE '%yellowpages.com' "
        "AND website NOT LIKE '%bbb.org' AND website NOT LIKE '%linkedin.com' "
        "AND website NOT LIKE '%indeed.com' AND website NOT LIKE '%ziprecruiter.com' "
        "AND website NOT LIKE '%monster.com' AND website NOT LIKE '%myworkdayjobs.com' "
        "AND website NOT LIKE '%procore.com' AND website NOT LIKE '%porch.com' "
        "AND website NOT LIKE '%homeadvisor.com' AND website NOT LIKE '%networx.com' "
        "LIMIT ?",
        (niche, niche, metro, metro, limit),
    ).fetchall()
    enriched = 0
    with_email = 0
    import re as _re
    for row in rows:
        try:
            res = enrich_waterfall({
                "company": row["business_name"],
                "website": row["website"] or "",
                "domain": (row["website"] or "").replace("www.", ""),
                "industry": row["niche"], "city": row["metro"],
            })
            email = (res.get("email") or "").strip()
            phone = (res.get("phone") or "").strip()
            linkedin = ((res.get("social_links") or {}).get("linkedin")
                        or (res.get("social_from_site") or {}).get("linkedin")
                        or "").split("?")[0]
            if not email and res.get("email_patterns"):
                email = res["email_patterns"][0]
            if phone and not _re.fullmatch(r"\+?1?[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}", phone):
                phone = ""
            if email or phone or linkedin:
                c.execute(
                    "UPDATE crm_leads SET email=COALESCE(NULLIF(?,''),email), "
                    "phone=COALESCE(NULLIF(?,''),phone), enriched=1 "
                    "WHERE lead_uid=?",
                    (email, phone, row["lead_uid"]))
                enriched += 1
                if email:
                    with_email += 1
        except Exception as e:
            print(f"[serp_discovery] enrich err uid={row['lead_uid']}: {e}")
    c.commit()
    c.close()
    return {"enriched": enriched, "with_email": with_email, "checked": len(rows)}


if __name__ == "__main__":
    import sys
    niche = sys.argv[1] if len(sys.argv) > 1 else "roofing"
    metro = sys.argv[2] if len(sys.argv) > 2 else "Nashville"
    print(discover_and_score(niche, metro))
    print(enrich_pending(niche, metro))
