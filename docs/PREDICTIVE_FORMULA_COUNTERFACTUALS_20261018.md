# EmpireOS — Predictive Revenue and Predictive Cloud Formula Enhancements

18 October 2026 | Feature-only continuation | `feature/predictive-decision-control-20261018`

## Why this was added

The existing canonical formula modules and Quant Brain were already in place.
Do not replace or parallel them. The founder directed the team to enhance
Predictive Revenue, preserve the wider Predictive Cloud mission, and make
revenue-first decisions backed by evidence rather than invented scores.

This release **extends**:
- `empire_os/predictive_revenue_formula.py`
- `empire_os/predictive_cloud_formula.py`
- `empire_os/revenue_distribution.py`
- the existing `predictive_decision_control` Founder Dashboard projection
- the existing Founder Console.

No new database, task scheduler, paid provider, commercial activation or
alternative predictive engine is introduced.

## Predictive Revenue formula bounds (new)

`revenue_formula_identification_bounds(inputs)` works with the *existing*
ten-factor funnel formula:

```text
R = D × Q × E × Ω × B × O × C × T × P × F × LTV
```

With LTV known and all factors bounded in [0, 1], the upper bound is
`LTV × product(known factors)`. If any factor is unknown the lower bound is
zero; if all factors are specified the lower and upper bounds coincide.

**These are purely mathematical partial-identification bounds**, not
confidence intervals, predictive probabilities, market sizing, financial
guidance, or actual revenue. With unknown LTV, both bounds are NULL.
An evidenced zero is correctly distinct from missing evidence.

The existing Revenue Distribution opportunity projection now includes
`canonical_prediction_identification_bounds` calculated from the *same
source-ref-filtered inputs* as its existing canonical prediction. The old
`canonical_prediction`, sorting and commercial governor behavior remain
unchanged. Missing sources stay missing.

## Predictive Revenue intervention review (new)

`review_revenue_factor_counterfactuals(inputs, interventions,
factor_evidence_refs=...)` recalculates the **canonical original formula**
for each proposed one-factor change. Algebraically:

```text
ΔR_model = LTV × (proposed_factor - baseline_factor)
           × PRODUCT(other existing factors)
ΔNet_model = ΔR_model - supplied scenario cost
```

Hypothetical factor changes are NOT observed causal improvements and proposed
costs are NOT an actual or approved budget. The model requires refs for each
baseline factor and LTV, refuses duplicate/unbounded actions, rejected
degradations, NaN/Infinity and unknown factor names. Presence of a ref does
not independently authenticate its source; callers must apply established
EmpireDB/Source Intelligence evidence verification.

One-factor counterfactuals cannot be added together without modelling
interaction terms. If another critical factor is an evidenced zero, improving
one unrelated factor does not magically create revenue. No outbound, terms,
finance or execution permission is granted.

## Predictive Cloud intervention review (new)

`review_cloud_quality_counterfactuals(...)` recomputes the already canonical
geometric-mean trust formula for hypothetical changes to Cloud factors or
residual uncertainty:

```text
CloudScore = 100 × GM(IQ, EC, SF, CC, CAUSAL, RR, GR, LR, PF, SR) × (1-U)
```

It reports only hypothetical operating-score changes, and **monetary deltas
only when every included portfolio opportunity has an available ERV**.
Operating constraints (capacity, compliance, inventory, cash, authority,
fulfilment) remain visible, never overridden by scenarios.

The legacy `cloud_adjusted_portfolio_value_cents` continues to represent
the sum over *available* opportunities for backwards compatibility. The new
`cloud_adjusted_portfolio_value_is_partial` flag marks incomplete scope;
`cloud_adjusted_full_portfolio_value_cents` is NULL whenever a complete
portfolio value is unprovable or no known opportunities exist.

The Cloud portfolio reader now requires explicit `status=AVAILABLE` to
accept an opportunity's numeric ERV; unapproved/unknown statuses cannot silently
become available. Both canonical formula modules reject NaN/Infinity/bool
values rather than propagating invalid numerical results.

## Live evidence readiness in the Founder Console

New `empire_os/predictive_formula_evidence_review.py` reads only the existing
`runtime/predictive_cloud/formula_latest.json` and
`runtime/revenue_distribution/latest.json` files. It applies schema,
OBSERVE-authority, timestamp and bounded-source checks and emits **safe
aggregated health only**. It never copies private customer opportunity rows
to the operator response or computes a new production forecast.

It exposes `decision.formula_evidence` in the existing Founder Dashboard
JSON and shows source freshness, prediction readiness, opportunity count and
missing factor counts in the existing Founder Console.

Observed in a read-only 18 October production inspection:
- The Cloud formula component exists, but its producer reports
  `prediction_ready=false`, `formula_evaluated=false`.
- Its observed blockers are `normalized_opportunity_economics_required`
  and `verified_probability_inputs_required`.
- Revenue Distribution snapshot is older than the 24-hour freshness bound;
  its candidate counts are therefore treated as unknown for current decisions.
- No formula forecast or real transaction was created.

These live observations are ephemeral and must be rechecked after any deployment.

## What these algorithms do NOT yet establish

- Independent verification of refs or causal validity of supplied scenarios.
- Sufficient, time-safe calibrated probability cohorts.
- Buyer-specific demand, signed terms, acceptance and payout.
- Measured ROI uplift attributable to model-suggested interventions.
- Realized gross profit, payment settlement or fulfilment.
- Permission to send, publish, spend, modify model weights, allocate, or ship.

The existing Economic Memory / `lead_shadow_calibration_benchmark` already
revalidates original prediction + verified outcome feedback and time-safe
baseline Brier comparisons. Reuse that established benchmark rather than
creating another learning model. No artificial forecast training or model
promotion has been introduced.

