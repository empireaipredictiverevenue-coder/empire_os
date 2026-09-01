#!/usr/bin/env python3
"""
brain_harness.py — THE HARNESS (Brain → all agents).

This is the physical control plane the Predictive Cloud Brain (Layer 23)
uses to command the entire Empire OS agent fleet. It is NOT just a
health-checker — it is the dispatch + supervision layer:

  1. Loads the standing scaling directive (BRAIN_SCALING_DIRECTIVE.md)
  2. Holds the full fleet registry (every agent, its engine, its tick fn)
  3. Each cycle:
       - probes every agent (alive? producing? on schedule?)
       - runs the agent's tick if due
       - writes heartbeats to agent_heartbeats.json (the brain's eyes)
       - if an agent is dead/stale -> triggers empire_watchdog restart
       - if a revenue gap is detected -> dispatches a corrective agent action
  4. Self-heals via empire_watchdog (DEAD -> restart + alert).

Run:  /root/venv/bin/python3 empire_os/brain_harness.py
Cron: every 5 min (aligned with watchdog) OR as a long-lived daemon.

NO new infra. Pure systemd + journalctl + sqlite + the directive file.
"""
from __future__ import annotations
import json, os, sys, time, subprocess, traceback
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/root/empire_os")
DB = "/root/empire_os/empire_os.db"
HEARTBEATS = "/root/empire_os/config/agent_heartbeats.json"
DIRECTIVE = "/root/empire_os/empire_os/BRAIN_SCALING_DIRECTIVE.md"
STATE = "/root/empire_os/logs/brain_harness_state.json"

# ── FLEET REGISTRY ──────────────────────────────────────────────────────────
# engine: which scaling engine the agent serves
# module / fn: how to invoke one tick (standalone agents)
# systemd: the service that keeps it alive (for health + restart)
FLEET = {
    # --- REVENUE LOOP (critical) ---
    # systemd values MUST match real `systemctl` unit names (verified 2026-09-01).
    # None = no dedicated unit (managed elsewhere / script-based) -> not false-flagged.
    "bsc_listener":        {"engine": "revenue_loop", "systemd": "empire-bsc-listener", "tick": None},
    "payment_matcher":     {"engine": "revenue_loop", "systemd": "empire-payment-matcher", "tick": None},
    "mail_sender":         {"engine": "revenue_loop", "systemd": "empire-mail-sender", "tick": None},
    "smtp_relay":          {"engine": "revenue_loop", "systemd": None, "tick": None},  # no dedicated unit; mail-sender covers it
    # --- MARKETPLACE (engine #1, $600M target) ---
    "buyer_hunter":        {"engine": "marketplace", "systemd": "empire-buyer-hunter", "tick": None},
    "a2a_publisher":       {"engine": "marketplace", "systemd": "empire-a2a-sales-agent", "tick": None},
    "a2a_buyer_mkt":       {"engine": "marketplace", "systemd": "empire-a2a-buyer-marketplace", "tick": None},
    "a2a_closer":          {"engine": "marketplace", "systemd": "empire-a2a-closer", "tick": None},
    "omni_agent":          {"engine": "marketplace", "systemd": None, "tick": None},  # no empire-omni-agent unit
    "revenue_engine":      {"engine": "marketplace", "systemd": "empire-revenue-generation", "tick": None},
    "router_engine":       {"engine": "marketplace", "systemd": "empire-ppc-router", "tick": None},
    "queue_sender":        {"engine": "marketplace", "systemd": "empire-unified-delivery", "tick": None},
    "lanes":               {"engine": "marketplace", "systemd": "empire-lanes", "tick": None},
    "neural_scout":        {"engine": "marketplace", "systemd": "empire-neural-scout", "tick": None},
    # --- INTELLIGENCE (L1-23) ---
    "omega_os":            {"engine": "intelligence", "systemd": "empire-omega-learning", "tick": None},
    "omega_learning":      {"engine": "intelligence", "systemd": "empire-omega-learning", "tick": None},
    "marketing_agent":     {"engine": "intelligence", "systemd": "empire-agent-marketing_agent", "tick": None},
    "agi_sim":             {"engine": "intelligence", "systemd": None, "tick": None},  # no empire-agi-sim unit
    "predictive_cloud":    {"engine": "intelligence", "systemd": "empire-predictive", "tick": None},
    # --- WHALE / ENTERPRISE / LAW-FIRM ---
    "whale_harvester":     {"engine": "whale", "systemd": None, "tick": None},  # no empire-whale-harvester unit
    "enterprise_campaigns":{"engine": "enterprise", "systemd": None, "tick": "empire_os.enterprise_campaigns:run", "script": True},
    # --- CONTENT ENGINE (top-of-funnel moat) ---
    "content_pipeline":    {"engine": "content", "systemd": None, "tick": "empire_os.content_pipeline:cycle", "script": True},
    # --- BETA OS (buyer/seller marketplace) covered by a2a_* above ---
}


