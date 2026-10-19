# Empire AI flagship — forecast population completeness, maturity and censoring

19 October 2026 — owner branch feature/predictive-decision-control-20261018.

## Purpose

A statistically impressive percentage among linked outcomes is not proof of
commercial prediction precision. For rigor, **every original registered
forecast**, including predictions which are pending, unresolved, expired,
unsuccessful or not included in Economic Memory, must be accounted for.

Reuse existing Quant, canonical Economic Memory, original conversion registry
and original verified outcome feedback. No new conversion model, tenant
database, commercial score, agent or permanent writer is created.

## Code

- empire_os/flagship_forecast_population_audit.py
- tests/test_flagship_forecast_population_audit.py
- Existing independent validation: lead_shadow_calibration_benchmark.py,
  predictive_calibration.py, outcome_feedback.py.
- Never touches the separately owned buyer/CRM, DB schema, website, timers,
  source polling, payment, outbound or Quant/model weight controls.

Audit accepts an optional bounded, owner-provided, **UNAUTHENTICATED**
population manifest. It revalidates the canonical Economic Memory and exact
forecast/outcome linkage before classifying each item:

1. Matched independently verified terminal win.
2. Matched independently verified terminal loss (not inferred).
3. Pending within forecast horizon.
4. Horizon elapsed with **unverified outcome** (NOT a negative label).
5. Verified Economic Memory prediction missing from the supplied manifest.

It rejects duplicate forecast/opportunity IDs, tenant mismatches, malformed
source lineage/probabilities, future/backdated chronology, a retrospectively
registered known outcome, or an inventory prediction inconsistent with
Economic Memory. An arbitrary manifest can NEVER prove original EmpireDB
registration, complete population, model accuracy, business revenue or
source authenticity. It emits aggregate classifications only, not people,
buyers, CRM leads or raw private commercial records.

## Calibration / commercial activation hold

- Source registry SQL/transport is staged and inactive. The feature branch
  cannot independently authenticate an exported registry universe.
- As of the live read-only October 19 checkpoint, canonical Economic Memory
  contains **0** paired terminal prediction/outcome calibration reviews and
  **0** verified linked learning feedback rows.
- An empty/missing exported forecast universe is UNKNOWN, not zero issued.
- An expired forecast without verified outcome must never be silently
  labelled 0: negatives require original verified terminal evidence.
- The fixed-threshold descriptive precision wave remains **held**. Wilson
  intervals do not correct biased samples or invented outcomes.
- No automatic model fitting, forecast promotion, outreach, payment, DB
  mutation or customer accuracy advertising is authorised.

## Next exact owner integration

Ask the original conversion registry owner to provide an authenticated
tenant-scoped read-only snapshot containing prediction ref, opportunity key,
model/version, original timestamp/horizon, original probability/evidence,
immutable DB registration time, and authenticated reader timestamp, with
complete population counts and independent original-row hashes. That
requires a separately approved DB actor and deployment evidence.
Ask the CRM/buyer and Economic Memory owners for a safe matching join
between original forecast refs and consent/opt-out-aware, first-party
terminal outcome evidence (including losses).

Then replace this unauthenticated manifest boundary with the existing
authorised reader after owner-reviewed integration. Only THEN calculate
population coverage and explore censoring/survival methods, rolling holdout
calibration, market-stratified reliability, uplift over historical baseline,
time to verified revenue and actual profit. Set thresholds and holdouts
before inspecting the outcome labels.

Test fixtures are isolated mathematical/evidence contract tests. They
are NOT real customer outcomes. Commit does not mean merged or deployed.
