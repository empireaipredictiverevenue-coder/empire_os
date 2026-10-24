# PRIME original-outcome calibration integration — shadow only

Date: 2026-10-24.
Branch: feature/prime-original-calibration-gate-20261024.
Base: 90eac1e89 (NWS → Universal Custody → PRIME source observatory).
Owner: original Predictive Cloud/Quant/Outcome/Finance OS. No buyer, sender,
CRM, website, finance or other agent ownership was changed.

## Scope completed

PRIME means Predictive Revenue Intelligence Matrix. Inside the existing
Predictive Cloud it combines original observed event intelligence, original
JEV evidence evaluation, deterministic scenario modelling and eventually
feedback from completed commercial outcomes.

New `empire_os/prime_original_outcome_calibration.py` is the deliberately
missing feedback-read gate:
1. Existing canonical outcome reader/Finance owner remains the ONLY source
   of authentic order/payment/fulfilment/recognized-revenue records.
2. Existing `review_verified_learning_candidate()` verifies a supplied
   feedback object, exact canonical order and genuine pre-outcome decision
   prediction by the ORIGINAL legacy contracts. These are **claims** unless
   supplied by the canonical authenticated reader/decision owner.
3. Existing `quant_brain.brier_score()` computes shadow binary-conversion
   prediction error on independently matched prediction/outcome pairs.
4. Original `build_predictive_revenue_brain_review()` accepts an OPTIONAL
   owner-supplied cohort; source observations never become labels and
   sales/CRM forecasts never become recorded payment outcomes.
5. Original aggregate-only `read_prime_founder_status()` can display just
   shadow pair count, shadow Brier score and hold status when given an
   authorised owner cohort by the existing trusted service. No new endpoint,
   credential, HTTP query parameter or tenant override has been introduced.

**PRIME does not fetch or read real orders here.** The normal deployed
Founder route does not supply the cohort, so its status stays
NOT_CONNECTED_NOT_A_VERIFIED_ZERO. No false claim of real financial
outcomes, commercially calibrated prediction probabilities, verified model
accuracy or new revenues.

## Safety gates

- Matching exact tenant UUID, order UUID, unique canonical feedback/outcome
  receipt and original prediction identity are required.
- Original predicate verifies terminal outcome status, payment, fulfilment,
  recognized revenue on wins and timestamped pre-decision model predictions
  when a prediction is supplied.
- Missing original prediction never creates a Brier score. Identical order
  or outcome references cannot be replayed for apparent larger cohorts.
- Strict input fields: no user-supplied revenue, sender flags, training grants,
  raw customer records or arbitrary CRM row patching.
- A screening threshold of 30 matched prediction/outcome pairs only marks
  enough for a first shadow aggregation review; it is **NOT** a scientific
  guarantee of meaningful calibration or promotion. Model training,
  probability calibration, priors, automatic decisions and production use
  remain disabled regardless of sample size.
- Returns aggregate sample counts, win-label count from owner-supplied
  feedback, Brier score and signed prediction bias; does not return order
  identifiers, tenant IDs, original predictions, customer contacts or
  personal data.
- Explicitly leaves revenue verified status unknown even if structurally
  valid owner-supplied fixture includes money. The Finance OS alone verifies
  authenticity and creates actual recognized revenue.
- All writes, outreach, payment, model-weight changes and ASTRA dispatch OFF.
  No GPU spending before genuine realized revenue and separate founder
  approval. Zero spending on this feature.

## Original-owner next release boundary

The already authorised Finance / Economic Memory / Predictive Cloud owners
must add an authenticated read-only source adapter that retrieves true
canonical feedback AND the exact original pre-outcome prediction, with
independent source authentication, tenant scope and retention/custody proof.
Then pass only source-authorized batches to this review through the existing
private Founder service.

Do not introduce a generic public HTTP preview accepting fabricated
outcomes as real. Do not mine public weather records, permits, news,
social posts or inferred buying signals as paid outcomes or forecast labels.
The original owner must independently inspect selective bias, class
imbalance, drift, prospective holdouts and appropriate denominators before
ever reviewing model promotion.

## Test command

```bash
cd /home/ubuntu/empire_worktrees/prime_original_calibration_gate_20261024
PYTHONPATH="$PWD" /srv/empire_os/.venv/bin/python -B -m pytest -q \
  -p no:cacheprovider \
  tests/test_prime_original_outcome_calibration.py \
  tests/test_commercial_verified_learning_review.py \
  tests/test_predictive_calibration.py \
  tests/test_quant_brain.py \
  tests/test_predictive_revenue_brain_bridge.py \
  tests/test_predictive_revenue_prime_status.py
```

Review and merge only with original owner's current concurrent worktree
reconciliation. Production and canonical `/srv/empire_os` untouched.
Rollback: drop feature commit/worktree; no persistent resources created.
