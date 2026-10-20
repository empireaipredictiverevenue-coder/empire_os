# Predictive Revenue — Four-Stage Economic Evidence Chain and Original Profit Forecast

**Owner worktree:** `/home/ubuntu/empire_agents/predictive_decision_control_20261018`
**Date:** 20 October 2026
**State:** reviewed, read-only feature; **not deployed or authenticated profit measurement**.

## Objective

Finish the source contracts for **(1) actual supplier quotations/invoices, (2) labour and delivery, (3) customer price/payment/refund, (4) prospective original Quant and profit-forecast custody**, then hand the resulting source-quality constraints to the **existing Predictive Cloud** owner. There must be no duplicate Materials, Payroll, Finance, Commerce, Quant registry or Cloud optimizer.

The north star stays **original forecast → independent actual revenue/COGS/cash outcome → error and calibration → improved resource allocation**. This incremental build constructs the *typed evidence handoff*. It cannot independently create actual external invoices, payroll records, signed commercial terms, settled customer transactions or an immutable forecast registry.

## Existing source owners inspected and reused

- `enterprise_finance_evidence_readiness.review_finance_source_readiness`: canonical Revenue Pulse / Economic Memory / Buyer Capacity snapshots, independently exposed seven proof gaps, and existing finance event reader source contract.
- `finance_event_reader_source_contract.review_source` and the dedicated canonical reader source: declaration/readiness, **not proof a live PostgreSQL function or reader role can currently authenticate each transaction**.
- `predictive_customer_value_commerce_evidence.review_customer_value_commerce_evidence`: typed, cancellation/refund-aware product, subscription, service and licensed-data source-owner claims.
- `original_conversion_registry.build_registration_request` and `inspect_prospective_registry_readback`: **conversion-probability-only** canonical registration preflight and readback consistency; caller-provided matching dictionaries cannot establish an independently signed immutable record.
- `predictive_profitability_playbooks.review_profitability_playbook`: the original hypothetical downside/base/upside economics.
- `solar_fulfilment_observation`: existing resource execution context; **CPU/time/disk observation is not actual monetary fulfillment cost**. No shadow payroll or invoice ledger built.

The runtime source sweep did not find original per-job supplier invoice/quote or payroll artifacts in the checked predictable folders. Finance currently has fresh **internal aggregate source snapshots** but **not independent money-movement attestation or complete same-cohort financial records**. Unknown remains null.

## Step 1 — Materials procurement and invoices

Added `empire_os/predictive_four_stage_economic_custody.py`:

Source owner packet `empire.predictive_revenue.materials_owner_claim.v1`, restricted to `existing_materials_procurement`, OBSERVE-only and `SOURCE_OWNER_REPORTED_UNAUTHENTICATED`. Each line requires an opaque SHA256 line/document reference, supplier quote *or* invoice classification, exact event date, original allocated units, exact integer minor-currency total, cost nature and explicit **unverified original document** state. It rejects duplicate lines, future invoices, incompatible currencies and nonintegral per-unit allocation.

**Quotes are not invoices and invoices aren't proof of paid costs.** If a basket mixes invoice and quote records without a trusted supersession chain, the selected material cost and computed contribution become **null**, not a made-up combination. A local digest doesn't authenticate a third party. Supplier, invoice and payment proof remains the existing Materials/Finance owner's task.

## Step 2 — Labour and last-mile delivery cost

Source owner packet `empire.predictive_revenue.operations_owner_claim.v1`, `existing_workforce_fulfilment`. Exactly the same opaque original tenant, pilot revision, product, geography and currency must match Materials and price owner packets.

Inputs are per-unit crew minutes, *assumed* loaded hourly labour rate, distance tenths-of-km, *assumed* rate per kilometre, other fulfilment expense and explicit `capacity_units_source_verified=false`. The instrument rounds cost fractions **up** in minor currency units. It does not infer staffing availability, travel radius, wage compliance, paid timesheets, accepted subcontractor capacity or a national index-to-local wage conversion.

Actual labour cost and serviceable radius require Workforce/Dispatch's original time logs, supplier terms, payroll/invoice and travel evidence, with product-specific allocation. No new route crawler, dispatcher or HR app installed.

## Step 3 — Accepted prices, real payments, refunds

Source owner packet `empire.predictive_revenue.selling_price_owner_claim.v1`, `existing_commercial_terms_billing`. Requires an opaque commercial terms and original price-event reference, source observation time, **quoted vs source-reported accepted** state and positive minor-currency unit amount. Even a source-reported acceptance **is not settled, attributable customer revenue**.

