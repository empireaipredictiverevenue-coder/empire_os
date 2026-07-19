---
name: cortex_swarm
description: The Empire Cortex Agent Swarm — four cooperating agents (Scanner/Judge/Architect/Bridge) that mine live prospects, AI-score ad patterns, and mint Exact-Copy blueprints. Runs as one durable systemd unit (empire-cortex-swarm.service, Restart=always) with self-heal via loop_closure_watchdog.cortex_health(). Companion to cortex_engine (4-pillar predictive intelligence).
trigger:
  - "run the empire cortex swarm / scanner judge architect"
  - "what is the cortex swarm doing"
  - scheduled: continuous loop inside empire-cortex-swarm.service
---

# SKILL: cortex_swarm

## Topology
```
Scanner (Eyes) --patterns--> Judge (Brain) --score--> Architect (Creator) --blueprint--> cortex_blueprints + Bridge --> hub:8080/queue/architect
        |                        |                         |
        +------------------------+-------------------------+--> _LATEST (in-process shared truth)
```
All four run as threads inside `empire-cortex-swarm.service` (run_swarm.sh).

## Files (host -> container)
- /apis/agentic_revenue/{scanner,judge,architect,bridge}/main.py  (HOST source of truth)
- /root/agentic_revenue/{scanner,judge,architect,bridge}/main.py (pushed to container)
- /root/agentic_revenue/swarm.py  (orchestrator)
- /root/agentic_revenue/run_swarm.sh (sources /root/empire_os/.env then launches)

## How to restart / verify
```bash
# restart
incus exec empire-hub -- systemctl restart empire-cortex-swarm.service
# status
incus exec empire-hub -- systemctl is-active empire-cortex-swarm.service
# tail logs
incus exec empire-hub -- journalctl -u empire-cortex-swarm.service -n 20
# blueprint count
incus exec empire-hub -- /root/venv/bin/python3 -c "import sqlite3;print(sqlite3.connect('/root/empire_os/empire_os.db').execute('SELECT COUNT(*) FROM cortex_blueprints').fetchone()[0])"
```

## Self-heal (already wired)
- loop_closure_watchdog.py: cortex_health() + self_heal() restarts the swarm if
  unit dead OR active-but-no-new-blueprint (stall). Added to unit-restart list.
- QC agent probes empire-cortex-swarm.service as active.

## Guard rails (MUST READ)
See cortex_swarm_GUARD_RAILS.md in this skills dir. Summary:
- NO fabricated "$/hr wallet" claims (French pitch was fiction).
- Real LLM only; mock flagged unreliable.
- Scanner read-only; Architect writes only cortex_blueprints.
- Never crash the swarm; try/except + sleep on error.
- No off-box egress except hub queue POST + OpenRouter LLM call.

## Per-agent skills
- cortex_scanner  — persona.md + SKILL.md
- cortex_judge    — persona.md + SKILL.md
- cortex_architect— persona.md + SKILL.md
- cortex_bridge   — persona.md + SKILL.md
