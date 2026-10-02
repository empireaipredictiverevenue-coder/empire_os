# Prediction → Action → Verified Outcome Calibration v1

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Quant / Economic Memory / Astra

## Purpose
Complete the calibration join from an evidence-backed Quant prediction, through a
real recorded action, to a verified commercial outcome without inferring any
missing link.

## Chain

```text
Opportunity Quant Review AVAILABLE decision packet
  -> stable content-addressed prediction_ref
  -> downstream real action explicitly persists prediction_ref
  -> same action explicitly persists causal_outcome_refs after outcome evidence exists
  -> Economic Memory exact-joins prediction_ref + explicit causal outcome ref
  -> calibration record
```

## Prediction reference
An AVAILABLE Quant review row receives a deterministic `prediction_ref` derived
from the opportunity key and the decision packet's evidence-bearing content.
UNAVAILABLE packets have `prediction_ref=null` because missing-input reviews are
not predictions.

The reference is lineage, not an outcome and not revenue truth.

## Action requirement
No action is invented. A department execution episode is calibration-eligible only
when its terminal DONE result explicitly contains:
- `prediction_ref`
- `causal_outcome_refs`

The prediction ref must exactly match a current canonical Quant prediction record.
The outcome ref must exactly match an accepted verified Economic Memory outcome.

Entity, niche, timing, geography, product, score similarity, evidence overlap or
shared opportunity alone are insufficient.

## Calibration output
Economic Memory adds:
- `prediction_action_outcome_calibration_count`
- `prediction_action_outcome_calibrations[]`

Each row contains prediction_ref, opportunity_key, Quant decision packet summary,
plan/step/work action identity, verified outcome ref/label, evidence refs and
`calibration_basis=explicit_prediction_and_causal_outcome_refs`.

No model weights are changed automatically. Calibration remains OBSERVE-only and
feeds later governed model review.

## Production truth
Zero calibration rows is valid while no verified commercial outcomes exist. The
engineering join is complete when lineage is implemented/tested/materialized and
zero remains zero rather than being backfilled by heuristic correlation.
