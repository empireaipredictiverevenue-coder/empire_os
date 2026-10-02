# Predictive Calibration Board v1 — Architecture Delta

Date: 2026-10-02
Status: IMPLEMENTATION CONTRACT
Owner: Data / Quant

## Purpose
Add a read-only calibration summary over the existing `predictive_calibration`
reviews. Do not create a second forecasting or calibration engine.

## Canonical inputs
- `ForecastCalibrationReview` rows from `empire_os.predictive_calibration`.
- Optional explicitly verified cohort metrics supplied by a caller with evidence
  refs; these may include Brier score, interval coverage and drift score.

## Rules
- MAE / mean relative error may be computed only from calibration-ready reviews.
- Unsupported metrics remain `None` / UNKNOWN.
- Brier score, interval coverage and drift MUST NOT be invented from generic
  forecast rows; they are accepted only as explicitly verified metrics with
  evidence references.
- Empty/insufficient verified cohorts fail closed with blockers.
- Forecast is not actual revenue.
- Calibration evidence cannot mutate models, weights, capital, pricing,
  commercial state or Revenue Truth.

## Output
A frozen deterministic board containing:
- review_count;
- ready_review_count;
- verified_cohort_size;
- mean_absolute_error;
- mean_relative_error;
- brier_score;
- interval_coverage;
- drift_score;
- bias counts;
- blockers;
- evidence refs;
- `mode=OBSERVE`;
- all mutation/execution authority false/none.

## Files
- `empire_os/predictive_calibration_board.py`
- `tests/test_predictive_calibration_board.py`

## Completion
Tests prove supported error metrics are computed only from verified/ready rows,
unsupported metrics stay UNKNOWN, evidence is preserved, and no execution or
model-mutation authority exists.
