---
name: cortex_engine
description: Empire Cortex — predictive revenue intelligence (the 4-pillar engine from north-mini's 90-day plan). Runs predictive.py (revenue/market-gap/leak/waste) on live DB, omega_os qualification pass, asi self-improvement, recurrence guard (units + hub health), writes cortex_report.json + feeds north-mini. Durable via empire-cortex-engine.timer (every 15 min, container).
trigger:
  - "run the cortex / predictive revenue intelligence"
  - "what is the empire cortex doing"
  - scheduled: every 15 min via empire-cortex-engine.timer (container)
---

# SKILL: cortex_engine

## What it does
Single intelligence layer for Empire OS. Every 15 min, inside the container:
1. pillar_revenue — predictive.py.predict_revenue on live lanes/subs/deals.
2. pillar_leaks — uncollected $ (crm_deals awaiting), 0 charges/settlements.
3. pillar_waste — empty lanes, idle agents.
4. pillar_market_gaps — top demand niches from si_buyer_outreach.
5. omega_pass — qualify_prospect on unscored prospects (batch 25).
6. asi_pass — reflect on north_mini_actions.jsonl (self-improvement).
7. recurrence_guard — empire-* units + hub /health; Telegram MONEY_ONLY if degraded.
Writes /root/feedback/cortex_report.json + /root/g-brain/system/cortex_snapshot.json.

## When to run
- Auto: empire-cortex-engine.timer (every 15 min, container).
- Manual: `python3 /root/empire_os/empire_os/agents/cortex_engine.py --once` (container).

## Steps (build-from-plan)
1. Load .env (secrets: Telegram token, vault, DB path).
2. Open live DB (no incus shell-out — runs in-container).
3. Compute 4 pillars via empire_os.predictive (real schema: lanes,
   si_subscription, crm_deals, si_buyer_outreach).
4. omega_pass: qualify_prospect("sqlite", pid) on score IS NULL rows.
5. asi_pass: ASILayer.reflect(north_mini_actions).
6. recurrence_guard: systemctl list-units + hub /health.
7. Write cortex_report.json + cortex_snapshot.json. Alert if degraded.

## Verification
- `--once` prints: guard status, uncollected $, omega_scored.
- Check: `cat /root/feedback/cortex_report.json` (4 pillars populated).
- Check: `cat /root/g-brain/system/cortex_snapshot.json` (north-mini feed).
- `systemctl is-active empire-cortex-engine.timer` → active.

## Pitfalls
- predictive.generate_daily_report() is BROKEN (shells out to `incus`, assumes
  host). Do NOT use it — cortex_engine computes pillars directly instead.
- Runs IN container. Do not run on host (DB + hub not there).
- projected_new_mrr=0 is CORRECT when funnel_velocity=0 (no claimed/settled).
  That IS the leak the cortex is meant to surface — do not "fix" it to inflate.
- omega qualify_prospect signature: qualify_prospect(backend, prospect_id,
  tort_key=None). For sqlite backend pass prospect_id = row's prospect_id.
- recurrence_guard relies on `systemctl` in container — empire-* units must be
  named empire-* (they are).
