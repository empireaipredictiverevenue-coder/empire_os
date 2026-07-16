#!/usr/bin/env python3
"""Empire OS — Agent Registry + Supervisor (structural cure for stub chaos).

Problems this fixes:
  - 65 agents exist but most are library stubs, never started as processes.
  - Some generate SIMULATED data (_seed_damage, synthetic_*). NO-SIM policy.
  - Nothing tracks run-state -> dead-by-morning (agents silently stop).
  - No single source of truth for what should be running.

Design:
  - agent_registry.json: declares every agent, mode (daemon|tool), sim_risk,
    enabled. Human-editable.
  - supervisor_daemon.py: launches ENABLED daemons as systemd units (survive
    reboot), health-checks, restarts, refuses sim agents unless allow_sim.
  - `python3 supervisor_daemon.py status` -> live run-state table.

Run:  python3 supervisor_daemon.py start   # launch all enabled daemons
      python3 supervisor_daemon.py status
      python3 supervisor_daemon.py stop
"""
import json, os, subprocess, sys, time
from pathlib import Path

AGENTS_DIR = Path("/root/empire_os/empire_os/agents")
REGISTRY = Path("/root/empire_os/empire_os/agent_registry.json")
SYSTEMD_DIR = Path("/etc/systemd/system")

# ── Manual classification ────────────────────────────────────────────────
# mode: daemon = persistent process (supervisor manages)
#       tool   = on-demand (called by hub/other agents, NOT a daemon)
# sim_risk: high = generates/uses synthetic data (NO-SIM gate)
# enabled: start on `supervisor start`?
REGISTRY_DATA = {
  "_meta": {"generated": "2026-07-16", "policy": "no-sim",
            "note": "Edit enabled/mode here. Daemons launched as systemd units."},
  "agents": {
    # ── REVENUE / LEAD GEN (daemons) ──
    "lead_sniper":        {"file": "lead_sniper_agent.py", "mode": "daemon",
                            "sim_risk": "low", "enabled": True,
                            "note": "Rule-based (MD). Review-only -> Supabase. VERIFIED."},
    "email_agent":        {"file": "email_agent.py", "mode": "daemon",
                            "sim_risk": "low", "enabled": True,
                            "note": "Drafts outreach, operator-approves. No auto-send."},
    "marketing_agent":    {"file": "marketing_agent.py", "mode": "daemon",
                            "sim_risk": "low", "enabled": True,
                            "note": "Reads prospects/pending, plans only."},
    "media_buyer":        {"file": "media_buyer_agent.py", "mode": "daemon",
                            "sim_risk": "low", "enabled": True,
                            "note": "Plans ppc. Must wire invoice writes."},
    "outreach_runner":    {"file": "outreach_runner.py", "mode": "daemon",
                            "sim_risk": "low", "enabled": True},
    "solana_listener":    {"file": "solana_listener_agent.py", "mode": "daemon",
                            "sim_risk": "low", "enabled": True,
                            "note": "USDC collection listener. Online 2h+."},
    # ── SATELLITE / STORM (daemons, but SIM until real source) ──
    "satellite_damage":   {"file": "satellite_damage_agent.py", "mode": "daemon",
                            "sim_risk": "high", "enabled": False,
                            "note": "USES _seed_damage (synthetic grid). DISABLED until real source."},
    "satellite_strike":   {"file": "satellite_strike_agent.py", "mode": "daemon",
                            "sim_risk": "medium", "enabled": True,
                            "note": "NWS storm cells. Null-geom crash fixed."},
    "satellite_strike_cap":{"file": "satellite_strike_cap_agent.py", "mode": "daemon",
                            "sim_risk": "medium", "enabled": True},
    # ── INFRA / SUPERVISION (daemons) ──
    "commander":          {"file": "commander_agent.py", "mode": "daemon",
                            "sim_risk": "low", "enabled": True},
    "supervisor":         {"file": "supervisor_agent.py", "mode": "daemon",
                            "sim_risk": "low", "enabled": True},
    "systems_engineer":   {"file": "systems_engineer_agent.py", "mode": "daemon",
                            "sim_risk": "low", "enabled": True},
    "idle_asset":        {"file": "idle_asset_sniper_agent.py", "mode": "daemon",
                            "sim_risk": "low", "enabled": True,
                            "note": "Waste/idle-truck/logistics detector. Rule-based, review-only -> Supabase. BUILT 2026-07-16."},
    "lead_deliverer":    {"file": "lead_deliverer_agent.py", "mode": "daemon",
                            "sim_risk": "low", "enabled": True,
                            "note": "Delivers leads to buyers (webhook+email) + invoices pay-per-lead to ppc ledger. VERIFIED 2026-07-16."},
    # ── TOOLS (on-demand, NOT daemons) ──
    "code_review":        {"file": "code_review_agent.py", "mode": "tool",
                            "sim_risk": "low", "enabled": False},
    "legal_compliance":   {"file": "legal_compliance_agent.py", "mode": "tool",
                            "sim_risk": "low", "enabled": False},
    "deep_research":      {"file": "deep_research_agent.py", "mode": "tool",
                            "sim_risk": "low", "enabled": False},
    "contractor_scraper": {"file": "contractor_scraper_agent.py", "mode": "tool",
                            "sim_risk": "low", "enabled": False},
    "b2b_scraper":        {"file": "b2b_scraper_agent.py", "mode": "tool",
                            "sim_risk": "low", "enabled": False},
    "mass_tort":          {"file": "mass_tort_agent.py", "mode": "tool",
                            "sim_risk": "low", "enabled": False},
    "predictive":         {"file": "predictive_agent.py", "mode": "tool",
                            "sim_risk": "low", "enabled": False},
    "product_research":   {"file": "product_research_agent.py", "mode": "tool",
                            "sim_risk": "high", "enabled": False,
                            "note": "synthetic_analyst dependency."},
    "synthetic_analyst":  {"file": "synthetic_analyst_agent.py", "mode": "tool",
                            "sim_risk": "high", "enabled": False,
                            "note": "SIM. Disabled under no-sim."},
    "synthetic_sim":      {"file": "synthetic_sim_agent.py", "mode": "tool",
                            "sim_risk": "high", "enabled": False,
                            "note": "SIM. Quarantined under no-sim."},
  }
}

