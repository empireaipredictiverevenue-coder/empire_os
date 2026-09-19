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
5. builds an OBSERVE-only Astra Operating Board: a deterministic ranked executive work queue across operations, buyer relationships/acquisition, allocation, qualification, source health and unit economics, with explicit approval flags and intelligence routes;
6. writes a local `runtime/astra/latest.json` observation artifact containing both the backward-compatible primary decision and the ranked operating board;
7. never sends outreach, changes commercial state, recognizes revenue, moves funds, or modifies production data.

## Database Authority

Required migration chain:

- `supabase/migrations/20260918123504_phase3f_outcome_feedback.sql` — creates the canonical outcome-feedback projection consumed by Astra;
- `supabase/migrations/20260918133000_phase4_astra_observer.sql` — creates the restricted Astra observer roles and feedback RPC grant;
- `supabase/migrations/20260919164500_phase4_astra_operational_evidence.sql` — creates the canonical read-only operational-evidence projection and grants it to the observer role.

The Phase 4 observer migration stages:

- `empire_astra_observer` — NOLOGIN, NOINHERIT, non-superuser, no bypass RLS;
- `empire_astra_observer_login` — restricted login, password NULL, connection limit 5;
- statement timeout 15 seconds;
- idle-in-transaction timeout 30 seconds;
- execute permission on `get_commercial_outcome_feedback(integer)` only.

The observer role cannot record commercial outcomes, recognize revenue, or write directly to commercial tables.

The required Phase 3F/4 migration chain has not been applied to canonical Supabase and no production observer password has been provisioned. Read-only verification on 2026-09-19 confirmed the canonical project does not yet contain the Astra observer roles or either Astra feedback/operational-evidence RPC.

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

## Astra Operating Board V1

`build_operating_board()` expands the single-decision bootstrap into a ranked OBSERVE-only work queue while preserving `decide()` / `decide_with_outcomes()` compatibility through the board's primary item. Priority remains deterministic: governance and verified negative-margin review outrank failed governed work, buyer replies, buyer acquisition, allocation, qualification, source repair and new acquisition. Items retain their existing `side_effect_approval_required` flags; the board itself has `side_effects=none` and creates no execution authority.

## Operational Snapshot Gate

The outcome projection does not contain all operational signals required by `AstraSnapshot` (buyer capacity, reply backlog, owned inventory, source health, etc.).

Therefore:
- canonical operational evidence is now preferred through `get_astra_operational_evidence()`;
- the read-only projection covers reply backlog, failed GTM jobs, identity-linked unallocated inventory, qualification-ready unallocated inventory, active buyer capacity and pending buyer candidates;
- premium-AI budget, outbound-domain verification and source-health remain explicit verified runtime bindings until canonical stores exist for them;
- any missing evidence keeps `decision.available=false` with the missing fields listed;
- an explicit full `AstraSnapshot` JSON remains a compatibility override only;
- partial snapshots are rejected rather than filled with default zero/false values;
- the snapshot execution mode remains OBSERVE and the worker accepts `EMPIRE_ASTRA_MODE=OBSERVE` only.

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

Secret-safe runtime preflight:

`/srv/empire_os/.venv/bin/python scripts/astra_activation_preflight.py`

The preflight reports booleans/blockers only and never emits the observer DSN. It verifies the dedicated env file exists with owner-only permissions, OBSERVE mode, observer DSN and explicit policy bindings, plus service/timer installation and timer enablement.

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
