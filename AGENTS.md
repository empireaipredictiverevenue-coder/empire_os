## PRODUCTION OVERRIDE — 2026-09-28

This section overrides any conflicting historical wording below.

### Founder directive — 2026-10-19: One task, one implementation owner

Canonical directive: `directive_0f97bbfe46434b1ab0b744d39c09226a`
(`Single-Owner Agent Scope Enforcement`). This policy applies to EmpireOS,
ASTRA, Codex, Hermes, Pi and independently operated implementation agents.
It **does not** give any agent authority to reassign another agent's work.

1. **Check ownership before edits or recommendations to take over work.**
   Identify the exact founder-assigned objective, current department and owner,
   permitted paths, and handoff interface. Inspect current production HEAD,
   relevant worktrees and dirty paths, recent commits, existing agent work and
   execution leases. A worktree's existence alone does not establish a live
   operator, and an empty lease list does **not** prove a domain is unowned.
2. **Stay in your assignment.** Work only on the identified task and its
   allowed paths; never opportunistically implement adjacent departments,
   change another owner's files, create parallel modules/agents, or take over
   remaining work just because an associated gap was discovered. Another
   agent's related progress is a reason to reconcile, not a new assignment.
3. **Conflicts fail closed.** If the owner is unknown, an active owner already
   owns the change, proposed paths are shared/dirty, or responsibilities
   conflict, do **not** edit, merge, deploy, queue outbound, or auto-reassign.
   Give the existing owner a factual **read-only handoff** with evidence and
   changed requirements. Founder reassignment is required before takeover.
4. **Use existing safeguards, not new governance infrastructure.** Where an
   executing builder is integrated with the Agent & Tool Execution Plane,
   supply narrowly scoped allowed paths and acquire its existing exclusive
   domain/path mutation lease before writing. Leases are temporary collision
   controls, **not** persistent ownership assignments or grants of production
   authority. Independently operated sessions must respect the same scope
   even when they cannot acquire a shared lease.
5. **Finish then stop:** implement only the assigned change, run focused
   verification, commit only owned files, report tested versus live outcomes,
   pass any cross-owner dependency to its owner, and **stop**. Do not invent
   the next assignment or reopen completed founder/buyer decisions.

This instruction is a shared operating policy, not evidence that every agent
runtime enforces it. Automated end-to-end coverage must be verified separately
by the existing execution-plane owner; do not claim it is active everywhere.
Existing restrictions on production writes, live outreach, finances, secrets
and protected paths remain in force.

- Blueprint V6 and the verified live runtime are production truth.
- EmpireDB PostgreSQL is the canonical production business database.
- `EMPIRE_DATA_BACKEND=empiredb`.
- Supabase is legacy/recovery evidence only and must not become canonical again.
- Unknown stays unknown. Never fabricate production data or evidence.
- Founder revenue-first operating order (2026-10-17): read the current
  `docs/MASTER_REMAINING_CHECKLIST.md` checkpoint and the Founder Priority
  Override in `docs/FOUNDER_DIRECTIVE_OS.md` before choosing new work.
  **Finish, integrate, test and commit owned pending changes before expanding**;
  remove optional internal bureaucracy, not actual legal/security safeguards.
  For the dirty main branch, reconcile each owner-specific feature and commit
  only validated paths. Do not `git add .`, stage generated `.next` archives,
  merge unrelated agent work, or erase unstaged edits. If the Codex sandbox
  cannot write `.git`, hand the verified explicit-path commit to the existing
  Git-capable operator instead of claiming the commit succeeded.
- Founder DO NOT PURSUE (2026-10-10): callvox.pro and partners@callvox.pro.
  The founder rejected this network after SMTP 550 5.1.1 and credibility concerns.
  Do not research, qualify, select, recommend, queue for outreach, email, call,
  submit forms, or automatically reconsider this entity. Historical records
  remain for audit only. The policy is in
  config/buyer_network_manual_review_holds.json; only a new explicit founder
  instruction may reverse the restriction.
- Default autonomous authority remains OBSERVE.
- Existing approved bounded revenue schedules may continue operating.
- New authority expansion remains founder-gated.
- Generic `empiredb_app` must never inherit sensitive sender, payment,
  commercial-approval or revenue-recognition authority.
- Dedicated runtime roles must remain least privilege.
- Migration 018 is HELD and must not be changed or applied without explicit
  founder approval.

Migration 018:

`migrations/empiredb/018_tenant_context_foundation.sql`

Required SHA256:

`e7edcfe1d0f94c3898437e68db0714557370b7b86f9b21ee76cc04be60bc3c21`

Engineering sequence:

DIAGRAM → ARCHITECTURE CONTRACT / DELTA → WORKER ASSIGNMENT → IMPLEMENT
→ INDEPENDENT VERIFY → LIVE VERIFY → CHECKLIST DONE

Recovery sequence:

OBSERVE → DIAGNOSE → CLASSIFY → PLAN → ACT → VERIFY → RECORD → RESUME

Never use `git add .`.
Never blindly `git reset --hard` or `git clean -fd`.
Do not mutate `recovery/` or `toop/` without explicit recovery scope.

Codex, Hermes, Pi and Empire Coder are implementation workers, not business
authorities. They cannot grant themselves production authority.

---

# Empire OS — Codex Repository Instructions

These instructions apply to the entire repository unless a deeper `AGENTS.md` overrides them.

## Mission

Empire OS is the execution platform for Empire AI / Predictive Revenue. Treat data integrity, commercial safety, and controlled autonomy as first-class requirements.

## Source-of-truth architecture

- EmpireDB PostgreSQL is the canonical business-data store.
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
3. Never silently fall back to SQLite or Supabase when canonical EmpireDB acquisition fails.
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

- apply live database migrations;
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