def write_registry():
    REGISTRY.write_text(json.dumps(REGISTRY_DATA, indent=2))
    print(f"Registry written: {REGISTRY}")

def unit_name(agent):
    return f"empire-agent-{agent}"

def launch_daemon(agent, spec):
    """Launch an enabled daemon as a systemd unit (survives reboot)."""
    if spec["mode"] != "daemon" or not spec.get("enabled"):
        return
    if spec["sim_risk"] == "high" and not os.environ.get("ALLOW_SIM"):
        print(f"  SKIP {agent}: sim_risk=high (no-sim gate). Set ALLOW_SIM=1 to force.")
        return
    uname = unit_name(agent)
    venv_py = "/root/empire_os/venv/bin/python3"
    # systemd unit that runs the agent's __main__
    unit = f"""[Unit]
Description=Empire OS agent: {agent}
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/empire_os
ExecStart={venv_py} /root/empire_os/empire_os/agents/{spec['file']}
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    (SYSTEMD_DIR / f"{uname}.service").write_text(unit)
    subprocess.run(["systemctl", "daemon-reload"], check=False)
    subprocess.run(["systemctl", "enable", "--now", uname], check=False)
    print(f"  STARTED {agent} -> {uname}.service")

def cmd_start():
    write_registry()
    print("Launching enabled daemons:")
    for agent, spec in REGISTRY_DATA["agents"].items():
        launch_daemon(agent, spec)
    print("Done. `python3 supervisor_daemon.py status` to verify.")

def cmd_status():
    if not REGISTRY.exists():
        write_registry()
    reg = json.loads(REGISTRY.read_text())
    print(f"{'AGENT':22} {'MODE':8} {'ENABLED':8} {'SIM':7} {'SYSTEMD':10}")
    print("-" * 60)
    for agent, spec in reg["agents"].items():
        uname = unit_name(agent)
        active = "online" if subprocess.run(
            ["systemctl", "is-active", uname],
            capture_output=True, text=True).stdout.strip() == "active" else "-"
        print(f"{agent:22} {spec['mode']:8} {str(spec['enabled']):8} "
              f"{spec['sim_risk']:7} {active:10}")

def cmd_stop():
    for agent, spec in REGISTRY_DATA["agents"].items():
        uname = unit_name(agent)
        subprocess.run(["systemctl", "disable", "--now", uname], check=False)
    print("All empire-agent-* stopped.")

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    {"start": cmd_start, "status": cmd_status,
     "stop": cmd_stop}.get(cmd, cmd_status)()
