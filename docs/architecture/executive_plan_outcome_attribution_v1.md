# Executive Plan → Verified Outcome Attribution v1

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Astra Executive / Economic Memory

## Purpose
Complete the executive plan-vs-outcome feedback loop by joining department execution
episodes to verified commercial outcomes only when an explicit causal outcome link
was persisted by the executing workflow.

## Truth rule
Correlation is not attribution. Never join on entity, company, niche, timing,
product, geography, forecast, score, or generic shared evidence alone.

A department episode is causally attributable only when its terminal `result`
contains `causal_outcome_refs` and one of those refs exactly equals the verified
Cortex outcome memory `outcome_ref`.

Eligible outcome refs must use canonical commercial-outcome provenance, e.g.
`canonical:commercial_outcomes:<id>`.

## Output
Economic Memory adds:
- `plan_outcome_attribution_count`
- `plan_outcome_attributions[]`
- `unattributed_verified_outcome_count`

Each attribution includes plan_id, step_id, work_id, goal/component/action,
outcome_ref, entity_id, verified label/value, conversion outcome, evidence refs,
and `attribution_basis=explicit_causal_outcome_ref`.

## Guards
- department DONE is not itself an outcome;
- only accepted verified outcome-conditioned memory may be attributed;
- synthetic/forecast outcomes remain excluded upstream;
- same entity without explicit causal ref does not join;
- generic evidence overlap does not join;
- duplicate causal refs dedupe deterministically;
- no model-weight, accounting, commercial or execution authority.

## Live completion
Zero attributions is a valid production state when no verified commercial outcomes
exist. The engineering loop is complete when the join is implemented, tested,
materialized live and accurately reports zero rather than inventing causation.
