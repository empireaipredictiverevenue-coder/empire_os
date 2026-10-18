# EmpireOS Predictive Decision Control — isolated enhancement

Date: 2026-10-18
Branch: `feature/predictive-decision-control-20261018`
Worktree: `/home/ubuntu/empire_agents/predictive_decision_control_20261018`
State: **Feature complete for read-only review; NOT deployed to production.**

## Intent

Make Empire AI identify which commercial and operational task should be tackled next,
without building a competing database, CRM, executive, or workflow engine.

### Reuse, do not duplicate

- `empire_os.next_best_action`: factual per-entity action suggestions.
- `empire_os.revenue_command_queue`: existing canonical funnel-stage and blocker projection.
- `empire_os.executive_founder_status`: validated ASTRA/COO/Chief-of-Staff operational priorities.
- `empire_os.revenue_pulse`: separately sourced recognized revenue, not portfolio forecasts.
- `empire_os.founder_dashboard`: existing backend response.
- `apps/search-command-centre/src/app/founder/page.tsx`: existing founder UI.

New `empire_os.predictive_decision_control` is a stateless, read-only *fusion* layer.

## What is implemented

1. **Automatic departmental priority ranking:** the projection ranks factual tasks
   from commercial proximity, type of required work, and exact known blockers.
   Rankings are explicit, deterministic triage heuristics, not probabilities,
   promises of uplift, or sales forecasts.
2. **Truth-preserving source checks:** the buyer snapshot must have the known
   schema, OBSERVE mode, no outbound/payment authority, and a timezone-aware
   timestamp within six hours. Future or stale snapshots are held. Queue
   authority claims must also match the expected read-only contract.
3. **Lineage and conflicts:** each queue task must be present in the canonical
   Next-Best Action snapshot with matching entity, prospect, action and state.
   Unknown actions and contradictory actions for one business are held.
   Stable privacy-safe task IDs dedupe repeated projections.
4. **Owner and decision lanes:** `INTERNAL_PREPARATION`,
   `INTERNAL_REVIEW`, `FOUNDER_DECISION`, `GOVERNED_REVIEW`,
   `WAITING_EXTERNAL`, and `EVIDENCE_HOLD` are distinguished. An
   internal preparation candidate is NOT a dispatch permission.
5. **Observed systemic gaps:** when ASTRA's *validated* executive source
   reports missing downstream buyer capacity or failed operational observers,
   the system surfaces the specific review job automatically—even when it
   isn't in the Chief-of-Staff top-three.
6. **Revenue truth separation:** recognized revenue is shown only if the
   separate revenue-pulse observer is available, known-schema, OBSERVE,
   excludes forecasts from truth, and reconciles with the queue. Otherwise
   it is `null`, not a fabricated zero. As of 18 October, the existing
   producer supplies `generated_at`; the decision control now validates its
   age against a six-hour bound and rejects future, malformed or untrusted
   snapshots. Realised gross profit is independently labelled and also
   stays `null` unless the trusted pulse and canonical queue agree.
7. **Founder integration:** adds `predictive_decision_control` to the
   existing Founder Dashboard API response; displays top-three jobs,
   owner, source freshness, readiness, and approval requirements in the
   existing Next.js Founder Console.
8. **Fail-closed bounds:** capped candidate processing; no database write,
   email, live AI dispatch, domain mutation, financial permission, or
   infrastructure deployment. Every task has `can_execute=false` and
   the projection reports `task_dispatch_performed=false`.

## How to review (no deployment required)

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=. /srv/empire_os/.venv/bin/python \
  -m empire_os.predictive_decision_control \
  --repo-root /srv/empire_os --top 5

PYTHONPATH=. /srv/empire_os/.venv/bin/python -m pytest -q \
  tests/test_predictive_decision_control.py \
  tests/test_revenue_command_queue.py \
  tests/test_next_best_action.py \
  tests/test_founder_dashboard.py

