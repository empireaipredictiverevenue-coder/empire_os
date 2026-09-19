# Phase 4 Astra Observer and Outcome Calibration

Status: production OBSERVE active
Execution authority: OBSERVE only

## Purpose

Phase 4 begins by giving Astra a bounded, evidence-backed view of Phase 3F commercial outcomes without granting it commercial mutation authority.

The observer:

1. uses the production HTTPS token-authenticated observer transport; the raw observer token stays on EmpireOS and Supabase stores only its SHA-256 hash;
2. calls only the token-wrapped read RPCs for `get_commercial_outcome_feedback(p_limit)` and `get_astra_operational_evidence()`;
3. calibrates observed conversion, revenue, cost, gross profit, buyer satisfaction, repeat-purchase and negative-margin signals;
4. optionally combines that calibration with a fully explicit operational snapshot;
5. builds an OBSERVE-only Astra Operating Board: a deterministic ranked executive work queue across operations, buyer relationships/acquisition, allocation, qualification, source health and unit economics, with explicit approval flags and intelligence routes;
6. writes a local `runtime/astra/latest.json` observation artifact containing both the backward-compatible primary decision and the ranked operating board;
7. never sends outreach, changes commercial state, recognizes revenue, moves funds, or modifies production data.

## Database Authority

Required migration chain:

- `supabase/migrations/20260918123504_phase3f_outcome_feedback.sql` — canonical outcome table, recorder/recognizer roles and outcome/revenue functions;
- `supabase/migrations/20260918124631_phase3f_runtime_identities.sql` — passwordless runtime login identities used by the Phase 3F role model;
- `supabase/migrations/20260918191547_phase3f_commercial_figures.sql` — read-only commercial figures and `empire_outcome_reader` role;
- `supabase/migrations/20260918133000_phase4_astra_observer.sql` — restricted Astra observer role and feedback RPC grant;
- `supabase/migrations/20260919164500_phase4_astra_operational_evidence.sql` — canonical read-only operational-evidence projection;
- `supabase/migrations/20260919223136_phase4_astra_token_rpc_observe.sql` — production HTTPS token-authenticated read wrappers; Supabase stores only the token SHA-256 hash.

The Phase 4 observer migration stages:

- `empire_astra_observer` — NOLOGIN, NOINHERIT, non-superuser, no bypass RLS;
- `empire_astra_observer_login` — restricted login, password NULL, connection limit 5;
- statement timeout 15 seconds;
- idle-in-transaction timeout 30 seconds;
- execute permission on `get_commercial_outcome_feedback(integer)` only.

The observer role cannot record commercial outcomes, recognize revenue, or write directly to commercial tables.

Production activation completed on 2026-09-19 after explicit approval. Canonical Supabase now contains the Phase 3F outcome/revenue foundation, commercial-figures reader, restricted Astra observer role, operational-evidence RPC and token-authenticated read wrappers. The direct database-login password path was deliberately not used in production; the live observer uses HTTPS RPC with a server-held random token and a hash-only verifier in Supabase.

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

The preflight reports booleans/blockers only and never emits observer secrets. It verifies the dedicated env file exists with owner-only permissions, OBSERVE mode, either a dedicated DB DSN or the production HTTPS token-RPC transport, explicit policy bindings, and a persistent scheduler.

Production scheduling is active through the host's existing `cron` service every five minutes with `flock` protection and `scripts/run_astra_observer_cron.sh`. The root-level systemd units remain staged and compatible with the same env/script, but the remote host policy blocks `sudo`; therefore systemd installation was not required for OBSERVE activation.

## Production Activation

Explicit Phase 4 OBSERVE production approval was granted on 2026-09-19. Activation completed with:
1. forward-only Phase 3F → Phase 4 canonical Supabase migrations;
2. least-privilege feedback and operational-evidence projections;
3. token-authenticated HTTPS observer transport with no raw token stored in Supabase;
4. owner-only runtime env/token files on EmpireOS;
5. a locked five-minute cron scheduler;
6. a successful live observer cycle writing `runtime/astra/latest.json` with `side_effects=none`.

Consequential authority remains gated. Phase 4 activation does not authorize outreach, spending, payments, pricing, allocation, model-weight changes or other commercial mutation.

## Validation

Validation completed for production OBSERVE activation:
- Astra calibration/observer/preflight/token-transport Python tests;
- isolated PostgreSQL observer-role and operational-evidence permission tests;
- live canonical migration/object/permission verification;
- live HTTPS token-RPC observer cycle;
- secret-safe runtime preflight with zero blockers;
- locked cron runner verification;
- Python compile checks and `git diff --check` before commit.
