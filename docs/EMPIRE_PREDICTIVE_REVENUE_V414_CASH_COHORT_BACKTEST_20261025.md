# Empire AI Predictive Revenue V4.14 — historical cash-cohort backtest (HELD)

**25 October 2026 | Original EmpireOS / EmpireDB / Smart CRM | No trading | Code-only release**

## Purpose

Move beyond synthetic P10/P50/P90 illustrations toward a properly reviewable *historical* assessment of forecast errors **without inventing verified cash receipts or converting revenue-recognition events into cash evidence**.

This release adds `empire_os/predictive_revenue_v414_historical_cash_backtest.py` and its tests. It composes original V4.12 organic cash twin's simulation-only contract, V4.13's recognised-event-vs-collected-cash evidence hold, and the existing `SignedCrmTenantVerifier` with fresh authenticated active membership. It does **not** mount a new API, provision a DB role, launch a worker, touch the service or modify existing source files.

## Actual implementation

- Accepts **12–240 explicit historical cash-cohort cases**, supplied by a researcher. Each case has a tenant, rights-source digest, exact currency (GBP/USD/EUR from original V4.12), distinct cohort key, cohort inception, forecast freeze time, fixed 30/60/90-day target, bounded integer-minor-unit forecast and naive baseline, and an optional claimed cash outcome.
- Rechecks **original signed CRM membership** and rejects mismatched tenant/currency/source, future observations, reversed time ordering, forecasts registered after cohort inception, mixed horizons, duplicate cohort refs, invalid fractional or non-finite currency amounts, missing provenance, and outcome dates not after the full horizon.
- **Never treats missing outcome as zero:** for missing, immature or incomplete fixed selections, the scorecard is held and no cherry-picked survivors-only MAE/WAPE/skill is presented.
- On a complete *caller-supplied* set only, derives bounded experimental MAE, WAPE and skill versus a last-known/naive supplied baseline, plus a chronological two-thirds older vs one-third more recent holdout segment. A synthetic favourable result cannot grant permissions.
- Any reference formatted `claim:...` is specifically untrusted, even if a researcher records a plausible cash amount. User-provided data, SHA-256 fingerprints or an apparent `canonical:` label are **not** EmpireDB financial verification.
- Both V4.12 P10/P50/P90 and V4.14 historical cash error statistics remain **unvalidated**. Historical forecasts may be fabricated/backfilled; source custody, full denominator, finance settlement, currency, refunds, chargebacks and finality all need separately authenticated original readers.
- All runtime gates stay off: no model/causal DAG updates, no economic memory writes, no outreach, no spend, no financial execution, no customer forecast release.

## How to read the result

`COMPLETE_CLAIMED_HISTORICAL_SCORECARD_EVIDENCE_HELD` means *all researcher-supplied rows are mature and contain a numeric claim*. It does **not** mean the cash outcomes, registered forecasts, selected population or customer revenue are independently verified.

`HISTORICAL_COHORT_COVERAGE_INCOMPLETE_HELD` means some rows are missing or not mature; related diagnostic errors and comparative skill are unavailable—not zero and not positive evidence.

The non-canonical scorecard prototype currently found in the live checkout is **untracked**, so it was not copied, modified, imported or deployed as part of this release. V4.14 is versioned, self-contained and additive to the shared GitHub base.

## Required for genuinely empirical 30/60/90 forecasting

1. Original EmpireDB owner supplies an approved restricted **cohort snapshot reader** that enumerates *all* eligible opportunities and records the population boundary, including losses, no responses and outstanding cases.
2. Finance independently validates **actual collected cash and reversals**, including chain/currency and exact minor units and timestamps, on the same cohort at each horizon. REV051's recognised-revenue event reader alone cannot do this.
3. Forecast snapshots must be registered before their prediction target and immutable under trusted issuer custody. Split by event time and prevent future information leaking into training.
4. Demonstrate performance against an honest naive model across sufficient diverse historical cohorts, separately evaluate P10/P50/P90 coverage on held-out data, track model bias and sample drift, and get commercial/finance/customer acceptance.
5. Only then seek approvals for a tenant-scoped **read-only founder dashboard**. Operational commercial actions remain separately gated.

### Verification

- 27 focused V4.14 tests: native Ed25519 CRM login, real V4.12 fixture, bounded histories, mature 30/60/90 targets, exact currency, stable time splits, forged/duplicate data rejection, missing/censored outcomes, benchmark failure detection and control holds.
- V4.9 live readiness remains OBSERVE; V4.10 migration 066 **not applied**; V4.11–V4.14 are code-only, not commercial forecast releases.
