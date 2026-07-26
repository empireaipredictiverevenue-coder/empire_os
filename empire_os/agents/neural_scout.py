#!/usr/bin/env python3
"""
neural_scout.py — Empire Neural Scout: AI-enhanced prospect discovery + intel synthesis.
Combines:
- Scout Intel (file inbox ingestion) 
- Neural Scout (ML lead scoring)
- Cortex Engine (predictive revenue intelligence)
- Intelligence Core (strategic decision support)

Runs as daemon inside empire-hub container. Every 60s:
1. Ingests raw intel from /root/inbox/phone (scout_intel)
2. Scores lane_leads with NeuralScout (ML + rule-based)
3. Runs Cortex 4-pillar analysis (revenue/leaks/waste/gaps)
4. Emits strategic recommendations via Intelligence Core
5. Writes unified intelligence report to /root/feedback/neural_intel_report.json
"""

import hashlib, json, os, sys, time, subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/empire_os/empire_os")

INBOX = Path("/root/inbox/phone")
RAW = Path("/root/feedback/raw_intel")
OUT = Path("/root/feedback/neural_intel_report.json")
LOG = Path("/root/feedback/scout_log.jsonl")

INTERVAL = int(os.environ.get("INTERVAL", "60"))

# Load .env for secrets
_ENV = "/root/empire_os/.env"
if os.path.exists(_ENV):
    for ln in open(_ENV).read().splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#") or "=" not in ln:
            continue
        k, v = ln.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v

def log(level, msg, **fields):
    e = {"ts": datetime.now(timezone.utc).isoformat(), "level": level, "msg": msg, **fields}
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG, "a") as f: f.write(json.dumps(e) + "\n")
    print(json.dumps(e), flush=True)

def fingerprint(p: Path) -> dict:
    b = p.read_bytes()
    return {
        "size_bytes": len(b),
        "sha256": hashlib.sha256(b).hexdigest()[:16],
        "head": b[:4096].decode("latin-1", errors="replace"),
        "tail": b[-4096:].decode("latin-1", errors="replace"),
    }

def ingest_intel():
    """Scout Intel: ingest files from D: drops"""
    if not INBOX.exists():
        return []
    RAW.mkdir(parents=True, exist_ok=True)
    results = []
    for p in INBOX.iterdir():
        if not p.is_file(): continue
        out = RAW / (p.stem + ".json")
        if out.exists(): continue
        try:
            meta = fingerprint(p)
            rec = {"file": str(p), "seen_at": datetime.now(timezone.utc).isoformat(),
                   "ext": p.suffix.lower(), **meta}
            out.write_text(json.dumps(rec, indent=2))
            log("INTEL", "ingested", file=p.name, sha=meta["sha256"], size=meta["size_bytes"])
            results.append(rec)
        except Exception as e:
            log("ERROR", "ingest_failed", file=p.name, err=str(e)[:200])
    return results

def run_neural_scout():
    """Neural Scout: score leads with ML + rules + ICP"""
    try:
        from empire_os.neural_scout import NeuralScout
        from empire_os.funnel import SQLiteBackend
        import sqlite3
        
        db_path = "/root/empire_os/empire_os.db"
        backend = SQLiteBackend(db_path)
        con = sqlite3.connect(db_path, timeout=30)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA busy_timeout=30000")
        
        # ICP engine import
        try:
            from empire_os.icp import find_best_icp, DEFAULT_ICP_PROFILES
            ICP_AVAILABLE = True
        except ImportError:
            ICP_AVAILABLE = False
            log("WARNING", "icp_not_available", msg="ICP engine not importable")
        
        # Phase 1: Score unscored-by-omega leads with ML
        leads = con.execute("""
            SELECT id, prospect_id, notes, niche, metro, zip, street, omega_score, omega_tier
            FROM lane_leads 
            WHERE omega_score IS NULL OR omega_score = 0
            LIMIT 500
        """).fetchall()
        
        if not leads and not ICP_AVAILABLE:
            con.close()
            return {"scored": 0, "leads": []}
        
        scored = []
        if leads:
            scout = NeuralScout(backend=backend, min_score=0.0)
            for (lid, prospect_id, notes, niche, metro, zip_code, street, omega_score, omega_tier) in leads:
                try:
                    scored_lead = scout.evaluate(
                        niche=niche or "",
                        details=notes or "",
                        phone="",
                        zip_code=zip_code or "",
                        name="",
                        address=street or "",
                        source="web",
                        prospect_id=prospect_id
                    )
                    if scored_lead:
                        score_val = scored_lead.score
                        tier = scored_lead.tier if hasattr(scored_lead, 'tier') else "D"
                        con.execute("UPDATE lane_leads SET omega_score=?, omega_tier=? WHERE id=?",
                                   (score_val, tier, lid))
                        scored.append({"id": lid, "score": score_val, "tier": tier})
                    else:
                        con.execute("UPDATE lane_leads SET omega_score=?, omega_tier=? WHERE id=?",
                                   (0.5, "C", lid))
                        scored.append({"id": lid, "score": 0.5, "tier": "C"})
                except Exception as e:
                    log("ERROR", "neural_score_failed", lead=lid, err=str(e)[:100])
        
        # Phase 2: ICP scoring on all leads missing ICP
        if ICP_AVAILABLE:
            try:
                icp_uncovered = con.execute(
                    "SELECT id, niche, metro, city, state, zip, street, omega_score FROM lane_leads "
                    "WHERE (icp_fit_score IS NULL OR icp_fit_score = 0) LIMIT 500"
                ).fetchall()
                for row in icp_uncovered:
                    try:
                        lead_dict = {
                            "niche": row[1] or "",
                            "metro": row[2] or "",
                            "city": row[3] or "",
                            "state": row[4] or "",
                            "zip": row[5] or "",
                            "street": row[6] or "",
                            "omega_score": row[7] or 0,
                        }
                        icp_result = find_best_icp(lead_dict)
                        con.execute(
                            "UPDATE lane_leads SET icp_fit_score=?, icp_tier=? WHERE id=?",
                            (icp_result["icp_fit_score"], icp_result["icp_tier"], row[0])
                        )
                    except Exception as icp_err:
                        log("DEBUG", "icp_score_failed", lead=row[0], err=str(icp_err)[:60])
                con.commit()
                log("ICP", f"scored {len(icp_uncovered)} leads", profiles=len(DEFAULT_ICP_PROFILES))
            except Exception as e:
                log("ERROR", "icp_batch_failed", err=str(e)[:100])
        
        con.close()
        return {"scored": len(scored), "leads": scored[:10]}
    except Exception as e:
        log("ERROR", "neural_scout_failed", err=str(e)[:200])
        return {"scored": 0, "error": str(e)[:200]}

