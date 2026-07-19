---
name: cortex_bridge
description: Empire Cortex Inter-Agent Bridge ("The Network") — routes Scanner→Judge→Architect messages via in-process _LATEST handoff and best-effort POSTs Architect results to empire-hub:8080/queue/architect. Connective tissue only; no scoring/generation. Part of empire-cortex-swarm.service.
trigger:
  - "check the cortex bridge / agent messaging"
  - scheduled: runs as daemon thread inside empire-cortex-swarm.service
---

# SKILL: cortex_bridge

## What it does
- `main()` starts background processor threads + serves the in-process handoff.
- The swarm's `_LATEST` dict is the live shared truth: Scanner writes
  `_LATEST['scanner']`, Judge writes `_LATEST['evaluation']`, Architect reads both.
- Optionally POSTs Architect output to `http://empire-hub:8080/queue/architect`.

## How to run
The bridge runs inside the swarm process (run_swarm.sh). It is NOT run standalone
in production. For a standalone check:
```bash
incus exec empire-hub -- bash -c 'cd /root/agentic_revenue && /root/venv/bin/python3 -c "import bridge.inter_agent_bridge as B; print(B.main.__doc__)"'
```

## Guard rails
- Cross-agent data stays in-container except the deliberate hub POST.
- POST failure => log + continue, never crash.
- No credentials/PII in messages beyond what the DB already holds.
