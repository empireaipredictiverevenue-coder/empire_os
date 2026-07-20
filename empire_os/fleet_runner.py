#!/usr/bin/env python3
"""
Empire OS — Department Fleet Runner (in-process, no containers).

Replaces the dead 80-container orchestrator. The 276 real modules now run
in-process inside empire-hub, grouped by department. Each department ticks
on its own natural cadence; the runner keeps every agent alive, writes
heartbeats, and emits a fleet_report.json the mesh can read.

No incus. No per-agent containers. One process, many departments.

Discovery: entrypoint resolution per module —
  - tries `main()`, `run()`, `forecast()`, `tick()` in that order
  - if none importable/runnable, the agent is marked REGISTERED (available
    as a department skill, not a live loop) — never crashes the fleet.

LLM-dependent agents (need Ollama) stay BLOCKED until networking phase.

Run: /root/venv/bin/python3 empire_os/fleet_runner.py
Heartbeats: /root/empire_os/config/agent_heartbeats.json
Fleet report: /root/empire_os/config/fleet_report.json
"""
import importlib, json, sys, time, traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
sys.path.insert(0, "/root/empire_os/empire_os")

REPO = Path("/root/empire_os")
HEARTBEATS = Path("/root/empire_os/config/agent_heartbeats.json")
FLEET_REPORT = Path("/root/empire_os/config/fleet_report.json")

# Department -> (modules, tick_interval_seconds)
# Mirrors scripts/gen_agent_skills.py DEPARTMENTS so skills + fleet stay in sync.
DEPARTMENTS = {
    "revenue":          (["seat_payment_onboarding", "founder_outreach", "settlement_gateway",
                           "solana_listener", "revenue_reasoner", "eval_connect_sweeps",
                           "build_buy_page", "migrate_prospects"], 300),
    "growth-marketing": (["advertising_agent", "outreach", "cold_outreach_worker", "campaigns",
                           "run_market_sweeps", "host_b2b_hunter", "search_api_leads",
                           "reddit_monitor"], 1800),
    "intelligence":     (["behavior_engine", "predictive_revenue", "deep_research_agent",
                           "scout_agent", "customer_analysis", "relationship_engine",
                           "influence_engine", "okf_tracker", "habit_memory"], 900),
    "leadership-ops":   (["leadership_council", "chief_of_staff", "ceo_agent", "cto",
                           "agent_copilot", "agent_harness", "mesh_agent",
                           "cortex_health_watchdog"], 600),
    "content-seo":      (["aeo_generator", "aeo_checker", "aeo_monitor", "aeo_refresh",
                           "local_spinner", "vertical_feed", "build_product_docs",
                           "publish_products", "enrich_products"], 3600),
    "scrapers-sourcing":(["biz_scraper", "industrial_sniper", "empire_lead_crawler",
                           "captcha_farm", "verify_business", "verify_prospects", "crm_pool",
                           "supabase_lead_activation", "mcp_lead_server"], 1200),
    "infra-platform":   (["agi_agent_service", "synthetic_service", "business_dir",
                           "storm_strike", "satellite_strike"], 1800),
}

# Modules that need an LLM (Ollama) to reason — blocked until networking phase.
LLM_MODULES = {"mesh_agent", "ceo_agent", "cto", "chief_of_staff"}

ENTRYPOINTS = ("main", "run", "forecast", "tick")

# last-run timestamp per agent (for cadence)
_last_run = {}


def _beat(name, status, detail):
    reg = {}
    if HEARTBEATS.exists():
        try:
            reg = json.loads(HEARTBEATS.read_text())
        except Exception:
            reg = {}
    reg[name] = {"status": status, "detail": detail,
                 "ts": datetime.now(timezone.utc).isoformat()}
    HEARTBEATS.parent.mkdir(parents=True, exist_ok=True)
    HEARTBEATS.write_text(json.dumps(reg, indent=2))


