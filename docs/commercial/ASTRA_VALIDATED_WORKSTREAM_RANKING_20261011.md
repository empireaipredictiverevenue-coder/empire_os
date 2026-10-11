# EmpireOS — Astra validated-opportunity workstream ranking, 11 October 2026

**Canonical checklist:** `docs/MASTER_REMAINING_CHECKLIST.md`, line 180, `check_b03f33b0a6848a3a`, “Feed validated candidates into Astra workstream ranking.”
**Implementation:** isolated branch `feature/astra-validated-workstream-ranking-20261011`, based on previous verified feature `2b0b9544`.
**Status:** offline engineering candidate; do not mark checklist DONE until approved integration and production readback.

## What production truth showed

- The current read-only router snapshot has **18 opportunities**, all `QUALIFY`.
- `runtime/astra/executive_latest.json` already contains the existing eight-step goal/plan sequence and production next-best-buyer/Quant prioritisation.
- The source router has not yet incorporated history persistence from the independently verified feature branch; consequently the derived ranking must remain `MATCHING_CURRENT_HISTORY_REQUIRED` rather than silently invent validity.
- The existing Astra Executive already routes Factory blockers to the canonical capability and department owner. Another planner/runtime/scoring system would duplicate that work.

## Exact bounded enhancement

`empire_os/astra_validated_workstream_ranking.py` projects **current, evidence-derived VALIDATE/EXPERIMENT candidates** onto Astra's existing capabilities and department owners. It is imported by the existing `astra_executive.py` world-state and plan builder.

Candidate eligibility requires:
- Current, time-aware, recent (<6 hours) router snapshot, OBSERVE-only, exact schema, no external authority and bounded unique identities.
- Matching **same-cycle** router lifecycle history with active identity, identical opportunity key/class/tenant/stage, untouched derived-stage provenance and no independent buyer/payment authority.
- `validated=true` and `commercial_validation_observed=true` in the *current* lifecycle, stage VALIDATE or EXPERIMENT. These are **derived status labels**, not proof of actual buyer acceptance, payment or independent demand.
- Canonical internal-analysis/research blocker route with original exact capability, action, mode and owner from the existing Evidence Router and Astra Control Fabric; component still requires its previously defined internal authority. Unknown or commercial-observation routes cannot receive a ranking boost.
- Deterministic workstream ranking by highest derived stage, number of distinct eligible opportunities and number of existing unresolved internal blockers. These are **task-ordering attributes**, not revenue scores.

Only the relative ordering **inside the pre-existing opportunity-evidence lane** changes. Buyer next-best actions, Quant prerequisites, first-revenue goals, plan-step count limit, memory/identity scopes, founder approval gates and all component authorities are unchanged. The output is advisory and stored in the current Astra Executive world-state/snapshot; no new file writer, database schema, timer, agent or command.

## Read-only production-shaped acceptance

Using the current `/srv/empire_os` Predictive Status, Evidence Router, Next Best Action, Revenue Pulse and Quant snapshots, the patched pure `build_executive_snapshot` returned:

- 18 observed opportunities, all QUALIFY; **0 VALIDATE promotions**;
- `MATCHING_CURRENT_HISTORY_REQUIRED` because the prior history feature is not live;
- 0 ranked workstreams, no changed live execution authority;
- eight existing plan steps, buyer actions and Quant ahead of opportunity research;
- SHA256 unchanged on every input artifact, zero server file writes.

Synthetic positive regression proves a genuinely current, matching `VALIDATE` history can place its existing internal blocker ahead of generic opportunity research. Negative tests cover expired sources, missing/forged history, duplicate key, cross-tenant/class collision, forged stage, altered action, unknown capability and old-stage promotions.

## Verification and release gates

Focused tests and wider Astra/Opportunity/Closer suites must pass in the isolated checkout. This is **not** evidence that production has accepted a validated commercial opportunity.

Integration order: upstream lifecycle/history feature already committed as `2b0b9544` → current Astra ranking branch → review/rebase against concurrently owned production work → approved merge and existing OBSERVE cycle → read back actual history and ranking into Astra Console. Do not force an external action or treat source validation as buyer acceptance.

Keep the canonical task **PENDING / CODE COMPLETE NOT LIVE** until that chain is independently verified. Continue genuine first-revenue buyer dialogue and the separate Lead Smart approval/route gates.
