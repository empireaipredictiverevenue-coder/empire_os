# EmpireOS Predictive Intelligence + Cloud — Trends and Future Trends, Phase 1

Date: 2026-10-22. Existing branch `feature/predictive-decision-control-20261018`. **No new system or AI agent was invented.** This extends `empire_os/future_trend_intelligence.py`, `empire_os/trend_regime.py` and the existing Future Trend component already published by Predictive Cloud.

## Production truth

The current materializer's `runtime/predictive_cloud/future_trend_latest.json` reports `algorithm_available=true` but `analysis_executed=false`, `prediction_ready=false`, `source_admission_state=UNVERIFIED_LOCAL_SNAPSHOT_ONLY`, and no independently attested original forecast/outcome pairs. The existing component represents runtime **availability**, not executed future trend forecasting. Do not retrofit fabricated trend data to turn the status green. The dedicated conversion registry in EmpireDB was separately confirmed absent by the original root-owned read-only operator; it remains an independent later activation gate.

## Implemented integration — existing Future Trend algorithm plus chronological source review

New pure `empire_os/predictive_trend_horizon_review.py` passes comparable, original metric observations into the existing `analyze_future_trend` logic for **direction, change velocity, acceleration, persistence, and emerging/declining phase**. It adds one-step rolling-origin research evaluation comparing zero-trend/naive with drift baseline **without using revisions learned after each historical cutoff**. A drift scenario is permitted only if it beats naive by >=10% of naive error, the series is fresh, has >=9 historical points, sampling is sufficiently regular, and the horizon does not exceed the measured historical span / supported extrapolation bound.

The horizon proposals are **7/30/90 days**; unsupported projections remain null, not 0. These are bounded *illustrative future index/demand scenarios*, NOT calibrated forecasts, expected revenue, confidence intervals or buying signals. The research engine never fits a price or conversion model and never modifies actual products or model weights.

The source envelope carries a fixed `source_name`, stable series ID, vertical, geography, original metric definition/unit (`index_0_100`, `index_points`, or original nonnegative `count`), observed event time, first externally available time, ingestion time, revision, and a SHA-256 integrity claim. It rejects mixing units, geographies, metric sources or sample frames, future events, delayed historical revisions, duplicate original revisions, NaN/Infinity, invalid counts and inconsistent clocks. The SHA-256 and file source are **not an original issuer signature or data licence**. The report emits a reproducible digest but not raw customer IDs or source refs.

### Meaningful niches and inputs

Existing source owners can eventually supply independently authorized fixed time series for **US/UK roofing, solar, HVAC, dental, legal, local search, property, consumer intelligence and other verticals**. Candidate categories:
- **Search interest**: Google Trends normalized search-interest indices (never raw search volume; normalization/low-sample noise must be retained); separate source-specific GSC impressions/clicks or other SEO series under distinct units.
- **Buyer demand**: original buyer requests, opted-in queries, qualified non-duplicated intent signals, with customer privacy and accepted source rights.
- **Supply shifts**: accepted publisher inventory, available permits/projects and provider capacity, keeping distinct geographies and sampled coverage.
- **Leading indicators**: OECD country-specific composite leading turning-point indicators, verified macro/supply indices. Do not convert qualitative turning-point signals directly into quantitative revenue predictions.

Never mix the 0-100 normalized search index with absolute volumes, compare dissimilar Google Trends normalization windows or combine buyer-intent counts with permits as one numeric series. Multi-source confluence and statistical model selection are future integration stages after original source ownership and sampling consistency are admitted.

### Primary methodological references

- https://support.google.com/trends/answer/4365533 — Google Trends is sampled, normalized to region/time and scaled 0–100, not absolute volume.
- https://nixtla.github.io/statsforecast/docs/tutorials/crossvalidation.html — rolling-origin time series cross-validation with historical cutoffs (not random train/test shuffle).
- https://www.oecd.org/en/data/datasets/oecd-composite-leading-indicators-clis.html — OECD CLI anticipates qualitative economic turning points, not a literal quantitative sales forecast.

## Private commands — exact pinned OBSERVE-only release

Existing `scripts/prepare_predictive_readonly_release_20261020.sh` stages checksum-pinned review commands:
- `empire-predictive-observe trends`: safely inspects existing Cloud trend availability and why verified forecast readiness remains closed; no source rows read.
- `empire-predictive-observe trends-template`: an EMPTY documented owner-source envelope, intentionally not a synthetic trend dataset.
- `empire-predictive-observe trends-series /path/to/original_approved_series.json`: bounded owner-supplied source research, with real timestamps and hold states. The filename is an optional approved owner artefact; it is **not** a prompt to scrape arbitrary websites or run paid traffic.

The existing Cloud runtime producer/Founder API do not change in this private release. A later separately approved Cloud producer bridge can consume a signed, owner-admitted trend series (not a local file assertion); until then cloud `analysis_executed=false` and consumer `prediction_ready=false` remain honest.

## Test/acceptance criteria

- Historical revisions unavailable at a fold cutoff cannot contaminate earlier training; post-decision backfills cannot alter an earlier digest or scenario.
- Future timestamps, mixed source units/regions, invalid index, nonfinite values, duplicate original revisions, irregular/stale series, flat/no-trend performance and extrapolation beyond history all fail closed or return null.
- Every output preserves `source_owner_authenticated=false`, `forecast_accuracy_verified_on_customer_outcomes=false`, `commercial_forecast_authorized=false`, `database_writes=false`, `actual_revenue=false` and `execution_authority=none`.
- Private release's checksum and smoke tests cover `trends` and empty `trends-template`. Existing Cloud materializer/Founder services and DB roles remain unchanged.

## Next release gates

1. Existing Market GPS / SEO / buyer source owners approve one stable, licensed historical time series by country+niche with real available/ingested times. Refuse fake or thin signals.
2. Independently test sampling and backtest against seasonal naive, change point detectors and rolling-origin holdouts; if drift fails, do NOT issue a numeric future scenario.
3. Add sector-geography multi-series confluence and real owner data ingestion to existing Future Trend materializer only after independent readback/rights and tenant isolation review.
4. Separate original conversion registry DDL, authenticated source/outcome evidence, customer model calibration, ASTRA GPT-6 review and founder approval remain necessary before customer-forecast or revenue action.