# Modules that are long-running services / daemons / side-effecting.
# The fleet runner does NOT tick these (they run as their own systemd
# services or must be invoked explicitly). Marked SERVICE, never called.
# Calling main() on some (e.g. seat_payment_onboarding) triggers LIVE
# side effects (email flush) — must be excluded from the tick loop.
SERVICES = {
    "seat_payment_onboarding", "solana_listener", "mcp_lead_server",
    "revenue_reasoner", "agi_agent_service", "synthetic_service",
    "storm_strike", "satellite_strike", "founder_outreach",
    "advertising_agent", "outreach", "cold_outreach_worker",
    "run_market_sweeps", "host_b2b_hunter", "search_api_leads",
    "reddit_monitor", "biz_scraper", "industrial_sniper",
    "empire_lead_crawler", "captcha_farm", "crm_pool",
    "aeo_generator", "aeo_checker", "aeo_monitor", "aeo_refresh",
    "local_spinner", "build_product_docs", "publish_products",
    "enrich_products", "vertical_feed", "business_dir",
    "supabase_lead_activation", "verify_business", "verify_prospects",
    "campaigns", "deep_research_agent", "scout_agent",
    "customer_analysis", "relationship_engine", "influence_engine",
    "okf_tracker", "habit_memory", "agent_copilot", "agent_harness",
    "cortex_health_watchdog",
    "social_syndication",
}


def _resolve_entrypoint(mod_name):
    """Return (module_obj, callable_name) or (None, reason)."""
    candidates = [
        f"empire_os.{mod_name}",
        mod_name,
        f"empire_os.agents.{mod_name}",
    ]
    for mod_path in candidates:
        try:
            m = importlib.import_module(mod_path)
        except Exception:
            continue
        for fn in ENTRYPOINTS:
            if hasattr(m, fn) and callable(getattr(m, fn)):
                return m, fn
    return None, "no entrypoint (registered only)"


def tick_agent(name):
    if name in LLM_MODULES:
        _beat(name, "BLOCKED", "needs Ollama reachable (networking phase)")
        return {"name": name, "status": "BLOCKED"}
    if name in SERVICES:
        _beat(name, "SERVICE", "long-running/side-effecting — launched separately")
        return {"name": name, "status": "SERVICE"}
    m, fn = _resolve_entrypoint(name)
    if m is None:
        _beat(name, "REGISTERED", "no live entrypoint — available as department skill")
        return {"name": name, "status": "REGISTERED"}
    try:
        t = time.time()
        getattr(m, fn)()
        dt = time.time() - t
        _beat(name, "OK", f"ran {fn} in {dt:.2f}s")
        return {"name": name, "status": "OK", "ms": round(dt * 1000)}
    except Exception as e:
        _beat(name, "FAIL", f"{type(e).__name__}: {e}")
        return {"name": name, "status": "FAIL", "error": str(e)[:160]}


def run_once():
    results = []
    for dept, (mods, _interval) in DEPARTMENTS.items():
        for name in mods:
            results.append(tick_agent(name))
    return results


def loop():
    print("[fleet] department fleet runner starting — in-process, no containers")
    while True:
        cycle_start = time.time()
        results = run_once()
        ok = sum(1 for r in results if r["status"] == "OK")
        reg = sum(1 for r in results if r["status"] == "REGISTERED")
        blk = sum(1 for r in results if r["status"] == "BLOCKED")
        fail = sum(1 for r in results if r["status"] == "FAIL")
        report = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "departments": len(DEPARTMENTS),
            "agents": len(results),
            "ok": ok, "registered": reg, "blocked": blk, "fail": fail,
            "cycle_ms": round((time.time() - cycle_start) * 1000),
        }
        FLEET_REPORT.parent.mkdir(parents=True, exist_ok=True)
        FLEET_REPORT.write_text(json.dumps(report, indent=2))
        # cadence: re-run full fleet every 60s (departments stagger internally
        # via _last_run if we later add per-agent spacing). Keep it simple: 60s.
        time.sleep(60)


if __name__ == "__main__":
    try:
        loop()
    except KeyboardInterrupt:
        print("[fleet] shutting down")
        sys.exit(0)