Optional existing `predictive_customer_value_commerce_evidence.v1` owner result is accepted for *claimed* aggregate paid/reversal event counts, only with source type/authority and currency checks. It **does not** authenticate that individual events belong to our product/territory or prove refund window completeness. Counts cannot be allocated across unrelated cohorts.

Illustrative per-unit contribution equals offered price minus **source-reported material reference and assumed labour/delivery/other fulfilment**. It's deliberately labelled *unverified and excludes CAC, payment fees, tax and overhead*. Do not use this figure as realised gross profit, ROI, a supplier quote, or currency converted earnings. A negative figure is a hypothetical warning, not documented financial loss.

## Step 4 — Original prospective forecast and financial error

Added `empire_os/predictive_original_profit_forecast_preflight.py`:

Builds a deterministic **unregistered profit forecast intention** before the originally planned pilot starts, including original opportunity, pilot revision, start/end, currency, product type, uncalibrated weighted/worst economic scenario profit and the cost/price source claims. The canonical SHA256 changes if stated economics or original clock changes.

**Critical distinction:** existing `original_conversion_registry` only permits the `conversion_probability` type. It must not accept our hypothetical operating-profit prediction under a false conversion type. The original Quant/Finance source owner needs a **separate, durable, authenticated profit-forecast registry**, with an independently auditable original timestamp and readback. A deterministic candidate hash does not satisfy this.

The preflight refuses retrospective forecast authoring after pilot start, currency or revision drift, or an already-verified actual revenue/profit claim. It sets original registered forecast, canonical readback, actual profit, profit error, calibration and Economic Memory learning **false or null**, never zero.

## Run the new operator

```bash
PYTHONPATH=/home/ubuntu/empire_agents/predictive_decision_control_20261018 \
  /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_four_stage_economics_20261020 --read-only
```

The default reads **existing** Finance-owner aggregate source readiness only. If the original Materials/Operations/Commercial/Quant owners provide a reviewed, explicit JSON bundle, pass:

```bash
PYTHONPATH=/home/ubuntu/empire_agents/predictive_decision_control_20261018 \
  /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_four_stage_economics_20261020 --read-only \
  --owner-evidence-bundle /path/to/approved-original-owner-evidence.json
```

The optional bundle requires exactly `pilot`, `materials`, `operations`, `selling_price` plus optional `economic_plan`, `commerce_owner_review`, `original_quant_candidate`, `registry_receipt`, `registry_readback`. With `economic_plan`, the prospective profit declaration preflight is also produced. No artifact is generated, registered, emailed or saved by the operator. Sample tests are **synthetic and offline only**, never operational finance data.

Default live checkpoint 20 October 2026: three internal Finance snapshots fresh, `SOURCE_OBSERVATIONS_ONLY_FINANCE_NOT_ATTESTED`, **seven independent finance proof requirements still open**, dedicated event reader source declaration present but **not a live DB attestation**; verified supplier/labour/settlement/profit-forecast coverage and actual gross profit forecast accuracy **unknown**. `cloud_financial_optimization_eligible=false`.

## Next: Predictive Cloud after source custody

The **existing** modules `predictive_cloud_scenario_optimization`, `predictive_cloud_fabric`, `predictive_cloud_materializer` and `predictive_cloud_status` must remain the owners. Cloud should ingest this four-step readiness and scenario hypotheses, not treat PPI or unverified unit margin as paid demand.

The first Cloud integration should enforce:
1. **evidence-lane eligibility** for original supplier material, real deliverability, accepted purchase, payment/refund finality and original forecast;
2. a **scenario portfolio** that keeps hypothetical profits, capacity/cash costs, time-to-value and downside risk separate, with unknown actual profit and calibration;
3. original source revision and frozen economic baseline tracking across Cloud simulation and later independently authenticated settlement;
4. tenant, currency, canonical product/territory and timespan matching, plus idempotence, data-rights and no-automatic-spend controls;
5. replayable measured-outcome/forecast-error recording **only after original dedicated Quant+Finance registry custodies exist**.

Do not merge these feature modules into production, enable Cloud scheduling, move money, acquire personal financial records, register a prediction or train profitability predictions without source owners' independently authenticated evidence and appropriate implementation approval.

## Tests

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_predictive_four_stage_economic_custody.py \
  tests/test_predictive_original_profit_forecast_preflight.py \
  tests/test_predictive_four_stage_economics_operator.py \
  tests/test_predictive_customer_value_commerce_evidence.py \
  tests/test_original_conversion_registry.py \
  tests/test_predictive_profitability_playbooks.py \
  tests/test_enterprise_finance_evidence_readiness_20261018.py
```

**Authority:** observe only, no external service call, new credential, monetary transaction, DB write, registry write, employer/source-owner mutation, outreach or deployment.
