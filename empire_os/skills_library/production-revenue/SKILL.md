---
name: production-revenue
description: Production-first operating skill for EmpireOS. Use at the start of every build/ops session until verified recurring revenue is proven.
---

# EmpireOS Production Revenue Skill

## Mission

Run EmpireOS as a real business system, not an architecture demo.

North-star loop:

Predicted GP -> Realized GP -> Prediction Error -> Better Decision -> More Realized GP

## Session start

Always inspect current live state before new feature work:

1. git status + recent log
2. Revenue Truth
3. source freshness
4. real prospect acquisition
5. enrichment/qualification
6. buyer capacity
7. outbound readiness
8. fulfilment/order state
9. BSC USDT payment state
10. outcome/revenue recognition
11. Empire Coder queue

State the single highest-value production blocker and work on it first.

## Original commercial loop

Keep this running continuously:

real source
-> quality gate
-> canonical Supabase prospect
-> provenance
-> enrichment
-> qualification
-> buyer/market matching
-> governed outreach
-> conversation/closer
-> commercial terms
-> fulfilment order
-> BSC USDT payment
-> fulfilment
-> outcome
-> recognized revenue / realized GP
-> learning

Governance must wrap this loop, not stop it.

## Data rules

- No fake/synthetic production buyers, leads, contacts, payments or outcomes.
- Synthetic data is test-fixture only and must be labeled.
- Unknown stays unknown.
- Preserve source and point-in-time provenance.
- Reject identity mismatches rather than inventing enrichment.
- Do not silently fall back to legacy SQLite.

## AI operating rule

AI must keep the system fresh.

Continuous safe loop:

OBSERVE -> REFRESH -> INGEST -> ENRICH -> SCORE -> QUEUE -> ACT WITHIN AUTHORITY -> OUTCOME -> LEARN

AI should automatically perform bounded reversible work whose evidence contract is satisfied.

Do not repeatedly ask the founder to re-approve an already-approved reversible gate.

Stop only for:
- destructive/irreversible infrastructure
- actual fund movement
- legally binding acceptance requiring founder authority
- new high-risk authority expansion

## Status language

Use exactly:
- STAGED: exists but not active
- TESTED: passed validation
- DEPLOYED: installed in production
- LIVE: processing genuine production inputs/outputs
- PROVEN: independently verified external/commercial evidence exists

Never call STAGED or TESTED work "done" in production.

## Acquisition rule

Real acquisition should normally run.

Do not keep the crawler permanently in dry-run/OBSERVE when:
- the source is real
- quality gates pass
- canonical ingest is idempotent
- provenance is preserved
- the batch is bounded

Enrichment is downstream and must remain evidence-backed.

## Revenue rule

Revenue exists only after canonical verified evidence.

A forecast, score, approved email, sent email, reply, payment request or escrow balance is not revenue.

## Engineering rule

Prefer one canonical implementation.

Before creating a new module, search for an existing one and extend it.

Use Empire Coder for parallel plans/investigation, but review all coder output before integration.

## Git rule

Never use git add .

Never touch:
- /srv/empire_os/recovery
- /srv/empire_os/toop

Stage explicit owned files only.

## End-of-session report

Always report:
- commits shipped
- tests passed
- STAGED
- TESTED
- DEPLOYED
- LIVE
- PROVEN
- current revenue truth
- current top blocker
- exact next production action
