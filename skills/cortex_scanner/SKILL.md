---
name: cortex_scanner
description: Empire Cortex Scanner ("The Eyes") — mines the live si_buyer_outreach prospect store (29,731 rows) for raw winning patterns (niche distribution, geo concentration, valid-email reach, keyword signals) and feeds the Judge. Read-only, real data only. Part of empire-cortex-swarm.service.
trigger:
  - "run the cortex scanner / what patterns are we seeing"
  - scheduled: every 60s inside empire-cortex-swarm.service
---

# SKILL: cortex_scanner

## What it does
Scans `si_buyer_outreach` and returns a patterns dict:
```
{
  "total_prospects": int,
  "valid_email_prospects": int,
  "niche_distribution": {niche: count},   # real column
  "geo_distribution": {metro: count},      # real column
  "quality_indicators": {...},
  "competitor_data": [...]                 # derived signal rows
}
```

## How to run (in-container)
```bash
incus exec empire-hub -- bash -c '
  export EMPIRE_DB=/root/empire_os/empire_os.db
  cd /root/agentic_revenue
  /root/venv/bin/python3 -c "import scanner.main as S; print(S.EmpireCortexScannerAgent().scan())"'
```

## Output contract
- `niche` and `metro` come from REAL columns. Do not invent niches.
- `valid_email_prospects` = rows where email LIKE '%@%' AND domain not sentry/generic.
- Writes snapshot to swarm `_LATEST['scanner']` for Judge + Architect.

## Guard rails
- Read-only SELECT. No writes to si_buyer_outreach.
- No off-box egress.
- DB missing → sleep, don't crash swarm.
- No fabricated revenue/wallet claims (that was the French pitch fiction).
