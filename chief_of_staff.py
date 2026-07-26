#!/usr/bin/env python3
"""
chief_of_staff.py — Empire OS Chief of Staff
Translates CEO vision + OKF gaps → actionable tasks for Business Manager
Monitors: OKF, CEO directives, relationship graph, customer analysis, agent health
Outputs: /root/feedback/cos_tasks.jsonl (task queue for business_manager)
"""
import json, os, time
from datetime import datetime, timezone
from pathlib import Path

FEEDBACK = Path("/root/feedback")
OKF = FEEDBACK / "okf.json"
CEO_DIRECTIVES = FEEDBACK / "ceo_directives.jsonl"
COS_TASKS = FEEDBACK / "cos_tasks.jsonl"
RELATIONSHIP = FEEDBACK / "relationship_graph.json"
CUSTOMER_ANALYSIS = FEEDBACK / "customer_analysis.json"
AGENT_HEALTH = FEEDBACK / "agent_health.jsonl"

TICK_SECONDS = int(os.environ.get("COS_TICK", "900"))  # 15 min

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def load_json(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}

def load_jsonl(path, max_lines=100):
    try:
        lines = path.read_text().strip().splitlines()
        return [json.loads(l) for l in lines[-max_lines:]]
    except Exception:
        return []

def write_task(task):
    task["ts"] = now_iso()
    task["role"] = "ChiefOfStaff"
    COS_TASKS.parent.mkdir(parents=True, exist_ok=True)
    with open(COS_TASKS, "a") as f:
        f.write(json.dumps(task) + "\n")

def check_okf_gaps():
    """Create tasks from OKF objective gaps"""
    okf = load_json(OKF)
    if not okf:
        return
    
    for obj in okf.get("objectives", []):
        obj_id = obj.get("id", "?")
        for kr in obj.get("krs", []):
            kr_id = kr.get("id", "?")
            current = kr.get("current", 0)
            target = kr.get("target", 1)
            pct = kr.get("pct", 0)
            
            if pct < 0.5:  # Below 50% of target
                write_task({
                    "type": "okf_gap",
                    "objective": obj_id,
                    "key_result": kr_id,
                    "detail": f"{kr.get('kr', kr_id)} at {current}/{target} ({pct:.0%})",
                    "priority": "high" if pct < 0.25 else "med",
                    "owner": "business_manager",
                    "action": f"accelerate_{obj_id.lower()}_{kr_id.lower()}"
                })

def check_ceo_directives():
    """Convert CEO directives to tasks"""
    directives = load_jsonl(CEO_DIRECTIVES, max_lines=20)
    for d in directives:
        if d.get("role") == "CEO" and d.get("priority") in ("high", "critical"):
            write_task({
                "type": "ceo_directive",
                "detail": d.get("msg", ""),
                "priority": d.get("priority"),
                "owner": "business_manager",
                "action": f"execute_{d.get('type', 'directive').lower()}"
            })

def check_relationship_health():
    """Monitor relationship graph metrics"""
    rel = load_json(RELATIONSHIP)
    if not rel:
        return
    
    quality = rel.get("interaction_quality") or 0
    nodes = rel.get("node_count", 0)
    centrality = rel.get("centrality") or 0
    
    if quality < 0.8:
        write_task({
            "type": "relationship_quality",
            "detail": f"Interaction quality {quality:.2f} < 0.8",
            "priority": "high",
            "owner": "business_manager",
            "action": "personalized_nurture_top_nodes"
        })
    
    if nodes < 5000:
        write_task({
            "type": "graph_growth",
            "detail": f"Relationship graph only {nodes} nodes (< 5k)",
            "priority": "med",
            "owner": "business_manager",
            "action": "mine_crm_referral_edges"
        })

def check_customer_intelligence():
    """Check for high-value customer signals"""
    ca = load_json(CUSTOMER_ANALYSIS)
    if not ca or "customers" not in ca:
        return
    
    for cust in ca["customers"]:
        if cust.get("tier") == "A" and cust.get("trigger_score", 0) > 0.8:
            write_task({
                "type": "high_value_trigger",
                "customer": cust.get("id"),
                "detail": f"Tier A customer trigger_score={cust['trigger_score']:.2f}",
                "priority": "high",
                "owner": "business_manager",
                "action": "immediate_outreach"
            })

def check_agent_health():
    """Monitor agent health from heartbeat logs"""
    try:
        lines = AGENT_HEALTH.read_text().strip().splitlines()
        recent = [json.loads(l) for l in lines[-50:]]
        down_agents = set()
        for r in recent:
            if r.get("status") == "down" or r.get("level") == "ERROR":
                down_agents.add(r.get("agent", "unknown"))
        
        for agent in down_agents:
            write_task({
                "type": "agent_down",
                "agent": agent,
                "detail": f"Agent {agent} reporting down/error",
                "priority": "high",
                "owner": "orchestrator",
                "action": "restart_agent"
            })
    except Exception:
        pass

def check_machine_earning():
    """Track agent-sourced MRR goal"""
    okf = load_json(OKF)
    if not okf:
        return
    
    agent_mrr = okf.get("metrics", {}).get("agent_mrr_usd", 0)
    if agent_mrr == 0:
        write_task({
            "type": "machine_earning",
            "detail": "No agent-sourced MRR yet — publish MCP endpoint + pitch agent networks",
            "priority": "high",
            "owner": "business_manager",
            "action": "publish_mcp_endpoint"
        })

def main():
    print(f"[{now_iso()}] Chief of Staff online — tick {TICK_SECONDS}s")
    COS_TASKS.parent.mkdir(parents=True, exist_ok=True)
    
    while True:
        cycle_start = time.time()
        try:
            # Clear old tasks (keep last 100)
            if COS_TASKS.exists():
                lines = COS_TASKS.read_text().strip().splitlines()
                if len(lines) > 100:
                    COS_TASKS.write_text("\n".join(lines[-100:]) + "\n")
            
            # Run all checks
            check_okf_gaps()
            check_ceo_directives()
            check_relationship_health()
            check_customer_intelligence()
            check_agent_health()
            check_machine_earning()
            
        except Exception as e:
            print(f"[{now_iso()}] ERROR: {e}")
        
        elapsed = time.time() - cycle_start
        sleep_time = max(1, TICK_SECONDS - elapsed)
        time.sleep(sleep_time)

if __name__ == "__main__":
    import sys
    sys.path.insert(0, "/root/empire_os")
    from datetime import datetime, timezone
    main()