---
name: cortex_architect
description: Empire Cortex Architect ("The Creator") — turns Scanner patterns + Judge evaluations into "Exact Copy" campaign blueprints mapped to real niches (roofing/solar/hvac/mass-tort). Persists winner blueprints to Empire OS SQLite cortex_blueprints table (no Supabase needed). Bridge POST to empire-hub:8080/queue/architect is best-effort. Part of empire-cortex-swarm.service.
trigger:
  - "generate exact copy / architect a campaign blueprint"
  - scheduled: every 120s inside empire-cortex-swarm.service
---

# SKILL: cortex_architect

## What it does
`generate_exact_copy(patterns, evaluation)` -> dict:
```
{
  "blueprint_id": "bp_<ts>",
  "architect_analysis": {winner_blueprints, total_winners},
  "generated_campaigns": [...],     # 4 audiences x winners
  "total_campaigns": int,
  "status": "success"
}
```
Side effect: INSERTs one row into `cortex_blueprints`.

## How to run (in-container)
```bash
incus exec empire-hub -- bash -c '
  export EMPIRE_DB=/root/empire_os/empire_os.db
  cd /root/agentic_revenue
  /root/venv/bin/python3 -c "
    import scanner.main as S, judge.main as J, architect.main as A
    p=S.EmpireCortexScannerAgent().scan()
    e=J.EmpireCortexJudgeAgent().evaluate_with_ai(p)
    print(A.ExactCopyArchitectAgent().generate_exact_copy(p,e))"'
```

## Verify persistence
```bash
incus exec empire-hub -- bash -c '
  /root/venv/bin/python3 -c "import sqlite3;c=sqlite3.connect(\"/root/empire_os/empire_os.db\");
  print(\"cortex_blueprints:\",c.execute(\"SELECT COUNT(*) FROM cortex_blueprints\").fetchone()[0])"'
```

## Guard rails
- Write ONLY to cortex_blueprints. Never touch other tables.
- Bridge POST failure = warning, continue.
- DB missing => skip persist, return result.
- No off-box egress of generated copy.
