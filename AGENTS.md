# Empire OS — Codex Repository Instructions

These instructions apply to the entire repository unless a deeper `AGENTS.md` overrides them.

## Mission

Empire OS is the execution platform for Empire AI / Predictive Revenue. Treat data integrity, commercial safety, and controlled autonomy as first-class requirements.

## Source-of-truth architecture

- Supabase/Postgres is the canonical business-data store.
- `prospects` is the canonical owned prospect inventory.
- `prospect_qualifications` contains scoring and intelligence.
- `fulfilment_orders` controls commercial allocation and delivery lifecycle.
- `commercial_events` is the immutable commercial ledger.
- SQLite tables such as `lane_leads` are legacy/operational compatibility stores, not canonical prospect identity.
- Buyer capacity controls allocation/delivery, not acquisition. Valid prospects remain owned inventory even when capacity is full.

## Canonical prospect acquisition

The intended acquisition flow is:

`LeadCandidate -> prepare_candidate -> lookup_existing_prospect -> materialize_prospect -> ingest_prospect_atomic`

Relevant files include:

- `empire_os/prospect_ingest.py`
- `empire_os/crawler_runner.py`
- `empire_os/autonomous_execution_bus.py`
- `migrations/003_prospect_acquisition_ledger.sql`

Rules:

1. Never fabricate prospect identities.
2. Never create timestamp-derived `prospect_*` IDs as canonical identity.
3. Never silently fall back to SQLite when canonical Supabase acquisition fails.
4. Ambiguous identity must fail closed or require manual resolution.
5. Preserve source evidence/provenance. A source URL is not automatically a verified business website.
6. Deduplication/identity claims must remain race-safe and idempotent.

## NO-SIM production policy

Production paths must not generate synthetic, seeded, mock, placeholder, hash-proxy, or otherwise fabricated leads, businesses, damage signals, contact details, or model outputs presented as observed data.

Allowed:

- test fixtures inside tests;
- explicit dry-run metadata that does not enter production stores;
- deterministic test doubles used only by tests.

When a real external source, imagery provider, model adapter, or API is unavailable, fail closed and report the reason.

## Protected paths

Do not modify, stage, delete, move, or use as implementation source material unless the user explicitly asks:

- `recovery/`
- `toop`

`recovery/` is historical/read-only. Treat it as evidence only.

## Production safety

Do not perform any of the following without explicit human approval in the current task:

- apply database migrations to live Supabase;
- restart production services;
- enable or switch autonomous execution to live mode;
- execute queued jobs;
- send email/SMS/outreach;
- trigger fulfilment or buyer delivery;
- create invoices or settlements;
- expose, print, copy, or commit secrets/credentials.

Code may be prepared and tested for those operations, but live side effects remain human-gated.

## Current roadmap

- Phase 0: complete
- Phase 1: complete
- Phase 2: complete
- Phase 3A qualification: complete
- Phase 3B market qualification materializer: complete
- Phase 3C canonical acquisition + live buyer capacity gate: complete
- Phase 3D buyer matching + capacity allocation: complete
- Phase 3E governed outbound: implementation complete/frozen; live revenue proof gates carried forward
- Phase 3F outcome feedback + Lead Intelligence: implementation complete/frozen; production proof gates carried forward
- Phase 4 Astra operating layer: current, OBSERVE-only
- Phase 5 Organic Growth / Search Intelligence: parallel foundation

Do not broaden a Phase 4 task into consequential production authority. Phase 3 real-revenue proof remains a narrow production/commercial gate and must not block Phase 4/5 engineering.

## Phase 3C completion criteria

Phase 3C is complete only when all of the following are true:

- real `LeadCandidate` acquisition uses the canonical Supabase path;
- `/v1/leads/direct` cannot create synthetic/timestamp prospect identities or directly establish canonical identity in `lane_leads`;
- migration `003_prospect_acquisition_ledger.sql` is reviewed and ready for live application;
- focused tests and compilation pass;
- `git diff --check` passes;
- a fresh queue gate shows no executable approved work before any service restart/live smoke;
- controlled live smoke uses real source data only;
- live migration/restart/smoke are performed only after explicit human approval.

## Working style

Before editing:

1. Inspect the narrowest relevant files and callers.
2. Confirm the change fits the current roadmap phase.
3. Prefer one coherent implementation over parallel legacy/canonical write paths.

After editing:

1. Run focused tests for changed behavior.
2. Run `python -m py_compile` for changed Python modules when applicable.
3. Run `git diff --check`.
4. Review `git status --short` and the diff/stat.
5. Never use `git add .`; stage explicit intended paths only.
6. Do not stage `recovery/` or `toop`.

Use the repository virtualenv when present, typically:

```bash
.venv/bin/python -m pytest -q <focused tests>
.venv/bin/python -m py_compile <changed modules>
git diff --check
```

The full test suite has known unrelated collection failures in legacy areas; do not hide those, but do not broaden scope to repair unrelated baseline failures unless requested.

## Commits and PRs

- Keep commits scoped to one architectural change.
- State what changed, tests run, and remaining blockers.
- Do not claim a production migration, restart, live smoke, or external action occurred unless it actually did.
- Do not amend or rewrite unrelated history.

## Secrets

Runtime configuration may live in `/etc/empire_os.env` or other service-managed locations. Never print secret values. Presence checks are acceptable; value disclosure is not.

## Decision rule

When forced to choose between preserving legacy behavior and preserving canonical data integrity, preserve canonical data integrity and fail closed, then document the compatibility impact.
