# Empire Cortex Swarm — GUARD RAILS (shared)

These rails apply to ALL four Cortex agents (Scanner, Judge, Architect, Bridge)
and the `empire-cortex-swarm.service` that runs them. Violating them is a
regression. The loop_closure_watchdog + QC agent enforce them.

## 1. NO FABRICATED REVENUE / WALLET CLAIMS
The original French "Empire Cortex" session claimed "$121/hr → YOUR WALLET" and
"$183M". Those were PITCH FICTION, never real code or money. Agents MUST NOT:
- emit "$X/hr", "wallet gets it all", or any payout-to-wallet language
- report revenue that isn't in the DB (0 charges = $0 collected, period)
- describe the French session as deployed fact

## 2. REAL DATA ONLY
- Scanner counts only what is in `si_buyer_outreach`. No invented prospects.
- Judge scores only via REAL OpenRouter LLM. Mock = flagged `reliable:false`.
- Architect persists only to `cortex_blueprints`. No other table touched.

## 3. READ-ONLY / WRITE-SCOPE
- Scanner: SELECT only on si_buyer_outreach. Zero writes.
- Judge: no DB writes at all.
- Architect: INSERT only into cortex_blueprints (CREATE IF NOT EXISTS).
- Bridge: no DB writes; POST only to empire-hub:8080/queue/architect.

## 4. NEVER CRASH THE SWARM
- Every agent loop wraps work in try/except and sleeps on error.
- A dead LLM key, missing DB, or failed POST = log + continue, NOT exit().
- systemd Restart=always is the backstop; the swarm must also self-contain.

## 5. NO OFF-BOX EGRESS (except deliberate)
- Patterns/scores/blueprints stay in-container.
- Only intentional egress: Bridge POST to empire-hub:8080/queue/architect,
  and the swarm's normal outbound LLM call to OpenRouter.

## 6. SELF-HEAL HOOKS
- loop_closure_watchdog.cortex_health() checks unit active + blueprint growth.
- Stall (active but 0 new blueprint in window) => auto-restart swarm.
- QC agent includes empire-cortex-swarm.service in its unit-active probe.

## 7. ROLES (who owns what)
- Scanner (Eyes): raw pattern extraction.
- Judge (Brain): AI quality scoring + approval gate.
- Architect (Creator): exact-copy blueprint generation + persistence.
- Bridge (Network): inter-agent messaging + hub truth sync.
- cortex_engine (separate timer): 4-pillar predictive intelligence + feeds north-mini.