## Tests and staged release

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=. /srv/empire_os/.venv/bin/python -m pytest -q \
  tests/test_predictive_formula_evidence_review.py \
  tests/test_predictive_formula_counterfactuals.py \
  tests/test_predictive_revenue_formula.py \
  tests/test_predictive_cloud_formula.py \
  tests/test_revenue_distribution.py \
  tests/test_founder_dashboard.py

cd apps/search-command-centre
./node_modules/.bin/tsc --noEmit -p tsconfig.json
./node_modules/.bin/eslint src/app/founder/page.tsx src/lib/founder-api.ts
```

Do not overwrite other agents' canonical work or deploy without coordinating
the paired API/frontend merge, source-producer refresh and founder-login QA.
Production is unchanged by this feature worktree commit.


## Multi-factor interactions and exact Shapley scenario decomposition

A further canonical function `review_joint_revenue_counterfactual` solves
one important algebraic problem: **adding separate one-factor improvements is
generally wrong** for a multiplicative funnel.

For a two-factor example with everything else fixed and LTV 10,000:
buyer match 0.5 and terms 0.5 give baseline model value 2,500.
Raising each individually to 1.0 would add 2,500 + 2,500.
Raising both together produces 10,000, so the **joint increase is 7,500**,
including a 2,500 interaction.

Exact subset-based Shapley allocation assigns 3,750 of the modeled increase
to each changed factor in this symmetric example. For up to ten existing
funnel factors the calculation is bounded to at most 2^10 coalitions.
This is a **mathematical decomposition of a hypothetical model scenario,
not causal contribution or a verified commercial outcome**.

The function requires the full evidenced baseline and explicit target factors
and scenario costs, refuses declines/invalid inputs, never performs actions,
and does not promote hypothetical improvements into calibrated revenue or
Economic Memory. It belongs to the original canonical formula module, not
a new optimizer or autonomous execution service.


## 18 October continuation — connect formula intelligence to verified outcomes

Enhance **existing** Economic Memory → canonical outcome validator → original
prediction calibration → Quant Brier → historical time-safe baseline. No new
model-fitting pipeline, database, worker or calibration math is invented.

### Existing shadow benchmark enhanced

`empire_os/lead_shadow_calibration_benchmark.py` now returns:
- `reviewed_as_of` (evaluation clock, not a claim about producer freshness)
- `calibration_improvement_brier_absolute` = historical baseline Brier minus
  original prediction Brier
- `calibration_improvement_brier_relative` = that delta divided by the
  historical baseline Brier (NULL when baseline is zero)
- `holdout_mean_predicted_probability`, `holdout_verified_event_rate`
- `holdout_signed_probability_bias` = predicted frequency minus observed
  verified frequency.

These diagnostics remain NULL until the **same** canonical provenance-checked
and chronologically safe comparison reaches its required cohort size. Tests
confirm the metrics are descriptive, do not fit/promote weights and cannot
include outcomes that became available after the original prediction.

### Readiness bridge

New `empire_os/predictive_learning_readiness.py` reuses the existing
`evaluate_shadow_calibration` function, rather than trusting a serialized
shadow score. It returns a bounded review packet and identifies the next
commercial evidence task:
- no terminal outcomes → `OBTAIN_VERIFIED_TERMINAL_COMMERCIAL_OUTCOMES`
- outcomes lacking original prediction lineage →
  `LINK_ORIGINAL_PREDICTION_TO_VERIFIED_OUTCOME`
- too little chronological holdout → `GROW_TIME_SAFE_VERIFIED_OUTCOME_COHORT`
- sufficient revalidated holdout →
  `FOUNDER_REVIEW_CALIBRATION_VS_HISTORICAL_BASELINE`.

Only a caller with an **explicit matching tenant_id** can evaluate a populated
tenant-specific cohort. The global founder dashboard deliberately holds a
tenant-scoped Economic Memory source instead of leaking customer-level data
or inference. Its unscoped review requires the existing Economic Memory file,
schema, OBSERVE/no authority, current timestamp and a bounded regular file.

The existing `predictive_formula_evidence_review` now exposes a nested
`verified_outcome_learning` packet. The existing Founder Console presents
verified reviews, matched outcomes, time-safe sample size, conditional
performance against the baseline and a next evidence action.

The earlier formula-readiness flag remains distinct from model calibration:
the arithmetic can be technically ready while verified commercial learning
is **not**. The console does not display revenue forecasts or counterfeit
calibration values.

### Observed production checkpoint (read-only)

18 October 2026 observed canonical unscoped Economic Memory:
- 0 verified calibration reviews
- 0 matched verified outcomes
- 0 time-safe evaluation rows
- next action: verified terminal commercial outcome evidence.

That result is an **evidence gap**, not proof of commercial failure across all
unqueried tenants. No transactions, outbound, source records, models or live
production deployment were changed by this branch.

### Verification

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=. /srv/empire_os/.venv/bin/python -m pytest -q \
  tests/test_predictive_learning_readiness.py \
  tests/test_lead_shadow_calibration_benchmark.py \
  tests/test_verified_outcome_learning_continuity.py \
  tests/test_predictive_formula_evidence_review.py \
  tests/test_founder_dashboard.py
cd apps/search-command-centre
./node_modules/.bin/tsc --noEmit -p tsconfig.json
./node_modules/.bin/eslint src/app/founder/page.tsx src/lib/founder-api.ts
```

After the coordinated feature merge, independently verify the authenticated
Founder Console and current producer outputs. Do not infer readiness from
test fixtures or silently change the existing financial/outbound gates.