def run_cortex_pillars():
    """Cortex Engine: 4-pillar predictive analysis"""
    try:
        import empire_os.predictive as P
        import sqlite3
        
        db_path = "/root/empire_os/empire_os.db"
        con = sqlite3.connect(db_path, timeout=30)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA synchronous=NORMAL")
        con.execute("PRAGMA busy_timeout=30000")
        
        # Pillar 1: Revenue
        lanes = con.execute("SELECT COUNT(*) FROM lanes").fetchone()[0]
        occupied = con.execute("SELECT COUNT(*) FROM lanes WHERE occupied_by IS NOT NULL AND occupied_by != ''").fetchone()[0]
        leads_total = con.execute("SELECT COUNT(*) FROM si_buyer_outreach").fetchone()[0]
        subs = con.execute("SELECT status, COUNT(*) FROM si_subscription GROUP BY status").fetchall()
        deals = con.execute("SELECT stage, COUNT(*) FROM crm_deals GROUP BY stage").fetchall()
        funnel = {}
        for st, n in subs: funnel[st] = n
        for st, n in deals: funnel[st] = funnel.get(st, 0) + n
        avg_seat = (con.execute("SELECT AVG(price_cents) FROM si_subscription WHERE price_cents>0").fetchone()[0] or 59900) / 100.0
        conv = 0.05
        try:
            rev = P.predict_revenue(lanes, occupied, leads_total, funnel, avg_seat_price=avg_seat, conversion_rate=conv)
        except:
            rev = {"error": "predict_revenue failed"}
        
        # Pillar 2: Leaks
        funnel_leaks = {}
        for st, n in con.execute("SELECT status, COUNT(*) FROM si_subscription GROUP BY status").fetchall():
            funnel_leaks[st] = n
        for st, n in con.execute("SELECT stage, COUNT(*) FROM crm_deals GROUP BY stage").fetchall():
            funnel_leaks[st] = funnel_leaks.get(st, 0) + n
        try:
            leaks = P.detect_leaks(funnel_leaks)
        except:
            leaks = {"error": "detect_leaks failed"}
        uncollected = con.execute("SELECT COUNT(*), COALESCE(SUM(amount_usdc),0) FROM crm_deals WHERE stage='awaiting_payment'").fetchone()
        charges = con.execute("SELECT COUNT(*) FROM si_charges").fetchone()[0]
        settlements = con.execute("SELECT COUNT(*) FROM si_settlements").fetchone()[0]
        
        # Pillar 3: Waste
        empty_lanes = con.execute("SELECT COUNT(*) FROM lanes WHERE occupied_by IS NULL OR occupied_by = ''").fetchone()[0]
        try:
            waste = P.detect_waste(lane_data=[], agent_health={})
            waste["empty_lanes"] = empty_lanes
            waste["total_lanes"] = lanes
        except:
            waste = {"error": "detect_waste failed", "empty_lanes": empty_lanes}
        
        # Pillar 4: Market Gaps
        niches_demand = con.execute("SELECT niche, COUNT(*) FROM si_buyer_outreach GROUP BY niche ORDER BY 2 DESC LIMIT 10").fetchall()
        lanes_supply = con.execute("SELECT sub_niche, COUNT(*) FROM lanes GROUP BY sub_niche").fetchall()
        try:
            gaps = P.detect_market_gaps(
                lane_data=[{"niche": n, "count": c} for n, c in lanes_supply],
                lead_data=[{"niche": n, "count": c} for n, c in niches_demand])
        except:
            gaps = {"error": "detect_market_gaps failed"}
        
        con.close()
        
        return {
            "revenue": {"lanes": lanes, "occupied_lanes": occupied, "leads_total": leads_total,
                       "avg_seat_price": round(avg_seat, 2), "projection": rev},
            "leaks": {"leaks": leaks, "uncollected_seats": uncollected[0],
                     "uncollected_usdc": round(uncollected[1], 2), "charges": charges, "settlements": settlements},
            "waste": {"waste": waste, "empty_lanes": empty_lanes},
            "market_gaps": {"market_gaps": gaps, "top_demand_niches": [{"niche": n, "count": c} for n, c in niches_demand[:5]]}
        }
    except Exception as e:
        log("ERROR", "cortex_failed", err=str(e)[:200])
        return {"error": str(e)[:200]}

