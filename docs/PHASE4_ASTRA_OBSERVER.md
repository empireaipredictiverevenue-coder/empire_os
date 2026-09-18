# Phase 4 Astra Observer and Outcome Calibration

Status: local implementation; production activation gated
Execution authority: OBSERVE only

## Purpose

Phase 4 begins by giving Astra a bounded, evidence-backed view of Phase 3F commercial outcomes without granting it commercial mutation authority.

The observer:

1. connects with the dedicated `empire_astra_observer` database role;
2. calls only `get_commercial_outcome_feedback(p_limit)`;
3. calibrates observed conversion, revenue, cost, gross profit, buyer satisfaction, repeat-purchase and negative-margin signals;
4. optionally combines that calibration with a fully explicit operational snapshot;
5. writes a local `runtime/astra/latest.json` observation artifact;
6. never sends outreach, changes commercial state, recognizes revenue, moves funds, or modifies production data.

## Database Authority

Migration:

`supabase/migrations/20260918133000_phase4_astra_observer.sql`

It stages:

- `empire_astra_observer` — NOLOGIN, NOINHERIT, non-superuser, no bypass RLS;
- `empire_astra_observer_login` — restricted login, password NULL, connection limit 5;
- statement timeout 15 seconds;
- idle-in-transaction timeout 30 seconds;
- execute permission on `get_commercial_outcome_feedback(integer)` only.

The observer role cannot record commercial outcomes, recognize revenue, or write directly to commercial tables.

The migration has not been applied to canonical Supabase and no production password has been provisioned.

## Calibration

`empire_os/astra_feedback.py` consumes only Phase 3F projection fields.

Default readiness floor:

- at least 20 real outcome rows;
- at least 5 real conversions.

Before both thresholds are met, calibration remains explicitly not ready. No model weights or scoring thresholds are changed automatically.

Current metrics:
- sample size;
- converted orders;
- actual revenue cents;
- actual cost cents;
- gross profit cents;
- conversion rate;
- gross margin rate;
- average buyer satisfaction;
- negative-margin orders;
- repeat-purchase orders.

Missing buyer-history observations remain `None`; they are not converted to fabricated false/zero evidence.

Verified negative-margin outcomes may elevate a `unit_economics / review_negative_margin` recommendation. This is review-only: Astra does not automatically change prices, budgets, model weights, offers, or commercial state. Calibration readiness never auto-retunes the system.

## Operational Snapshot Gate

The outcome projection does not contain all operational signals required by `AstraSnapshot` (buyer capacity, reply backlog, owned inventory, source health, etc.).

Therefore:
- if no operational snapshot is supplied, the worker returns `decision.available=false` with `operational_snapshot_missing`;
- an explicit snapshot must provide every current `AstraSnapshot` field;
- partial snapshots are rejected rather than filled with default zero/false values;
- the snapshot execution mode must remain `observe` or `dry_run`;
- the worker itself accepts `EMPIRE_ASTRA_MODE=OBSERVE` only.

## Runtime

CLI:

`scripts/astra_observer.py`

Environment template:

`config/astra_observer.env.example`

Default local artifact:

`/srv/empire_os/runtime/astra/latest.json`

The write is atomic (`.tmp` then replace).

Systemd packaging is staged as:
- `empire-astra-observer.service`
- `empire-astra-observer.timer`

The service is not installed or enabled. It runs as `ubuntu`, uses `ProtectSystem=strict`, and only needs the repository runtime area writable for the local observation artifact.

## Production Gates

Before activation, Phil must explicitly approve:
1. applying the Phase 4 observer migration to canonical Supabase;
2. provisioning the dedicated observer login password/DSN;
3. installing/enabling the systemd service/timer.

Those actions are deliberately outside the local implementation batch.

## Validation

Required before commit:
- Astra calibration unit tests;
- observer worker unit tests with fake transport;
- outcome role transport tests;
- isolated PostgreSQL observer-role permission test;
- Python compile checks;
- `git diff --check`;
- no canonical Supabase contact.
