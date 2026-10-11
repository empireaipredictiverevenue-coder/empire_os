# EmpireOS — Opportunity lifecycle continuity, 11 October 2026

**Original canonical master task:** `check_31726bcc8190df96`, `docs/MASTER_REMAINING_CHECKLIST.md` line 185: “Dedupe opportunity history across cycles and preserve lifecycle.”
**Delivery state:** CODE FOUNDATION TESTED, NOT PRODUCTION DEPLOYED; keep the master checkbox PENDING until production runtime and history-readback proofs.
**Base:** `8899412e`; isolated branch `feature/opportunity-history-lifecycle-20261011`.

## What was missing, and what was reused

The existing Radar rebuilds current opportunity candidates and the canonical `opportunity_evidence_router` derives DISCOVER → QUALIFY → VALIDATE → EXPERIMENT → PROVE → SCALE observations. However, `evidence_routes_latest.json` previously replaced that state every cycle. It had no bounded first-seen/last-seen history and could not distinguish new/reappearing/disappeared opportunities. In addition, a dictionary comprehension silently selected the last Radar candidate if two sources or tenants shared the same key.

**Fix inside the existing Evidence Router:** a pure `empire_os/opportunity_history.py` reconciler is invoked by `refresh_evidence_routes`; its bounded `history` object is embedded in the very same atomic `runtime/opportunity_factory/evidence_routes_latest.json` output. No new scheduler, agent, database, migration, API, provider transport or operational writer.

History stores 500-identity bounded, deterministic per-opportunity keys/classes/tenant scopes, first-seen, last-seen, observation count, missed cycles, reappearances, current research-derived stage and stage-transition counts. Missing opportunities remain **not observed**, not automatically retired or marked lost. Reappearing entries keep their first-seen identity. An actual stage regression overwrites the prior stage rather than falsely preserving a higher stage. Old route outputs lacking `history` bootstrap from their own observed state.

Bad or duplicate identities, changed tenant/class on a reused key, malformed/synthetic prior lifecycle, replay with a non-advancing timestamp, exceeding retention limits, nonboolean authority fields and unreadable previous output fail closed. A malformed history **does not overwrite** the prior artifact. Route mapping now also rejects duplicate Radar or Factory Intake keys before any lifecycle derivation or downstream planner dispatch.

**Authority boundary:** Previous or current QUALIFY/VALIDATE/PROVE labels are *research-derived observations*; no previous stage supplies new buyer intent, verified demand, commercial terms, price, delivery, payout, payment, live traffic or permission. All new history objects carry `commercial_stage_independently_verified=false` and `execution_authority=none`. No stage/payout/lifecycle facts are promoted into canonical revenue.

## Actual existing production evidence — read-only acceptance

- Snapshot inputs: `runtime/opportunity_radar/latest.json`, `runtime/opportunity_factory/intake_latest.json`, `runtime/opportunity_factory/evidence_routes_latest.json`.
- Previous router generated 2026-10-11 15:58:15 UTC with **17** opportunities.
- The feature's pure new router + history reconciliation against those exact runtime inputs recovered **17 identities**, all QUALIFY, **0 newly invented opportunities**, **0 independent commercial stage verifications**, and **0 external authority**.
- SHA256 of all three production snapshot files remained identical before/after. No runtime writer, provider call, migration or traffic change was executed.

## Tests and next gates

- Focused Radar/History/Lifecycle/Loop regression: **65 passed**.
- Broad Radar → research → Evidence Normalizer → Factory → lifecycle routing → Quant/Planner + TAM/Storm/Economic and existing Closer/Buyer regression: **304 passed**, zero failures.
- Production checkout contains substantial concurrent uncommitted work. Do not copy, reset or merge into that dirty checkout without a separate controlled integration and release review.
- Once merged by the authorised production owner, run one existing bounded `opportunity_loop` in OBSERVE and read back `history` from `evidence_routes_latest.json`; verify a second real cycle retains prior first-seen dates while new and missing identities are counted. **Only then** consider the master line 185 verified DONE.
- Keep Lead Smart call routing/ANI, landing sign-off, caller-ID, traffic and founder go-live gates independent. Nothing in history authorises outreach or monetisation.
