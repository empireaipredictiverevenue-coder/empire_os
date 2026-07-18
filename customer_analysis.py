#!/usr/bin/env python3
"""
Empire OS — Customer Analysis (AGI + Synthetic Intelligence).
TIHD: Trigger-Intent-Habit-Discovery per customer.

AGI layer: when an LLM (MiniMax M3) is reachable, it generates the TIHD narrative
(triggers, inferred intent, habit loop, discovery path) from raw CRM signals.
Synthetic fallback: rule-based heuristics when LLM is 503/unavailable — never blind.

No hard deps: imports agent_core.OllamaClient (MiniMax-ready) inside a try so the
module works even if the framework path shifts. Reads CRM via crm_query helper.
"""
import json, subprocess, time, os, sys

CONTAINER = "empire-hub"
OUT = "/root/feedback/customer_analysis.json"

sys.path.insert(0, "/root/empire_os")
try:
    from empire_os.agent_core import OllamaClient
    _LLM_OK = True
except Exception:
    _LLM_OK = False


def _llm():
    """Return a MiniMax-backed client, or None if unreachable."""
    if not _LLM_OK:
        return None
    try:
        key = os.environ.get("MINIMAX_API_KEY", "")
        base = os.environ.get("LLM_BASE_URL", "https://api.minimax.io/v1")
        model = os.environ.get("LLM_MODEL", "MiniMax-M3")
        return OllamaClient(base_url=base, model=model, api_key=key, timeout=30)
    except Exception:
        return None


def _crm(query, args=()):
    cmd = ["incus", "exec", CONTAINER, "--", "/root/venv/bin/python3",
           "/root/empire_os/crm_query.py", query, json.dumps(list(args))]
    try:
        return json.loads(subprocess.run(cmd, capture_output=True, text=True,
                                          timeout=20).stdout)
    except Exception:
        return []


def _syn_profile(biz, email, src, url):
    """Synthetic (rule-based) TIHD profile — always works."""
    vert = src.split(":")[-1] if ":" in src else "unknown"
    triggers = [f"detected via {src}"] + (
        ["permit/registration signal"] if vert in ("logistics", "roofing", "hvac") else [])
    intent = "high" if (email and url) else ("med" if email else "low")
    habit = "repeat" if src.count(":") >= 1 else "new"
    discovery = f"peer/agent discovery via {vert} cluster" if email else "uncategorized"
    return {"triggers": triggers, "intent": intent,
            "habit_loop": habit, "discovery_path": discovery}


def analyze(customer=None, vertical=None, limit=20, use_agi=True):
    """TIHD customer analysis. use_agi=True → LLM narrative when available."""
    if customer:
        rows = _crm("SELECT business_name, email, source, url FROM si_buyer_outreach "
                    "WHERE business_name LIKE ? LIMIT ?", (f"%{customer}%", limit))
    else:
        v = vertical or "logistics"
        rows = _crm("SELECT business_name, email, source, url FROM si_buyer_outreach "
                    "WHERE source LIKE ? ORDER BY prospect_id DESC LIMIT ?",
                    (f"%{v}%", limit))
    llm = _llm() if use_agi else None
    customers = []
    for r in rows:
        if not isinstance(r, list) or len(r) < 3:
            continue
        biz, email, src, url = r[0], r[1], r[2], (r[3] if len(r) > 3 else "")
        prof = _syn_profile(biz, email, src, url)
        rec = {"customer": biz, "email": email, "vertical": prof.get("discovery_path", "").split()[-1] if False else src.split(":")[-1],
               "reachable": bool(email), **prof}
        # AGI: ask LLM to enrich the narrative if reachable
        if llm and email:
            try:
                prompt = (f"Customer: {biz} ({rec['vertical']}). Triggers: {prof['triggers']}. "
                          f"Intent: {prof['intent']}. As a growth strategist, in 2 sentences "
                          f"say how to deepen this relationship via trigger+discovery, not a funnel.")
                narr = llm.chat(prompt) if hasattr(llm, "chat") else llm(prompt)
                rec["agi_narrative"] = (narr[:300] if narr else "")
            except Exception:
                rec["agi_narrative"] = ""  # graceful: synthetic only
        customers.append(rec)
    return {"analyzed": len(customers), "agi_used": bool(llm),
            "customers": customers,
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


if __name__ == "__main__":
    cust = sys.argv[1] if len(sys.argv) > 1 else None
    vert = sys.argv[2] if len(sys.argv) > 2 else "logistics"
    out = analyze(customer=cust, vertical=vert)
    print(json.dumps(out, indent=2)[:700])