cd apps/search-command-centre
node_modules/.bin/tsc --noEmit -p tsconfig.json
```

The isolated worktree's `node_modules` symlink, if present, references
the existing server dependency install. It is not tracked in git.

## Honest acceptance / remaining integration work

- Feature review and cherry-pick/merge into the existing mainline by the
  owning agent, after comparing with other agents' uncommitted dashboard edits.
- Apply existing authenticated API and tenant visibility checks to the final
  founder-facing deployment; this feature adds *no* new public endpoint.
- Confirm real founder login displays the new card once the backend and
  frontend versions are deployed together. No claim of live UI activation.
- The current revenue-pulse producer supplies `generated_at`, now checked
  for freshness. Continue to establish independently verified accounting
  reconciliation rather than mistaking a fresh report for a bank receipt.
- Add **separately authorised** internal dispatch via the existing execution
  bus: task ownership, idempotency, allowed read-only/internal actions,
  producer/consumer version matching, outcome receipt, cancellation, and
  human escalation. Do not use `can_prepare_internal_work` alone as a
  security decision.
- Introduce calibrated commercial prediction **only after** sufficient
  verified conversion outcomes exist; do not relabel triage ranks as
  forecasts. Economic Memory must only learn from verified outcomes.
- Do not change the standing rules: no automatic cold outbound, spending,
  customer delivery, binding commercial terms, payments or production DB
  privilege activation without their existing specific authorisations.

## Review checkpoint

Check `git status` and `git log` in the feature worktree for the exact
commit, tests and diff. The dirty canonical `/srv/empire_os` worktree was
not reset, staged, merged or overwritten as part of this isolated upgrade.


## 18 October continuation — Department Handoff bridge

Added `empire_os/predictive_decision_handoff.py`. This feature translates
**only** current, provenance-matched `INTERNAL_PREPARATION` decisions into
non-executable work-step proposals in ASTRA's established
`DepartmentWorkQueue` format. It uses the queue's deterministic work ID
function for idempotent review identity, **without constructing the queue**
or changing any file, lease, or job state. The live Gtm execution bus and
department worker have not been modified or enabled.

Safeguards:

- Snapshot freshness, provenance, source authority and task identity must agree.
- Actions and department-to-component mappings are hard allowlists.
- Auto-dispatch is always `false`, enqueuing authorisation is always `false`,
  and the proposed work step has `authority=observe`.
- It reads at most six queue-state files per proposed task and rejects
  symlinks, oversized, malformed, contradictory or duplicate states.
- Existing `ready/running/review` work is observed, never re-created;
  `blocked/failed` is escalated rather than retried; `done` is not
  mistaken for verified sales or economic outcomes.
- No match in this specific handoff plan does **not** prove no related work
  exists in other ASTRA plans. Cross-plan semantic deduplication is a
  separate remaining integration requirement.
- Existing Economic Memory already understands linked completed work and
  verified commercial feedback. No counterfeit feedback is inserted.

The existing Founder Console has a handoff section showing review packets,
already queued work and evidence holds; it does not expose an "Execute"
button because the current preview has no safe execution authority.

### Current production-evidence OBSERVE snapshot (not deployed)

From the isolated feature worktree reading `/srv/empire_os` snapshots:
`decision_status=REVIEW_READY`,
`handoff_status=REVIEW_READY`,
`candidate_count=2`,
`ready_for_review_count=2`,
`existing_work_count=0`,
`held_count=0`,
`queue_mutated=false`,
`work_dispatched=false`.

The two preview actions are `verify_decision_maker` and `research_more`.
This is not evidence those activities were actually executed, nor that any
buyer or payment became commercially verified.

### Production integration still outstanding

Merge coordinated backend/frontend versions with ASTRA's current feature
work and independently validate the running Founder Console login and
server-side visibility. Before any autonomous work submission, build a
separately governed dispatcher with supported low-risk *read-only* adapters,
cross-plan duplicate detection, owner leases, bounded budgets, current
source rechecks and signed outcome receipts. The existing worker claims
`READY` items and supports adapters with side effects: a queue entry must
never substitute for that independent execution authorisation. No current
`candidate` flag alone is an approval.


## 18 October continuation — verified buyer-capacity action bridge

The existing validated ASTRA Executive → Founder status projection now retains
the safe aggregate readiness counters previously dropped: reviewed buyers,
market-defined buyers, configured capacity and present delivery destination.
It still excludes raw buyer identity/contact details, secrets and per-buyer
commercial terms.

A small stateless helper, `empire_os/buyer_capacity_action_brief.py`,
reconciles those counts with the validated source status, rejects malformed or
contradictory state, and produces an eight-stage **read-only evidence checklist**
for Business Development. It never equates aggregate counts with one specific
paying buyer, payout authorisation, a working delivery route or actual revenue.

The existing Predictive Decision Control response and Founder Console panel now
show the source state, next missing proof, safe stage counts and next reviewing
owner. Missing revenue/GP values render as **Unknown** rather than artificial
zero. No worker/job was queued, no external contact performed and no production
service changed.

Read-only production observation from 18 October: buyer inventory 1,057;
reviewed 1; market-defined 107; positive configured capacity 121; destinations
present 485; independently verified capacity, terms, delivery and activation
aggregates all zero. **These are source aggregates, not commercially verified
buyers in any one market or corridor.** First current evidence task:
`VERIFY_CURRENT_BUYER_CAPACITY_EVIDENCE`.

Production integration remains a coordinated backend/frontend deployment after
ASTRA and other owning agents review and merge the isolated feature. This
change does not create specific buyer buy-box proof; the actual agreements,
partner identity, acceptance and economics still have to be obtained and
verified using existing CRM/revenue pathways.
