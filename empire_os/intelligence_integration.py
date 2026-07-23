#!/usr/bin/env python3
"""
Intelligence Integration Layer — Empire OS v3
=============================================
Single entrypoint that wires AGI/Intelligence systems into the lead pipeline:

1. CORTEX SCORER — niche/metro heat from revenue intelligence
2. SYNTHETIC INTELLIGENCE — lead quality, intent, fit analysis  
3. OMEGA OS — lead tiering (S/A/B/C/D) for buyer matching
4. AEO — auto-generate niche/metro landing pages for inbound
5. A2A — push qualified leads to buyer marketplace

Usage:
    from empire_os.intelligence_integration import enrich_lead, enrich_batch, auto_aeo, push_to_a2a
    
    enriched = enrich_lead(lead_candidate)
    # enriched now has: cortex_score, synthetic_analysis, omega_tier, buyer_match
    
    enrich_batch(leads)  # bulk
    auto_aeo()  # generates pages for top gaps
    push_to_a2a(enriched)  # if omega_tier >= B
"""

import json, os, time, sqlite3
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

DB = "/root/empire_os/empire_os.db"
CORTEX_CACHE = Path("/run/cortex_niche_scores.json")
OMEGA_CACHE = Path("/root/feedback/omega_scores.jsonl")
SYNTH_CACHE = Path("/root/feedback/synthetic_leads.jsonl")

# ──────────────────────────────────────────────────────────────────────
@dataclass
class EnrichedLead:
    # Original fields
    name: str
    email: str
    phone: str
    niche: str
    metro: str
    state: str
    details: str
    source: str
    lead_score: int
    url: str
    raw: dict
    
    # Intelligence enrichment
    cortex_score: int = 0           # 50-95 from Cortex niche heat
    cortex_tier: str = ""           # hot/warm/cold
    synthetic_intent: str = ""      # high/medium/low
    synthetic_fit: float = 0.0      # 0.0-1.0 niche fit
    synthetic_reasoning: str = ""   # why
    omega_tier: str = "D"           # S/A/B/C/D quality tier
    omega_confidence: float = 0.0   # 0.0-1.0
    aeo_priority: int = 0           # 1-10, should we build AEO page
    buyer_matches: List[dict] = None # A2A buyer matches
    enriched_at: str = ""
    
    def to_dict(self) -> dict:
        d = asdict(self)
        d["buyer_matches"] = self.buyer_matches or []
        return d


# ──────────────────────────────────────────────────────────────────────
# CORTEX — Niche/Metro Heat
# ──────────────────────────────────────────────────────────────────────
_cortex_ts = 0
_cortex_scores = {}

def _load_cortex():
    global _cortex_ts, _cortex_scores
    try:
        if CORTEX_CACHE.exists():
            data = json.loads(CORTEX_CACHE.read_text())
            _cortex_ts = data.get("ts", 0)
            _cortex_scores = data.get("scores", {})
    except Exception:
        _cortex_scores = {}

def get_cortex_score(niche: str, metro: str = "") -> tuple[int, str]:
    """Returns (score, tier) where tier in {hot, warm, cold}."""
    global _cortex_ts, _cortex_scores
    if time.time() - _cortex_ts > 60:
        _load_cortex()
    
    n = (niche or "").lower().strip()
    key = f"{metro.lower()}:{n}" if metro else n
    score = _cortex_scores.get(key, _cortex_scores.get(n, 55))
    
    if score >= 80: tier = "hot"
    elif score >= 65: tier = "warm"
    else: tier = "cold"
    return score, tier


