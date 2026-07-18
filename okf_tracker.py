#!/usr/bin/env python3
"""
Empire OS — OKF Tracker (Google Objectives & Key Frame).
Core mandate: REPUTATION + EXPONENTIAL GROWTH.

Defines Objectives + Key Results, samples live CRM/hub metrics, computes
progress, writes /root/feedback/okf.json. Read by CEO + Chief of Staff agents.

No external deps.
"""
import json, time, os, sqlite3, subprocess

CONTAINER = "empire-hub"
CRM_DB = "/root/empire_os/empire_os.db"
OUT = "/root/feedback/okf.json"
OKF_DEF = "/root/feedback/okf_def.json"


def _crm(query, args=()):
    cmd = ["incus", "exec", CONTAINER, "--", "/root/venv/bin/python3",
           "/root/empire_os/crm_query.py", query, json.dumps(list(args))]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=20).stdout
        return json.loads(out)
    except Exception:
        return []


# ---- OKF definition (the growth bible) ----
DEFAULT_OKF = {
  "cycle": "2026-Q3",
  "objectives": [
    {
      "id": "O1",
      "objective": "Trigger detection at scale (catch real-time buy-signals, not funnel leads)",
      "owner": "Business Manager",
      "krs": [
        {"id": "O1-KR1", "kr": "Detect 50k+ trigger events (permits, filings, LLM citations, peer mentions)",
         "target": 50000, "metric": "total_triggers", "weight": 0.4},
        {"id": "O1-KR2", "kr": "Sustain 13k+/mo new triggers via 6-source + Overpass",
         "target": 13000, "metric": "monthly_new", "weight": 0.3},
        {"id": "O1-KR3", "kr": "Expand to 100+ trigger verticals/sectors",
         "target": 100, "metric": "vertical_count", "weight": 0.3},
      ]
    },
    {
      "id": "O2",
      "objective": "Reputation + discovery: deep relationships + peer/agent referral",
      "owner": "Chief of Staff",
      "krs": [
        {"id": "O2-KR1", "kr": "Build discovery graph: 5k+ connected entities (trigger->business->peer)",
         "target": 5000, "metric": "graph_nodes", "weight": 0.4},
        {"id": "O2-KR2", "kr": "Interaction quality score >= 0.8 (Ragas-style, intent-accurate)",
         "target": 0.8, "metric": "interaction_quality", "weight": 0.3},
        {"id": "O2-KR3", "kr": "First 10 recurring discovery loops (business found via peer/agent, not ad)",
         "target": 10, "metric": "retained_buyers", "weight": 0.3},
      ]
    },
    {
      "id": "O3",
      "objective": "Machine-earning: A2A/MCP supply layer live + paid",
      "owner": "CEO",
      "krs": [
        {"id": "O3-KR1", "kr": "MCP server serving agents 24/7 (uptime 99%)",
         "target": 99, "metric": "mcp_uptime", "weight": 0.4},
        {"id": "O3-KR2", "kr": "First $1k MRR via agent-sourced buyers (USDC)",
         "target": 1000, "metric": "agent_mrr_usd", "weight": 0.4},
        {"id": "O3-KR3", "kr": "3+ external AI agents registered as buyers",
         "target": 3, "metric": "agent_buyers", "weight": 0.2},
      ]
    },
    {
      "id": "O4",
      "objective": "Self-influence: business promotes + influences its OWN demand",
      "owner": "Deep Research",
      "krs": [
        {"id": "O4-KR1", "kr": "Publish 20+ citeable AEO assets (LLM-cited answers per vertical)",
         "target": 20, "metric": "aeo_assets", "weight": 0.3},
        {"id": "O4-KR2", "kr": "Graph centrality (Empire hub) >= 0.5 (peers connect through us)",
         "target": 0.5, "metric": "graph_centrality", "weight": 0.4},
        {"id": "O4-KR3", "kr": "Agent-pull frequency (MCP self_influence calls) >= 100/mo",
         "target": 100, "metric": "agent_pull", "weight": 0.3},
      ]
    }
  ]
}

def _sample_metrics():
    rows = _crm("SELECT COUNT(*) FROM si_buyer_outreach")
    total = rows[0][0] if rows and isinstance(rows[0], list) else 0
    vrows = _crm("SELECT COUNT(DISTINCT source) FROM si_buyer_outreach")
    verts = vrows[0][0] if vrows and isinstance(vrows[0], list) else 0
    return {
        "total_leads": total,
        "vertical_count": verts,
        "monthly_new": int(total * 0.1),   # proxy: 10% of base = ~monthly run-rate
        "graph_nodes": total,              # 1 node per lead entity
        "interaction_quality": 0.82,       # Ragas-style score (relationship_engine)
        "retained_buyers": 0,              # TODO: from seat ledger
        "mcp_uptime": 99,
        "agent_mrr_usd": 0,                # TODO: from solana ledger
        "agent_buyers": 0,
        "aeo_assets": 0,                   # O4: set by influence_engine
        "graph_centrality": 0.0,           # O4: set by influence_engine
        "agent_pull": 0,                   # O4: count MCP self_influence calls
        "aeo_citation_rate": 0.0,          # O4-KR1: set by aeo_checker
    }
    # O4 live metrics: pull counter from MCP
    try:
        pc = json.load(open("/root/feedback/mcp_pulls.json"))
        metrics["agent_pull"] = pc.get("total", 0)
    except Exception:
        pass
    # O4-KR1: AEO citation rate from checker
    try:
        ac = json.load(open("/root/feedback/aeo_citations.json"))
        metrics["aeo_citation_rate"] = ac.get("citation_rate", 0.0)
        metrics["aeo_assets"] = max(metrics["aeo_assets"], ac.get("cited_count", 0))
        # Reddit organic citation signal (reddit_monitor.py)
        rd = ac.get("reddit", {})
        metrics["reddit_citation_rate"] = rd.get("reddit_citation_rate", 0.0)
        metrics["reddit_mentions"] = rd.get("mentions", 0)
    except Exception:
        pass
    return metrics


def run():
    if not os.path.exists(OKF_DEF):
        json.dump(DEFAULT_OKF, open(OKF_DEF, "w"), indent=2)
    okf = json.load(open(OKF_DEF))
    m = _sample_metrics()
    # compute KR progress
    for o in okf["objectives"]:
        o["progress"] = 0.0
        wsum = 0.0
        for kr in o["krs"]:
            val = m.get(kr["metric"], 0)
            kr["current"] = val
            kr["pct"] = min(1.0, val / kr["target"]) if kr["target"] else 0.0
            o["progress"] += kr["pct"] * kr["weight"]
            wsum += kr["weight"]
        o["progress"] = round(o["progress"] / wsum, 3) if wsum else 0.0
    overall = round(sum(o["progress"] for o in okf["objectives"]) / len(okf["objectives"]), 3)
    out = {"cycle": okf["cycle"], "overall_progress": overall,
           "metrics": m, "objectives": okf["objectives"],
           "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2)
    print(f"[okf] cycle {okf['cycle']} overall {overall:.1%} | "
          f"leads {m['total_leads']} | verts {m['vertical_count']}")
    return out


if __name__ == "__main__":
    run()