def run_intelligence_core(state: dict):
    """Intelligence Core: strategic recommendations from state"""
    try:
        # Simple rule-based strategic analysis (no LLM dependency)
        recommendations = []
        
        # Revenue insights
        rev = state.get("revenue", {})
        if rev.get("projection", {}).get("unrealized_mrr", 0) > 50000:
            recommendations.append({
                "type": "REVENUE_EXPANSION",
                "priority": "HIGH",
                "insight": f"${rev['projection']['unrealized_mrr']:,.0f} unrealized MRR from {rev.get('empty_lanes', 0)} empty lanes",
                "action": "Prioritize lane recruitment in top demand niches"
            })
        
        # Lead quality
        leads = state.get("neural_scout", {})
        if leads.get("scored", 0) > 0:
            high_tier = sum(1 for l in leads.get("leads", []) if l.get("tier") in ("A", "B"))
            recommendations.append({
                "type": "LEAD_QUALITY",
                "priority": "MEDIUM",
                "insight": f"Scored {leads['scored']} leads, {high_tier} high-tier (A/B)",
                "action": "Route high-tier leads to premium buyers immediately"
            })
        
        # Market gaps
        gaps = state.get("market_gaps", {})
        hot_gaps = gaps.get("market_gaps", {}).get("hot_gaps", [])
        if hot_gaps:
            recommendations.append({
                "type": "MARKET_GAP",
                "priority": "HIGH",
                "insight": f"{len(hot_gaps)} hot market gaps detected",
                "action": "Launch AEO pages for top 3 gaps: " + ", ".join(g["niche_metro"] for g in hot_gaps[:3])
            })
        
        # Waste
        waste = state.get("waste", {})
        empty = waste.get("empty_lanes", 0)
        if empty > 100:
            recommendations.append({
                "type": "WASTE_REDUCTION",
                "priority": "MEDIUM",
                "insight": f"{empty} empty lanes burning capacity",
                "action": "Run corridor repricing or retire bottom 20% lanes"
            })
        
        return {"recommendations": recommendations, "count": len(recommendations)}
    except Exception as e:
        log("ERROR", "intelligence_core_failed", err=str(e)[:200])
        return {"error": str(e)[:200]}

def main():
    RAW.mkdir(parents=True, exist_ok=True)
    INBOX.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    
    log("START", "neural_scout_online", interval=INTERVAL)
    
    while True:
        cycle_start = time.time()
        try:
            log("CYCLE", "start")
            
            # 1. Scout Intel ingestion
            intel = ingest_intel()
            
            # 2. Neural Scout scoring
            neural = run_neural_scout()
            
            # 3. Cortex 4-pillar analysis
            cortex = run_cortex_pillars()
            
            # 4. Intelligence Core strategic recommendations
            combined_state = {
                "intel_ingested": len(intel),
                "neural_scout": neural,
                "revenue": cortex.get("revenue", {}),
                "leaks": cortex.get("leaks", {}),
                "waste": cortex.get("waste", {}),
                "market_gaps": cortex.get("market_gaps", {})
            }
            intelligence = run_intelligence_core(combined_state)
            
            # 5. Unified report
            report = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "cycle_duration_ms": round((time.time() - cycle_start) * 1000, 2),
                "intel_ingested": len(intel),
                "neural_scout": neural,
                "cortex": cortex,
                "intelligence": intelligence,
                "status": "healthy"
            }
            
            # Atomic write
            tmp = OUT.with_suffix(".tmp")
            tmp.write_text(json.dumps(report, indent=2, default=str))
            tmp.replace(OUT)
            
            log("CYCLE", "complete", 
                intel=len(intel), 
                scored=neural.get("scored", 0),
                mrr=cortex.get("revenue", {}).get("projection", {}).get("total_predicted_mrr", 0),
                recs=intelligence.get("count", 0))
            
        except Exception as e:
            log("ERROR", "cycle_failed", err=str(e)[:200])
        
        elapsed = time.time() - cycle_start
        sleep_time = max(1, INTERVAL - elapsed)
        time.sleep(sleep_time)

if __name__ == "__main__":
    main()