def _log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")


def _service_active(spec: dict) -> bool:
    svc = spec["systemd"]
    if not svc:
        return True  # script-based, checked by tick
    target = ["incus", "exec", "empire-hub", "--", "systemctl", "is-active", svc] if spec.get("container") \
        else ["systemctl", "is-active", svc]
    try:
        r = subprocess.run(target, capture_output=True, text=True, timeout=10)
        st = r.stdout.strip()
        # Only "active" or "activating" count as alive. "activating" must NOT
        # be treated as dead — restarting an activating unit SIGTERMs a healthy
        # startup and causes a death spiral (status=15/TERM on client request).
        return st in ("active", "activating")
    except Exception:
        return False


def _is_failed(spec: dict) -> bool:
    """True only when the unit is in a genuinely failed state (not just
    inactive between batch runs, not activating). Restarting non-failed
    units murders healthy processes."""
    svc = spec["systemd"]
    if not svc:
        return False
    target = ["incus", "exec", "empire-hub", "--", "systemctl", "is-failed", svc] if spec.get("container") \
        else ["systemctl", "is-failed", svc]
    try:
        r = subprocess.run(target, capture_output=True, text=True, timeout=10)
        return r.stdout.strip() == "failed"
    except Exception:
        return False


def _recent_log(spec: dict, mins: int = 10) -> bool:
    svc = spec["systemd"]
    if not svc:
        return True
    target = ["incus", "exec", "empire-hub", "--", "journalctl", "-u", svc,
              "--since", f"{mins} min ago", "--no-pager", "-n", "1"] if spec.get("container") \
        else ["journalctl", "-u", svc, "--since", f"{mins} min ago", "--no-pager", "-n", "1"]
    try:
        out = subprocess.run(target, capture_output=True, text=True, timeout=15)
        for line in out.stdout.splitlines():
            if line and not line.startswith("--") and "No entries" not in line:
                return True
    except Exception:
        pass
    return False


def _run_tick(spec: dict) -> dict:
    """Run a standalone agent's tick function (for script-based agents)."""
    if spec.get("script") and spec.get("tick"):
        mod, fn = spec["tick"].split(":")
        try:
            m = __import__("empire_os." + mod, fromlist=[fn])
            getattr(m, fn)()
            return {"status": "OK"}
        except Exception as e:
            return {"status": "FAIL", "error": str(e)}
    return {"status": "SKIP"}  # systemd-managed, no manual tick


def _restart(spec: dict) -> str:
    svc = spec["systemd"]
    if not svc:
        return "no-svc"
    # Use `restart` (not kill) so units with Restart=no are brought back if
    # they can start; broken units fail gracefully (err:N) instead of being
    # left permanently SIGTERM'd. Unit names are now correct (verified 2026-09-01)
    # so this no longer hits the old err:5 wrong-name failure.
    target = ["incus", "exec", "empire-hub", "--", "systemctl", "restart", svc] if spec.get("container") \
        else ["systemctl", "restart", svc]
    try:
        r = subprocess.run(target, capture_output=True, text=True, timeout=30)
        return "restarted" if r.returncode == 0 else f"err:{r.returncode}"
    except Exception as e:
        return f"err:{e}"


