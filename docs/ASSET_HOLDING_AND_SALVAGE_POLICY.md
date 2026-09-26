# EmpireOS Asset Holding & Salvage Policy

## Purpose
Keep useful but undecided, incomplete, legacy, experimental, or not-yet-prioritized work without contaminating production or losing valuable ideas/code.

## Canonical states
Every held asset gets exactly one state:

1. **PRODUCTION**
   - Canonical and actively used.
   - Lives in normal production paths such as `empire_os/`, `apps/`, `scripts/`, `supabase/`.

2. **INCUBATE**
   - Worth building, but not yet on the active Founder priorities.
   - Keep code isolated under `incubator/` when a standalone copy is needed.
   - Must not be imported, mounted, scheduled, or exposed in production until promoted.

3. **SALVAGE_CANDIDATE**
   - Old/legacy code or files contain useful logic, data, prompts, UI ideas, schemas, or workflows.
   - Original file may stay where it is.
   - Extract only the useful pieces into canonical modules when the relevant roadmap item becomes active.

4. **REBUILD_LATER**
   - Concept is wanted, but current implementation is too obsolete or unsafe to reuse directly.
   - Preserve requirements and useful artifacts; rebuild against current Supabase/BSC/OBSERVE architecture when scheduled.

5. **REFERENCE_ONLY**
   - Useful for history, design inspiration, benchmarks, or product research.
   - Must never become a runtime dependency without a new review.

6. **REJECTED / RETIRED**
   - Superseded, unsafe, wrong architecture, fake/synthetic, wrong payment rail, or otherwise not to be revived.
   - Keep only enough history to explain the decision.

7. **FOUNDER_GATE**
   - Technically ready or valuable but requires explicit founder action because it changes authority, money, production data, contracts, public publishing, or destructive infrastructure.

## Where things go

### Production code
`empire_os/`, `apps/`, `scripts/`, `supabase/`

### Incubation code
`incubator/`
Use for clean, isolated modules we may build later but do not want wired into production yet.
Each subfolder must have a README stating:
- purpose;
- source/origin;
- current state;
- dependencies;
- why it is not production;
- promotion criteria.

### Historical/reference docs
`docs/history/`
For old plans, handoffs, prior architectures, screenshots/specs, and retired implementation notes.

### Salvage decisions / inventory
Primary registers:
- `docs/FOUNDER_CLOSURE_LEDGER_2026-09-20.md`
- `docs/LEGACY_ASSET_SALVAGE_AUDIT_2026-09-20.md`
- `docs/FOUNDER_MASTER_STATUS_2026-09-20.md`

These are the source of truth for whether something is:
PRODUCTION / INCUBATE / SALVAGE_CANDIDATE / REBUILD_LATER / REFERENCE_ONLY / REJECTED / FOUNDER_GATE.

### Runtime-generated inventories
`runtime/asset_intake/`
Machine-readable inventories and scan results only.
Do not place source-of-truth business code here.

## Protected paths
Do not use or modify these for holding/salvage:
- `/srv/empire_os/recovery/`
- `/srv/empire_os/toop`

They remain protected exactly as defined by Founder operating rules.

## Promotion rule
Nothing leaves holding/incubation because it merely looks useful.
Promotion requires:
1. roadmap owner;
2. canonical architecture target;
3. evidence/source provenance;
4. dependency/security/license review;
5. tests;
6. integration point;
7. clear production authority;
8. no conflict with current Founder Execution Lock.

## Practical rule for old files
Do **not** blindly move old files that are already in the repo.
Moving them can break imports/history.
Instead:
- register the file in the Closure Ledger;
- classify it;
- extract/rebuild useful parts when its roadmap item activates;
- retire the obsolete implementation once the canonical replacement is proven.

## Current examples
- `okf_tracker.py`: **SALVAGE_CANDIDATE / REBUILD_LATER**. Strategic OKR ideas retained; old SQLite/USDC/proxy metrics retired.
- Legacy `/v1/sweep/run`: **RETIRED implementation / REBUILD_LATER product**. Old execution route returns 410; modern Market Sweep must be rebuilt over Source Mesh + Intelligence Fabric.
- Old Revenue Pulse standalone projects: **SALVAGE_CANDIDATE / REBUILD_LATER**. Useful Command Tower concept retained; canonical Revenue Pulse V3 uses current Supabase revenue truth.
- Firecrawl core: **REFERENCE_ONLY / REJECT_FROM_RUNTIME**. Empire Web Intelligence Crawler remains canonical.
- Legacy AEO page estate: **SALVAGE_CANDIDATE** pending quality/census/recovery.
