# Completion Engine 023 — Exact Live Proof Bridge

## Objective
Close a bounded set of pending checklist tasks with independent, current,
read-only *operational* evidence instead of creating more PLAN-only work.
Preserve the canonical master checklist and the existing closure reconciler.

## Root issue verified 2026-10-09
The completion reconciliation classified 206 remaining items as
NEEDS_LIVE_PROOF. The existing live-proof engine defined four exact rules
which matched **zero** currently pending checklist items, so no exact live
checkpoints were emitted and the closure reconciler could not automatically
move proven operational items to DONE. This is distinct from missing
commercial outcomes, which remain gated.

## Added exact pending rules
The new rules match the **literal existing** checklist item names in the
"Automate recurring intelligence" section:

- **Automatic Founder snapshot refresh**: department-cycle timer both active
  and enabled, recent Astra Executive governed snapshot with expected schema
  and zero authority, plus recent canonical completion progress snapshot.
- **Service/timer health**: department-cycle timer both active and enabled,
  recent Ops Control health report with exact schema and
  `health_domains.services_and_timers == HEALTHY`.

Each receipt timestamp must be timezone-aware, at most 20 minutes old and
no more than two minutes future-dated. Missing receipts, wrong schema,
disabled timer, stale data and degraded health block the exact checkpoint.
Identically titled pending checklist items cause refusal to match; no
arbitrary line is selected. On a failed fresh verification, the engine
invalidates only its own previously emitted line-bound automatic checkpoint.

These rules prove *the specified operational capability*, not buyer
conversations, live outbound, tenant readiness, payment, or realized
revenue. Their checkpoints do NOT autonomously alter the checklist. The
existing independent closure reconciler must also find a prior successful
VERIFY job bound to the exact current checklist line before a local
internal completion flag is eligible.

## Non-goals
No migration, new timer, external HTTP/network request, paid provider,
outbound send, funds movement, public publishing or founder approval
inference. No blanket promotion of the 206 candidates. Only these two
narrowly defined entries are within this engineering slice.

## Acceptance
1. Focused unit tests for fresh/stale/future/wrong-schema/missing receipts,
   bad timer state, duplicate checklist names and checkpoint invalidation.
2. Existing closure-reconciler tests and wider completion-control tests.
3. Main-branch regression after scoped integration.
4. Live main-worktree proof: exact rule matches, 2 current operational
   checkpoints, and independent `reconcile_completion_closure(apply=False)`
   confirming the eligible exact lines before any mutation.
5. Change the two checklist boxes only after those independent gates pass.
   Recalculate all canonical registry/checklist snapshots from source.
