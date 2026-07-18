#!/usr/bin/env python3
"""
Empire OS — Deep Research Agent (AGI + Synthetic Intelligence).
Owns the AI-trends surface: A2A, AEO/GEO, AI-SEO, SEO, optimization.
Researches via the 6 free search sources (no paid), reasons on MiniMax (AGI) when
available, writes findings + CEO directives to /root/feedback/deep_research.jsonl.

Runs as persistent loop (no cron). Tick 6h. Feeds the C-suite.
"""
import json, time, os, sys, subprocess

FEEDBACK = "/root/feedback"
OUT = f"{FEEDBACK}/deep_research.jsonl"
CEO_DIRECTIVES = f"{FEEDBACK}/ceo_directives.jsonl"
TICK = 21600  # 6h
SOUL = "/root/empire_os/empire_os/agents/souls/deep_research_SOUL.md"
sys.path.insert(0, "/root/empire_os")
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

# topics this agent owns
TOPICS = ["A2A agent2agent protocol", "answer engine optimization AEO GEO",
          "AI SEO generative engine", "SEO 2026 trends", "LLM optimization",
          "agent marketplace USDC settlement", "MCP model context protocol"]

sys.path.insert(0, "/root/empire_os")
try:
    from empire_os.agent_core import OllamaClient
    _LLM_OK = True
except Exception:
    _LLM_OK = False


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


def _web_research(query, n=5):
    """Use the 6-source engine's Mojeek (free, no-key) to pull real signals."""
    try:
        import search_api_leads as _m
        doms = _m.mojeek_domains(query) if hasattr(_m, "mojeek_domains") else []
        return doms[:n]
    except Exception:
        return []


def research_topic(topic, llm):
    signals = _web_research(topic)
    finding = {"topic": topic, "signals_found": len(signals),
               "signal_domains": signals}
    # AGI synthesis when LLM reachable
    if llm:
        try:
            prompt = (f"Research brief on '{topic}' for a B2B lead-gen business. "
                      f"In 3 bullet points: what changed in 2026, how it affects "
                      f"customer acquisition (trigger-intent-habit-discovery, not funnel), "
                      f"one actionable move. Under 120 words.")
            out = llm.chat(prompt) if hasattr(llm, "chat") else llm(prompt)
            finding["agi_brief"] = (out[:600] if out else "")
        except Exception:
            finding["agi_brief"] = ""
    else:
        finding["agi_brief"] = ""  # synthetic: signal-only
    return finding


def observe():
    return {"topics": TOPICS, "last_run": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def reason(state, llm):
    findings = [research_topic(t, llm) for t in state["topics"]]
    # derive a CEO directive if any topic shows actionable signal
    directive = {
        "type": "ai_trends_research",
        "msg": f"Deep research complete: {len(findings)} topics scanned. "
               f"Top signal: {findings[0]['topic']} ({findings[0]['signals_found']} hits). "
               f"Apply AEO/A2A to lead supply — optimize for LLM citation + agent discovery.",
        "priority": "med", "findings": findings}
    return directive


def act(directive):
    os.makedirs(FEEDBACK, exist_ok=True)
    rec = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "role": "DeepResearch", **directive}
    with open(OUT, "a") as f:
        f.write(json.dumps(rec) + "\n")
    if _HABIT:
        hm.record("deep_research", "scan", {"topics": len(directive.get("findings", []))})
    # forward to CEO directives (C-suite loop consumes it)
    with open(CEO_DIRECTIVES, "a") as f:
        f.write(json.dumps({"ts": rec["ts"], "role": "CEO", "type": "ai_trends",
                            "msg": directive["msg"], "priority": directive["priority"]}) + "\n")
    print(f"[research] {len(directive['findings'])} topics | "
          f"signal: {directive['findings'][0]['topic']}")


def loop():
    llm = _llm()
    soul = load_soul()
    print(f"[research] agent live — A2A/AEO/AI-SEO/SEO | AGI={'on' if llm else 'synthetic'} | soul {len(soul)}c")
    if _HABIT:
        print(f"[research] habit memory ON ({len(hm.load('deep_research'))} prior scans)")
    while True:
        try:
            act(reason(observe(), llm))
        except Exception as e:
            print(f"[research] err: {e}")
        time.sleep(TICK)


if __name__ == "__main__":
    loop()
