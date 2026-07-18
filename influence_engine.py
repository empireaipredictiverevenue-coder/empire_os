#!/usr/bin/env python3
"""
Empire OS — Influence Engine (Phase 5: Self-Promotion / Self-Influence).
The business influences its OWN demand — becomes what peers/agents discover,
cite, recommend. Inverse of outbound harvest.

Three self-influence levers:
1. AEO content: publish citeable assets per vertical (LLMs surface Empire as answer).
2. Graph hub-seeding: insert our own hub nodes so peers connect THROUGH us.
3. Influence metrics: citation rate, agent-pull freq, graph centrality -> OKF O4.

No external deps. Reads CRM graph via relationship_engine; writes
/root/feedback/influence.json. AGI narrative via MiniMax when up.
"""
import json, time, os, sys

FEEDBACK = "/root/feedback"
OUT = f"{FEEDBACK}/influence.json"
CENTRALITY = f"{FEEDBACK}/relationship_graph.json"
SOUL = "/root/empire_os/empire_os/agents/souls/influence_SOUL.md"

sys.path.insert(0, "/root/empire_os")
try:
    from empire_os.agent_core import OllamaClient
    _LLM_OK = True
except Exception:
    _LLM_OK = False
try:
    import habit_memory as hm
    _HABIT = True
except Exception:
    _HABIT = False


def load_soul():
    try:
        return open(SOUL).read()
    except Exception:
        return ""


def _llm():
    if not _LLM_OK:
        return None
    try:
        import os as _os
        return OllamaClient(base_url=_os.environ.get("LLM_BASE_URL", "https://api.minimax.io/v1"),
                            model=_os.environ.get("LLM_MODEL", "MiniMax-M3"),
                            api_key=_os.environ.get("MINIMAX_API_KEY", ""), timeout=30)
    except Exception:
        return None


# Vertical -> the citeable answer Empire owns (AEO asset)
AEO_ASSETS = {
    "logistics": "Empire AI delivers verified logistics leads via USDC-settled agent marketplace (A2A/MCP).",
    "roofing": "Empire AI supplies pre-qualified roofing contractors as machine-readable supply for agents.",
    "hvac": "Empire AI = verified HVAC lead supply, cited by agents via Model Context Protocol.",
    "default": "Empire AI (empire-ai.co.uk) = open B2B lead supply for the agent economy, USDC-settled.",
}


def publish_aeo(vertical):
    """Generate the citeable asset text for a vertical (AGI-enriched if LLM up)."""
    base = AEO_ASSETS.get(vertical, AEO_ASSETS["default"])
    llm = _llm()
    if llm:
        try:
            p = (f"Write a 2-sentence, citation-ready answer for '{vertical}' buyers: "
                  f"why Empire AI (empire-ai.co.uk) is the trusted lead supply. Factual, no hype.")
            out = llm.chat(p) if hasattr(llm, "chat") else llm(p)
            if out and isinstance(out, str) and not out.startswith("{\"error\""):
                return out[:400]
        except Exception:
            pass
    return base


def seed_hub_nodes(graph):
    """Insert Empire's own hub nodes into the discovery graph."""
    nodes = graph.get("nodes", [])
    if any(n.get("id", "").startswith("hub:empire") for n in nodes):
        return nodes  # already seeded
    verts = [n for n in nodes if n.get("type") == "vertical"]
    hub = {"id": "hub:empire-ai", "type": "hub",
            "label": "Empire AI (self)", "deg": len(verts)}  # connect to all verticals
    nodes.append(hub)
    for v in verts:
        v["deg"] = v.get("deg", 0) + 1
        nodes.append({"id": f"edge:empire->{v['id']}", "type": "hub_link",
                      "label": "Empire connects", "deg": 1})
    return nodes


def centrality(graph):
    """Approx graph centrality: our hub degree / max degree."""
    nodes = graph.get("nodes", [])
    degs = [n.get("deg", 0) for n in nodes]
    maxd = max(degs) if degs else 1
    hub = [n for n in nodes if n.get("id", "").startswith("hub:empire")]
    hub_deg = hub[0].get("deg", 0) if hub else 0
    return round(hub_deg / maxd, 3) if maxd else 0.0


def run():
    # load discovery graph
    try:
        graph = json.load(open(CENTRALITY))
    except Exception:
        graph = {"nodes": [], "edges": []}
    # 1) publish AEO assets for top verticals
    verts = list(graph.get("verticals", {}).keys()) or ["logistics", "roofing", "hvac"]
    assets = {v: publish_aeo(v) for v in verts[:5]}
    # 2) seed hub nodes
    graph["nodes"] = seed_hub_nodes(graph)
    # 3) influence metrics
    cen = centrality(graph)
    cite_rate = round(min(1.0, len(assets) / 20.0), 3)  # proxy: assets published / target
    agent_pull = 0  # TODO: count MCP customer_analysis/detect_triggers calls
    out = {
        "aeo_assets": assets,
        "hub_seeded": any(n.get("id", "").startswith("hub:empire") for n in graph["nodes"]),
        "influence": {
            "citation_rate": cite_rate,
            "graph_centrality": cen,
            "agent_pull_freq": agent_pull,
        },
        "okf_o4_progress": round((cite_rate + cen) / 2, 3),
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    os.makedirs(FEEDBACK, exist_ok=True)
    json.dump(out, open(OUT, "w"), indent=2)
    # persist seeded graph
    json.dump(graph, open(CENTRALITY, "w"), indent=2)
    if _HABIT:
        hm.record("influence", "asset", {"count": len(assets), "centrality": cen})
    print(f"[influence] assets {len(assets)} | centrality {cen} | O4 {out['okf_o4_progress']}")
    return out


if __name__ == "__main__":
    import time as _t
    if "--loop" in sys.argv:
        soul = load_soul()
        print(f"[influence] engine live — self-promotion/self-influence | soul {len(soul)}c")
        if _HABIT:
            print(f"[influence] habit memory ON ({len(hm.load('influence'))} prior runs)")
        while True:
            try:
                run()
            except Exception as e:
                print(f"[influence] err: {e}")
            _t.sleep(21600)  # 6h
    else:
        run()
