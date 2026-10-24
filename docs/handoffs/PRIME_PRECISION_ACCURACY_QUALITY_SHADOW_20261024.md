# PRIME — precision, accuracy and probability quality: truthful shadow diagnostics

Date: 2026-10-24.
Branch: feature/prime-precision-accuracy-quality-20261024.
Base: 78f586014 (original PRIME authenticated-outcome **review**, not deployed).
Owner: original Predictive Cloud / Quant Brain / verification and outcome owners.
Mode: OBSERVE; **no Sales, Smart CRM or finance mutations**.

## What this increment actually completes

Before this feature, the original shadow outcome gate exposed Brier score
and signed probability bias but did not distinguish classification precision
from accuracy. This feature integrates a deterministic **metrics calculation**
for genuinely paired original prediction/outcome review objects; it does
not authenticate source records, declare the model accurate, adjust model
weights or enact business/trading decisions.

New pure `empire_os/prime_prediction_quality.py`:
- Confusion matrix (TP, TN, FP, FN) using a **fixed 50% RESEARCH threshold**
  only; not the real go/no-go or bid decision threshold.
- Precision = TP / (TP + FP) or UNKNOWN if no predicted positives.
- Accuracy = (TP + TN) / N or UNKNOWN without observations.
- Recall = TP / (TP + FN), specificity = TN / (TN + FP),
  F1 = 2 TP / (2 TP + FP + FN), balanced accuracy when both classes exist.
- Majority-class accuracy baseline shows how a model can achieve 98%
  accuracy with only 50% precision; abstains when no credible comparison.
- Positive-outcome prevalence and fraction predicted positive.
- Wilson 95% **sampling interval** on precision and accuracy when defined.
  These intervals assume an appropriate Bernoulli sampling design and
  DO NOT correct for selection bias, dependence, time leakage or outcome
  provenance; they are NOT forecasts of production accuracy.
- Reuses original `quant_brain.brier_score`, `log_loss` and
  `calibration_bins`. Expected calibration error is only a coarse,
  small-sample-sensitive descriptive quantity, NEVER a calibrated model
  certificate.
- 0 outcomes returns UNKNOWN ratios (not 0%), all-negative predictions
  cannot masquerade as a high-precision positive prediction engine.
- Rejects NaN, infinity, out-of-range probabilities, float/boolean or
  out-of-range binary labels, unbounded or unpaired records.
- All source authentication, out-of-time prospective holdouts, model
  training, deployment and commercial use remain permanently FALSE
  in this isolated OBSERVE review.

Integration into existing PRIME gate:
`prime_original_outcome_calibration.review_prime_outcome_calibration`
runs the metrics only on original valid matched pre-decision prediction
and terminal outcome pairs. It reuses the exact owner-controlled
`review_verified_learning_candidate` and core Quant scoring, without
inventing a second learned or calibrated model.

`read_prime_founder_status` now optionally reports only aggregate
precision, accuracy, class-baseline and FP/FN counts on the founder
private route if a source-owning trusted service supplies an authentic
cohort. The deployed route does **not** connect a cohort itself; normally
these metrics stay null NOT_CONNECTED_NOT_A_VERIFIED_ZERO.

## Release gates (all still held)

1. Independently authenticated exact canonical order/outcome reader and
   original pre-outcome prediction journal reader (tenant-bound, consent,
   custody, chronology, payment/fulfilment checks).
2. Enough representative positive AND negative terminal outcomes across
   relevant market/time strata; minimum 30 pairs is a screening threshold
   ONLY, not statistical calibration. No resampling of duplicated orders.
3. Prospective out-of-time holdout and leakage analysis; known missing
   outcomes accounted for, careful label definition and class imbalance.
4. Independently approved decision threshold, explicit business cost of
   false positives and false negatives, controlled downside and drift.
5. Only separately authorised original owner may consider model
   adjustment; no automatic promotion, price change, live trading,
   campaign activation or revenue claim.

This is useful for both Revenue and future Trading predictive intelligence
as a metric concept, but **NO TRADING BACKTEST, STRATEGY SNIPER,
PRICE FEED, EXECUTION, OR CAPITAL HANDLING IS IMPLEMENTED HERE**. Trading
requires independent market labels, realistic spread/slippage, execution
fees, latency, walk-forward tests and capital/drawdown risk validation.
Do not market classification accuracy as profitable trading performance.

## Test command

```bash
cd /home/ubuntu/empire_worktrees/prime_precision_accuracy_quality_20261024
PYTHONPATH="$PWD:$PWD/tests" /srv/empire_os/.venv/bin/python -B -m pytest \
 -q -p no:cacheprovider \
 tests/test_prime_prediction_quality.py \
 tests/test_prime_original_outcome_calibration.py \
 tests/test_commercial_verified_learning_review.py \
 tests/test_quant_brain.py \
 tests/test_predictive_revenue_brain_bridge.py \
 tests/test_predictive_revenue_prime_status.py
```

Feature branch only; production code, EmpireDB, pgBackRest, existing
Sales/CRM agents, money and paid GPUs untouched. Original Core owner
must reconcile its concurrent root changes before any merge or release.
Rollback: discard this feature commit, with no persistent resources.