# ──────────────────────────────────────────────────────────────────────
# SYNTHETIC INTELLIGENCE — Lead Quality Analysis
# ──────────────────────────────────────────────────────────────────────
def analyze_lead_synthetic(name: str, email: str, niche: str, metro: str, 
                           details: str, source: str) -> dict:
    """
    Uses local heuristics (no API key) to score:
    - intent: high/medium/low
    - fit: 0.0-1.0
    - reasoning: string
    """
    score = 0.5
    reasons = []
    
    # Email quality
    if email:
        local = email.split("@")[0].lower()
        if local in ("info","sales","contact","hello","admin","office","support"):
            score += 0.15; reasons.append("generic_role_email")
        elif any(c.isdigit() for c in local):
            score -= 0.1; reasons.append("numeric_local_part")
        else:
            score += 0.1; reasons.append("personal_email")
    
    # Phone presence
    if "@" in details or "phone" in details.lower() or "call" in details.lower():
        score += 0.1; reasons.append("phone_mentioned")
    
    # Source quality
    source_quality = {
        "county_permits": 0.3, "google_maps": 0.2, "yelp": 0.15,
        "bbb": 0.2, "state_registry": 0.25, "universal_scraper": 0.1,
        "search_api": 0.1, "reddit_intent": 0.2, "job_boards": 0.15,
    }
    score += source_quality.get(source.split(":")[0], 0.05)
    
    # Niche fit keywords
    niche_kw = {
        "roofing": ["roof","shingle","gutter","leak","storm"],
        "hvac": ["hvac","ac","furnace","cooling","heating","duct"],
        "plumbing": ["plumb","pipe","drain","water","leak","sewer"],
        "electrical": ["electric","wire","panel","outlet","circuit"],
        "solar": ["solar","panel","inverter","battery","pv"],
        "pest_control": ["pest","termite","rodent","exterminat"],
        "landscaping": ["lawn","tree","irrigation","sprinkler","yard"],
    }
    for kw in niche_kw.get(niche.lower(), []):
        if kw in details.lower():
            score += 0.05
            reasons.append(f"kw:{kw}")
    
    # Metro specificity
    if metro and metro in details:
        score += 0.05; reasons.append("metro_match")
    
    score = max(0.0, min(1.0, score))
    
    if score >= 0.7: intent = "high"
    elif score >= 0.45: intent = "medium"
    else: intent = "low"
    
    return {
        "intent": intent,
        "fit": round(score, 2),
        "reasoning": "; ".join(reasons) if reasons else "baseline",
    }


# ──────────────────────────────────────────────────────────────────────
# OMEGA OS — Lead Tiering (S/A/B/C/D)
# ──────────────────────────────────────────────────────────────────────
_omega_cache = {}
_omega_ts = 0

def _load_omega():
    global _omega_cache, _omega_ts
    try:
        if OMEGA_CACHE.exists():
            for line in OMEGA_CACHE.read_text().strip().splitlines():
                d = json.loads(line)
                key = f"{d.get('niche','').lower()}:{d.get('metro','').lower()}"
                _omega_cache[key] = d
            _omega_ts = time.time()
    except Exception:
        pass

def get_omega_tier(niche: str, metro: str, lead_score: int, 
                   cortex_score: int, synthetic_fit: float) -> tuple[str, float]:
    """Returns (tier, confidence) where tier in {S,A,B,C,D}."""
    global _omega_ts, _omega_cache
    if time.time() - _omega_ts > 300:
        _load_omega()
    
    n = (niche or "").lower().strip()
    m = (metro or "").lower().strip()
    key = f"{m}:{n}" if m else n
    
    # Base from lead_score
    base = lead_score
    
    # Cortex boost
    base += (cortex_score - 55) * 0.5
    
    # Synthetic fit boost
    base += synthetic_fit * 20
    
    # Omega historical tier bonus
    if key in _omega_cache:
        tier = _omega_cache[key].get("tier", "C")
        tier_bonus = {"S": 15, "A": 10, "B": 5, "C": 0, "D": -5}.get(tier, 0)
        base += tier_bonus
    
    # Determine final tier
    if base >= 90: tier, conf = "S", 0.95
    elif base >= 80: tier, conf = "A", 0.9
    elif base >= 70: tier, conf = "B", 0.85
    elif base >= 60: tier, conf = "C", 0.75
    else: tier, conf = "D", 0.65
    
    return tier, round(conf, 2)


# ──────────────────────────────────────────────────────────────────────
# AEO — Auto-generate niche/metro landing pages
# ──────────────────────────────────────────────────────────────────────
AEO_GAPS_FILE = Path("/root/feedback/aeo_gaps.json")
AEO_PUBLISHED = Path("/srv/aeo")