def _load_directive() -> dict:
    d = {"raw": "", "has_scaling": False}
    try:
        txt = Path(DIRECTIVE).read_text()
        d["raw"] = txt
        d["has_scaling"] = "SCALING" in txt.upper() or "$1B" in txt
    except Exception:
        pass
    return d


def _read_state() -> dict:
    try:
        return json.load(open(STATE))
    except Exception:
        return {}


def cycle() -> dict:
    """One supervision + dispatch cycle. Returns a report for the brain."""
    state = _read_state()
    directive = _load_directive()
    report = {"ts": datetime.now(timezone.utc).isoformat(),
              "directive_loaded": directive["has_scaling"],
              "agents": {}, "dead": [], "stale": [], "actions": []}

    for name, spec in FLEET.items():
        active = _service_active(spec)
        recent = _recent_log(spec, 15) if active else False
        if not active:
            # Only restart a unit that is genuinely FAILED — never one that is
            # merely inactive (batch/oneshot between runs) or activating.
            # Restarting healthy/starting units SIGTERMs them -> death spiral.
            if _is_failed(spec):
                res = _restart(spec)
                report["dead"].append(name)
                report["agents"][name] = {"status": "DEAD", "action": res}
                state[name] = time.time()
            else:
                # not active but not failed (e.g. oneshot between ticks) -> skip
                report["agents"][name] = {"status": "OK", "tick": "skip-not-failed"}
        elif not recent:
            # STALE but alive — alert only (long-cycle agents stay up)
            report["stale"].append(name)
            report["agents"][name] = {"status": "STALE(alive)", "action": "alert"}
        else:
            # healthy — run tick if script-based
            tick = _run_tick(spec)
            report["agents"][name] = {"status": "OK", "tick": tick.get("status")}

    # ── BRAIN DISPATCH: detect revenue gaps, fire corrective agent ──
    try:
        # Short-timeout local read; gatekeeper owns heavy writes so this won't
        # content for long (Pitfall 59). If the DB is busy, metrics are skipped
        # rather than blocking the whole cycle.
        import sqlite3
        conn = sqlite3.connect(DB, timeout=10)
        conn.execute("PRAGMA busy_timeout=10000")
        cur = conn.cursor()
        settled = cur.execute("SELECT COUNT(*) FROM si_settlements").fetchone()[0]
        leads = cur.execute("SELECT COUNT(*) FROM lane_leads").fetchone()[0]
        outreach = cur.execute("SELECT COUNT(*) FROM si_buyer_outreach").fetchone()[0]
        conn.close()
        report["metrics"] = {"settlements": settled, "lane_leads": leads, "outreach": outreach}
        # gap: lots of leads, few settlements -> push marketplace harder
        if leads > 1000 and settled == 0:
            report["actions"].append("GAP: leads flowing, $0 settled -> ensure pay-links + bsc_listener live")
        if outreach < 100:
            report["actions"].append("GAP: low outreach -> buyer_hunter cadence up")
    except Exception as e:
        report["metrics_error"] = str(e)

    # write heartbeats (brain's eyes)
    hb = {}
    if Path(HEARTBEATS).exists():
        try:
            hb = json.load(open(HEARTBEATS))
        except Exception:
            hb = {}
    for name, info in report["agents"].items():
        hb[name] = {"status": info["status"], "ts": report["ts"], "engine": FLEET[name]["engine"]}
    Path(HEARTBEATS).parent.mkdir(parents=True, exist_ok=True)
    Path(HEARTBEATS).write_text(json.dumps(hb, indent=2))
    json.dump(state, open(STATE, "w"))

    _log(f"cycle: {len(FLEET)} agents | dead={len(report['dead'])} stale={len(report['stale'])} "
         f"actions={len(report['actions'])}")
    return report


if __name__ == "__main__":
    rep = cycle()
    print(json.dumps(rep, indent=2, default=str)[:2000])
