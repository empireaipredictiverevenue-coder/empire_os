# Empire AI Predictive Revenue — BLS Cost-Index Measurement and Twin Hypotheses

**20 October 2026 | Existing Predictive Decision Control worktree**
**Read-only additive feature. No new feed worker, no network call, no production changes.**

## Purpose and evidence semantics

The core economic objective is **Predicted Gross Profit → Realised Gross Profit → Prediction Error → Better Allocation**. Demand discovery alone cannot compute profitability. We also need independent price, variable cost, wage pressure, labour availability, fulfilment capacity, cash timing and refunds.

The U.S. Bureau of Labor Statistics is a valuable *official statistical context source*, especially for historical inflation and wage-related pressure. However, **Producer Price Index (PPI) is a producer output PRICE index**, not the amount a roofer, installer, service company or Empire AI actually paid for materials or subcontracting; a published wage/compensation index is not payroll proof, contractor capacity or available work hours.

Official reference:
- BLS Public Data API v1/v2, including original response `status`, `Results.series[].seriesID`, `data[].year/period/value/footnotes`: https://www.bls.gov/developers/api_signature_v2.htm
- Version 1 permits limited anonymous historical queries; version 2 requires registration for greater limits and optional metadata: https://www.bls.gov/developers/api_FAQs.htm
- BLS expressly states it **does not publish actual or average prices** in PPI, only index levels: https://www.bls.gov/ppi/faqs/questions-and-answers.htm
- PPI is an OUTPUT price index and does not directly measure an individual supplier's costs: https://www.bls.gov/ppi/publications/price-adjustment-guide-for-contracting-parties.htm

**Do not invent or guess a BLS industry/series meaning from the series ID prefix.** The existing Economic Source/Finance owner must validate specific series and catalog descriptions, base years, revision status, series geography, seasonal adjustment and reuse rights. Original source messages are owner-supplied and need independent authentication for production.

## New feature source contract

`empire_os/predictive_bls_cost_index.py`

`review_bls_cost_index_owner(owner,as_of=...)` consumes *already collected* original owner metadata:

- `schema_version=empire.economic_sources.bls_owner_review.v1`
- `mode=OBSERVE`, `execution_authority=none`, exact original BLS publisher and official API URL, `data_rights_scope=INTERNAL_ECONOMIC_RESEARCH`, no personal wage records, customer price quote, sales authority or original job supplier invoices
- `generated_at` fresh no older than **72 hours** (this is retrieval freshness, not data-month freshness)
- `bls_api_response` retaining `status=REQUEST_SUCCEEDED`, empty warning/error messages, `Results.series` and bounded original monthly observations
- An explicitly owner-reviewed mapping: original public series ID, a narrowly labelled `producer_output_price_index` or `wage_related_index`, U.S. source geography, monthly frequency, `index_not_currency` and seasonal-adjustment status. **Owner review is not independent catalogue attestation.**

The parser rejects duplicate IDs/periods, missing series, annual-average periods, future months, stale original data periods (older than **150 days**), invalid/fabricated numeric values, Boolean counts, source clock inconsistency, input data outside the allowlist or private source URLs. It computes year-over-year *index percent movement only if the exact same month of the previous year exists*. Missing comparison → `null`, not zero.

Each card keeps the public series ID, source month, index levels, preliminary footnote presence, YoY percentage, exact response/manifest revision SHA256 and explicit commercial-proof limitations.

**SHA256 is a deterministic drift marker, not signed BLS source provenance or proof of direct local supplier pricing.**

`propose_bls_hypothetical_material_cost_stress(review,series_id,assumed_cost_exposure_share,assumed_price_change_pass_through_fraction)`

The explicitly hypothetical what-if formula is:

```text
hypothetical fulfilment-cost multiplier =
  1 + (BLS YoY output price index change / 100)
      × researcher-assumed exposure share
      × researcher-assumed pass-through fraction
```

This proposes one controlled material-cost scenario under independently chosen 0–1 assumptions. The multiplier is bounded 0.5–1.5; a different cost mapping must be reviewed by the original Materials/Finance owner. A national PPI output price change cannot be directly called a local supplier cost increase; wages may **not** be mapped to the existing `labor_capacity` driver merely because compensation changed.

`bind_bls_cost_stress_to_existing_twin(review,stress,twin)` validates that the input is the original existing `HYPOTHETICAL_MARKET_ECONOMIC_TWIN_REVIEWED` and recomputes the stress from the reviewed source. It only outputs a research link to the existing `material_cost` driver and original pilot-design hash. The economic twin is **not run, modified or calibrated**, and no forecast, payout or worker is issued.

## Original measurement layer integration

`empire_os/predictive_measurement_instruments.py` now includes:
- the BLS owner-source availability/validation check;
- `bls_original_index_series_count` as an added metric, `null` when source absent or held;
- only previously reviewed research cards, never actual finance postings;
- unchanged independence of Storm, Market GPS, original Quant registry and Economic Memory.