def get_aeo_priority(niche: str, metro: str, cortex_score: int, 
                     lead_count: int, omega_tier: str) -> int:
    """1-10 priority for AEO page generation."""
    priority = 0
    # Cortex heat
    priority += min(4, cortex_score // 20)
    # Lead volume
    priority += min(3, lead_count // 50)
    # Omega tier
    priority += {"S": 3, "A": 2, "B": 1, "C": 0, "D": 0}.get(omega_tier, 0)
    # Gap check
    if AEO_GAPS_FILE.exists():
        try:
            gaps = json.loads(AEO_GAPS_FILE.read_text())
            if f"{metro}:{niche}" in gaps.get("gaps", {}):
                priority += 2
        except Exception:
            pass
    return min(10, priority)


def auto_aeo(top_n: int = 10) -> List[dict]:
    """
    Generate AEO pages for top priority niche/metro combos.
    Returns list of generated pages.
    """
    from empire_os.aeo_generator import generate_aeo_page
    from empire_os.aeo_surface import deploy_spec
    
    # Load Cortex report for hot niches
    try:
        with open("/root/feedback/cortex_report.json") as f:
            report = json.load(f)
    except Exception:
        return []
    
    hot = report.get("market_gaps", {}).get("hot_gaps", [])
    demand = report.get("market_gaps", {}).get("top_demand_niches", [])
    
    combos = []
    for gap in hot:
        niche = gap.get("niche_metro", "").split(":")[0]
        metro = gap.get("niche_metro", "").split(":")[1] if ":" in gap.get("niche_metro","") else ""
        if niche and metro:
            combos.append((niche, metro))
    
    for d in demand[:20]:
        niche = d.get("niche", "")
        if niche and niche not in [c[0] for c in combos]:
            combos.append((niche, "NATIONAL"))
    
    generated = []
    for niche, metro in combos[:top_n]:
        try:
            spec = generate_aeo_page(niche, metro)
            url = deploy_spec(spec)
            generated.append({"niche": niche, "metro": metro, "url": url})
        except Exception as e:
            print(f"AEO gen failed {niche}/{metro}: {e}")
    
    return generated


# ──────────────────────────────────────────────────────────────────────
# A2A — Push qualified leads to buyer marketplace
# ──────────────────────────────────────────────────────────────────────
def find_buyer_matches(niche: str, metro: str, omega_tier: str, 
                       min_tier: str = "B") -> List[dict]:
    """Query A2A catalog for buyers wanting this niche/metro."""
    try:
        import urllib.request
        url = f"http://10.118.155.218:8081/v1/a2a/catalog?niche={niche}&metro={metro}"
        with urllib.request.urlopen(url, timeout=5) as r:
            catalog = json.loads(r.read())
        
        buyers = []
        tier_rank = {"S":5,"A":4,"B":3,"C":2,"D":1}
        min_rank = tier_rank.get(min_tier, 3)
        
        for product in catalog.get("products", {}).values():
            if product.get("niche") == niche and product.get("metro") == metro:
                p_tier = product.get("tier", "C")
                if tier_rank.get(p_tier, 0) >= min_rank:
                    buyers.append({
                        "buyer_id": product.get("seller"),
                        "product_id": product.get("id"),
                        "price_usdc": product.get("price_usdc"),
                        "tier": p_tier,
                        "capacity": product.get("capacity", 10),
                    })
        return buyers[:5]  # top 5 matches
    except Exception:
        return []


def push_to_a2a(enriched: EnrichedLead) -> bool:
    """If lead is tier >= B, create A2A listing for buyers."""
    if enriched.omega_tier not in ("S", "A", "B"):
        return False
    
    try:
        import urllib.request
        payload = {
            "lead_id": f"lead_{enriched.name}_{enriched.metro}_{enriched.niche}".replace(" ", "_"),
            "niche": enriched.niche,
            "metro": enriched.metro,
            "contact": {"name": enriched.name, "email": enriched.email, "phone": enriched.phone},
            "score": enriched.lead_score,
            "omega_tier": enriched.omega_tier,
            "source": enriched.source,
            "details": enriched.details,
            "matched_buyers": enriched.buyer_matches,
        }
        req = urllib.request.Request(
            "http://10.118.155.218:8081/v1/a2a/lead",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except Exception as e:
        print(f"A2A push failed: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────
# MAIN ENTRYPOINTS
# ──────────────────────────────────────────────────────────────────────
def enrich_lead(cand: Any, quick: bool = False) -> EnrichedLead:
    """Enrich a single LeadCandidate with all intelligence. quick=True skips HTTP calls (buyer_matches)."""
    niche = (cand.niche or "").strip()
    metro = (cand.metro or "").strip()

    # Cortex
    cortex_score, cortex_tier = get_cortex_score(niche, metro)

    # Synthetic Intelligence
    synth = analyze_lead_synthetic(
        cand.name, cand.email, niche, metro, cand.details, cand.source
    )

    # Boost lead_score with cortex
    boosted_score = max(cand.lead_score, cortex_score)

    # Omega
    omega_tier, omega_conf = get_omega_tier(
        niche, metro, boosted_score, cortex_score, synth["fit"]
    )

    # AEO priority
    lead_count = 0
    if not quick:
        try:
            with sqlite3.connect(DB, timeout=10) as c:
                lead_count = c.execute(
                    "SELECT COUNT(*) FROM si_buyer_outreach WHERE niche=? AND metro=?",
                    (niche, metro)
                ).fetchone()[0]
        except Exception:
            pass

    aeo_prio = get_aeo_priority(niche, metro, cortex_score, lead_count, omega_tier)

    # A2A buyer matches — only when not quick (HTTP call)
    buyer_matches = [] if quick else find_buyer_matches(niche, metro, omega_tier)
    if quick and omega_tier in ("S", "A", "B"):
        # lightweight: just count from local DB, no HTTP
        try:
            with sqlite3.connect(DB, timeout=10) as c:
                cnt = c.execute(
                    "SELECT COUNT(*) FROM si_buyer_outreach WHERE niche=? AND metro=? AND payout_per_lead > 0",
                    (niche, metro)
                ).fetchone()[0]
                buyer_matches = [{"buyer_count": cnt, "quick": True}]
        except Exception:
            pass
    
    return EnrichedLead(
        name=cand.name,
        email=cand.email,
        phone=cand.phone,
        niche=niche,
        metro=metro,
        state=cand.state or "",
        details=cand.details,
        source=cand.source,
        lead_score=boosted_score,
        url=cand.url or "",
        raw=cand.raw or {},
        cortex_score=cortex_score,
        cortex_tier=cortex_tier,
        synthetic_intent=synth["intent"],
        synthetic_fit=synth["fit"],
        synthetic_reasoning=synth["reasoning"],
        omega_tier=omega_tier,
        omega_confidence=omega_conf,
        aeo_priority=aeo_prio,
        buyer_matches=buyer_matches,
        enriched_at=datetime.now(timezone.utc).isoformat(),
    )


def enrich_batch(candidates: List[Any]) -> List[EnrichedLead]:
    """Bulk enrich with caching."""
    return [enrich_lead(c) for c in candidates]


def persist_enriched(enriched: EnrichedLead) -> bool:
    """Upsert enriched lead back to si_buyer_outreach."""
    try:
        with sqlite3.connect(DB) as c:
            c.execute("""
                UPDATE si_buyer_outreach SET
                    lead_score = ?,
                    cortex_score = ?,
                    cortex_tier = ?,
                    synthetic_intent = ?,
                    synthetic_fit = ?,
                    synthetic_reasoning = ?,
                    omega_tier = ?,
                    omega_confidence = ?,
                    aeo_priority = ?,
                    buyer_matches = ?,
                    enriched_at = ?
                WHERE prospect_id = ?
            """, (
                enriched.lead_score,
                enriched.cortex_score,
                enriched.cortex_tier,
                enriched.synthetic_intent,
                enriched.synthetic_fit,
                enriched.synthetic_reasoning,
                enriched.omega_tier,
                enriched.omega_confidence,
                enriched.aeo_priority,
                json.dumps(enriched.buyer_matches or []),
                enriched.enriched_at,
                f"lead_{enriched.name}_{enriched.metro}_{enriched.niche}".replace(" ", "_"),
            ))
            return c.rowcount > 0
    except Exception as e:
        print(f"Persist failed: {e}")
        return False


# ──────────────────────────────────────────────────────────────────────
# DAEMON: Continuous enrichment loop (lane_leads target)
# ──────────────────────────────────────────────────────────────────────
def enrichment_cycle(batch_size: int = 500) -> dict:
    """
    One enrichment cycle against lane_leads.
    Returns summary dict {considered, enriched, skipped, errors}.
    Skips leads that already have predicted_value_usd set (don't double-work).
    """
    summary = {"considered": 0, "enriched": 0, "skipped": 0, "errors": 0, "started": time.time()}
    try:
        with sqlite3.connect(DB, timeout=60) as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA busy_timeout=60000")
            # target lane_leads where omega_tier is tier-B+ AND not yet value-enriched
            rows = c.execute("""
                SELECT id, niche, metro, omega_tier, omega_score, icp_fit_score,
                       street, city, state, zip
                FROM lane_leads
                WHERE omega_tier IN ('gold','silver','tier_a','tier_b','S','A','B','C')
                  AND (buyer_id IS NULL OR buyer_id='')
                  AND (predicted_value_usd IS NULL OR predicted_value_usd = 0)
                ORDER BY id DESC LIMIT ?
            """, (batch_size,)).fetchall()
            summary["considered"] = len(rows)

            for row in rows:
                lid, niche, metro, tier, score, icp_fit, street, city, state, zipc = row
                try:
                    # Build a fake candidate for analysis (lane_leads has no
                    # email/phone/name -- those live on si_buyer_outreach,
                    # but for enrichment we just need niche/metro/details)
                    details_parts = [niche or '', metro or '', street or '', city or '', state or '']
                    details = " ".join([p for p in details_parts if p])
                    cand = type("Cand", (), {
                        "name": f"lane_lead_{lid}",
                        "email": "",
                        "phone": "",
                        "niche": niche or "",
                        "metro": metro or "",
                        "state": state or "",
                        "details": details,
                        "source": "lane_leads",
                        "lead_score": score or 50,
                        "url": "",
                        "raw": {},
                    })()
                    enriched = enrich_lead(cand, quick=True)

                    # UPDATE lane_leads with intelligence layer results
                    c.execute("""
                        UPDATE lane_leads SET
                            cortex_score = COALESCE(NULLIF(?, 0), cortex_score),
                            aeo_priority = COALESCE(NULLIF(?, 0), aeo_priority)
                        WHERE id = ?
                    """, (
                        enriched.cortex_score,
                        enriched.aeo_priority,
                        lid,
                    ))
                    summary["enriched"] += 1
                except Exception as e:
                    summary["errors"] += 1
                    print(f"  enrich error on {lid}: {e}")
            c.commit()
    except Exception as e:
        print(f"[enrichment_cycle] error: {e}")
        summary["errors"] += 1
    summary["elapsed"] = round(time.time() - summary["started"], 2)
    return summary


def enrichment_daemon(interval: int = 900, batch_size: int = 500):
    """
    Run continuously: enrich unenriched lane_leads on a loop.
    Note: A2A push is handled by a2a_buyer_marketplace.py on its own timer.
    """
    print(f"[intelligence] enrichment daemon starting, interval={interval}s, batch={batch_size}")
    while True:
        try:
            s = enrichment_cycle(batch_size)
            print(f"[intelligence] cycle: considered={s['considered']} enriched={s['enriched']} errors={s['errors']} elapsed={s['elapsed']}s")
        except Exception as e:
            print(f"[enrichment_daemon] error: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "daemon":
        enrichment_daemon()
    elif len(sys.argv) > 1 and sys.argv[1] == "once":
        # one-shot for systemd timer
        s = enrichment_cycle(int(sys.argv[2]) if len(sys.argv) > 2 else 500)
        print(json.dumps(s, indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "aeo":
        print(json.dumps(auto_aeo(), indent=2))
    elif len(sys.argv) > 1 and sys.argv[1] == "test":
        # Quick test
        from empire_os.lead_sources import LeadCandidate
        test = LeadCandidate(
            name="ABC Roofing", email="info@abcroof.com", phone="555-1234",
            niche="roofing", metro="LAX", state="CA",
            details="Roof repair and replacement in LA", source="universal_scraper",
            lead_score=55, url="https://abcroof.com"
        )
        e = enrich_lead(test)
        print(json.dumps(e.to_dict(), indent=2))
    else:
        print("Usage: python3 -m empire_os.intelligence_integration [daemon|aeo|test]")
