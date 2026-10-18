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
   it is `null`, not a fabricated zero. Pulse freshness is explicitly
   `PRESENT_FRESHNESS_UNKNOWN` because the current pulse contract does
   not expose a verified observation timestamp.
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
- Enhance the revenue-pulse producer to include a verified
  `observed_at` or `generated_at` timestamp and validate its age here.
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