The live operator supports one optional **existing owner-reviewed JSON**:

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

# No input: missing BLS source remains unknown, not fabricated zero.
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_measurement_instruments_20261020 --read-only

# Future step ONLY when an existing BLS source owner has a reviewed result.
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_measurement_instruments_20261020 \
  --read-only --bls-owner-review /path/to/approved_owner_result.json
```

Live operator checkpoint on 20 October 2026: **BLS_OWNER_SOURCE_NOT_CONNECTED**, 11 Market GPS researched markets, no original matched forecast/paid outcome; 28 scorecard metrics with one added unknown source-count metric. The previously cached Storm data remains stale, not current weather.

## What to build next — existing owner handoffs

1. **Official Macro/Materials/Finance source owner:** choose genuinely suitable *monthly* BLS PPI and any genuinely monthly wage-related **index** series, including revisions, official catalogue meaning, units, geography and vintage. The official Employment Cost Index (ECI) is **quarterly** and requires a separate original period contract before integration; it must not be passed through the monthly adapter. Produce a small approved read-only response. No installer or paid API key is needed for the adapter itself.
2. **Material/Operations owners:** connect the official source index to supplier quotations, original invoice/contract, job-level cost allocation, geographic applicability and fulfilment capacity. Do not infer all inputs from an industry index.
3. **Scientific Quant:** register original 2026 (or later) model forecast and scenario assumptions **before** observing outcomes, with immutable readback and time-bound horizon.
4. **Finance/Economic Memory:** reconcile original paid/fulfilled units, refunds and costs to the same pilot/product/cohort. Then compute actual margin and forecast error with sample-size and selection-bias checks.
5. **Decision Control:** use scenario sensitivity for responsible research decisions, not auto-spend, customer repricing or permission to send.

## Verification

`tests/test_predictive_bls_cost_index.py` covers original payload/period parsing, year-on-year signs/missing baseline, revision drift, invalid or future observations, malformed values, preliminary footnotes, source authority forgery, wage/source distinctions, bounded assumed pass-through and unchanged original twin execution rights.

`tests/test_predictive_measurement_instruments.py` also covers absent, reviewed and falsely promoted BLS source packets in the original unified multi-source scorecard.

**No source fetch, provider registration, new feed worker, source-owner overwrite, production data mutation, billing, web publishing, model training, automatic market shock or marketing messages were performed.**

## 20 October 2026 — first actual public BLS API connection (opt-in)

The official documentation names **PCU327320327320** as ready-mix concrete manufacturing (national industry Producer Price Index). The public, unregistered API v1 permits a bounded one-series GET without an API key. The instrument `empire_os/predictive_bls_public_probe.py` and opt-in switch below provide one original live response, and the source keeps its preliminary revision flag.

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_multi_index_cost_pressure_20261020 \
  --read-only --probe-official-bls-v1
```

**Live read-only probe checkpoint** from the official v1 endpoint:
- September 2026 published index **402.820** (preliminary, subject to revision);
- September 2025 index **393.592**;
- original monthly year-over-year price index change **2.3446%**;
- 35 original source records returned; 2 included **M13 annual-average** values. Both are now explicitly excluded from monthly analytics; none is silently treated as December.
- 33 monthly readings examined, with published source periods and no buyer, job invoice or finance owner approval.

The probe makes **one deliberate HTTPS GET** to a hard-coded official BLS URL, checks the final URL, bounds the response, validates status and source IDs, declines malformed source months/duplicate periods/missing year-on-year observations and discloses its freshness/limitations. **No stored source owner packet, API credentials, data warehouse write, cron, agent, scraper, spend or supplier invoice claim.**

`scripts.review_predictive_multi_index_cost_pressure_20261020` now supports `--probe-official-bls-v1` solely for research. It **does not replace** the existing `--bls-owner-review` path, does not set `bls_series_count` for unapproved original owner input, and cannot trigger a hypothetical scenario from public data alone. To issue *even a hypothetical model* on this dataset, the existing Materials/Finance/Economic Source owner must approve the series description, relevance, context and exact original economic scenario assumptions. Public PPI does **not** mean actual Empire paid input costs.

The original `review_bls_cost_index_owner` is also fixed to recognise correctly typed `M13/Annual` observations and exclude them from monthly YoY comparisons. Invalid M13 periods still HOLD. This removes a genuine structural incompatibility with original BLS API v1 responses, with accompanying tests and no other source-owner modifications.

References:
- https://www.bls.gov/developers/api_signature.htm
- https://www.bls.gov/developers/api_FAQs.htm
- https://www.bls.gov/ppi/notices/2013/ppi-introduces-regional-detail-for-ready-mix-concrete-indexes.htm

**Still not a full live connected cost-optimisation engine**. Ready-mix concrete is an initial verifiable proof-of-source series; before using roofing, HVAC, solar or other niche scenarios, source owners must select and verify relevant series, preserve geographic/period meaning, confirm source licences and obtain actual customer/product-level invoices, payments and forecasts. No producer feed was activated in production.
