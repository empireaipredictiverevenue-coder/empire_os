# Empire AI Predictive Revenue — precision calibration checkpoint

19 October 2026 | Predictive Decision Control owner branch only.

## What has actually changed

The original lead_shadow_calibration_benchmark.py still owns canonical
tenant-scoped original prediction/outcome validation, prequential time
holdouts, Brier comparison, baseline, probability bias and reliability
bins. This wave adds a strictly predeclared **0.70 probability threshold**
diagnostic on the SAME previously validated temporal holdout, without
building an alternative estimator or modifying Quant Brain.

For a candidate forecast with an original probability >=0.70, the
diagnostic counts terminal verified successes, the selected sample
denominator, positive predictive value and a 95% Wilson binomial interval.
It **does not** publish a numerical precision when there are fewer than
20 selected opportunities or when the canonical minimum prior history /
time-holdout evaluation is not met.

The existing predictive_learning_readiness.py exposes only safe aggregate
results. Its global Founder reader still refuses tenant-specific snapshots,
and model promotion, customer precision claims, outbound, payment, retraining
and DB writes remain disabled.

## Important precision terminology and caveats

This quantity is *positive predictive value among linked verified
outcomes*, NOT calibration of 0.70 probabilities, and NOT precision across
all registered forecasts or the whole market. It is a descriptive
diagnostic only. Verified feedback may be non-randomly observed; unanswered,
rejected, withdrawn or not-yet-matured opportunities could be missing.
The denominator of ALL issued predictions has not been independently
reconciled with the canonical original forecast registry. Neither a
Wilson interval nor a significant Brier delta fixes sample-selection bias
or causal attribution. A 20-selected-outcome threshold merely permits an
exploratory report, not a high-confidence performance claim.

An actual probability-calibration promotion additionally requires:
- Independent authenticated and tenant-safe immutable prediction registration
  *before* a future outcome.
- Complete opportunity/forecast universe and negative-label maturity audit.
- Sufficiently broad consecutive holdouts by market, time, product and
  geography, with deduplication.
- Brier and log loss relative to strictly historical baseline, probability
  reliability plots, intercept/slope and probability drift analysis.
- Uncertainty intervals and promotion rules defined BEFORE examining
  holdout labels; independent owner review and explicit release approval.
- Tracked real revenue, cost, fulfilment and time-to-revenue after
  verified first-party commercial events.

No feature in the geographic/material ontology, public forum observations or
source catalogue is allowed to act as a commercial success label or an
estimated buyer conversion probability.

## Original live evidence at this checkpoint

Read-only inspection of canonical production Economic Memory snapshot:
- empire.economic_memory.v1, OBSERVE, no execution authority.
- Original prediction/outcome calibration rows: **0**.
- Verified linked learning feedback rows: **0**.
- No promoted learning.

Therefore **no real precision or calibration improvement can be established
from this path as of this checkpoint**. Built and tested in isolated branch;
NOT a public site, model, canonical DB or live service release.

## Next path to genuine customer precision

1. Get one real signed buyer/offer/price/route/fulfilment requirement from
   existing CRM, with approved tenant scope and buyer-capacity owners.
2. Register original prospective probability and full source inputs under
   existing authenticated original-conversion-registry boundaries; do not
   invoke production writer without separate migration and role approval.
3. Record observed terminal outcomes and censored/expired opportunity status
   so selection bias can be measured.
4. After a predeclared minimum longitudinal cohort, review the Brier, baseline,
   fixed-threshold precision and uncertainty before considering any
   model recalibration, without self-promotion.

**Execution state:** tests only; no live activation, funding, outbound,
API billing, external source fetch or source publication.
