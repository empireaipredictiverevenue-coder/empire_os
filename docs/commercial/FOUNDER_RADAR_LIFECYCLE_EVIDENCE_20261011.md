# EmpireOS — Founder Radar lifecycle evidence surface (11 October 2026)

**Canonical master checklist**: line 187, `check_efad7f3a6dd57dce`.
**Workstream:** Market Intelligence / Founder Console
**Delivery status:** TESTED FEATURE — NOT MERGED / NOT DEPLOYED.
**Feature branch:** `feature/founder-radar-lifecycle-surface-20261011`, isolated from live checkout, based on `eb338c8f`.

## Existing architecture, no duplicate system

`empire_os.founder_dashboard.build_founder_dashboard` already includes a Radar section with latest opportunity-loop research and Factory blockers. Its existing Founder Dashboard API and authentication remain in place. The missing evidence is a *source-correlated* read of `runtime/opportunity_factory/evidence_routes_latest.json` and, when available, the new same-cycle lifecycle history. There is no reason to create a second dashboard, agent, queue, database, job scheduler or API endpoint.

The feature extends the existing `opportunity_radar` JSON with `lifecycle_evidence`, reading the current canonical Evidence Router snapshot. It requires matching OBSERVE schemas and no external authority; timezone-aware loop start/end and Router generation within the same cycle; bounded row count, unique opportunity keys and stage-count/row agreement. If absent, malformed or unrelated, it returns UNKNOWN instead of plausible-looking zeros or fabricated advancement.

When history is present, the projection additionally verifies exact same Router generation, derived-only stage, no independent commercial proof, active/non-missed state, unique keys/classes/tenant scopes matching current rows and bounded new/reappeared/transition counts. Valid *derived* stage changes remain observations, not buyer acceptance, payment or revenue. Missing production history (currently the case) produces `CURRENT_ROUTER_WITHOUT_HISTORY`; new-identity and advancement counts remain null. External execution, outreach, commercial validation, payments and revenue recognition are never granted.

## Independent verification

- Source-root-compatible original Founder Dashboard tests and new negative tests: **87 passed**.
- Broader Founder Dashboard + Opportunity History/Radar + Astra/Executive + Daily Results + Buyer Capacity/Closer tests: **257 passed, zero failures**, one Starlette/anyio dependency deprecation warning.
- Exact live input dry-run against `/srv/empire_os/runtime/opportunity_radar/loop_latest.json` and `runtime/opportunity_factory/evidence_routes_latest.json`: **18** observed opportunities, all QUALIFY; Router has no history so promotion/new identities are UNKNOWN and no commercial verification is claimed. SHA256 source checksums unchanged; no model call, queue execution, production write or service restart.

## Agent-assignment and release blockers

The approved, non-consequential Hermes **implementation** job `completion-20261011-founder-radar-lifecycle-v1` was genuinely queued via the existing Execution Plane, but finished `FAILED` with `HermesControlError: OmniRoute has no healthy eligible zero-cost Hermes model candidates`. No proposal was produced. A single governed local Empire Coder fallback `completion-20261011-local-radar-guard-v1` ran in an isolated clone, returned no changed source or proposal branch; avoid repeated trial-and-error. This manually engineered isolated code increment is independent from both failed agent outcomes.

Two additional non-overlapping tasks were queued through the same existing Hermes control branch and failed for the same model-capacity condition: queue lifecycle first-party local OTEL events (line 824) and Sensor Mesh evidence to existing Opportunity Radar (line 264). These are **blocked assignments**, not implementations. No new agents, paid models or schedules may be inferred as active.

Do not mark item 187 DONE merely because these offline tests pass. Reconcile with concurrent production owners, merge only through the existing release gate, run original existing Founder API and verify actual lifecycle JSON readback. Only then consider checklist promotion. Do not change source checklist during another agent's write lease.

**Execution authority:** none. No outbound, production restarts, migrations, public pages, payment, buyer delivery or traffic activation.
