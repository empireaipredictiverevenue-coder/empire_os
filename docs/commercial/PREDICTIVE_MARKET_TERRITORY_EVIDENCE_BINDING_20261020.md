# Empire AI Predictive Revenue — Territory Evidence & Economic Twin Binding

**20 October 2026 | Predictive Decision Control feature branch | owner-safe, read-only**

## Why this is a critical part of the original system

Predictive Revenue must eventually answer **who wants to buy what, where and when; at what acceptable price; whether we can actually deliver; what the fully attributed gross/operating profit and cash exposure would be; what could change the result; and which playbook should run**. Its north-star remains:

**Predicted Gross Profit → Realized Gross Profit → Prediction Error → Better Allocation**

This increment binds the *existing* Revenue GPS database-derived market research to the *existing* Market Economic Digital Twin, with strict geography/niche/source-epoch and commercial-proof boundaries. It is not a stand-alone market research product, another buyer worker, an unreviewed campaign or a parallel finance system.

The real issue previously was that:
- The Market Sweep already had **territory-by-niche** observational aggregate counts.
- Digital-twin scenarios already calculated demand/capacity/pricing effects on complete unit economics.
- But the twin could not identify the **exact original market record and revision** behind a specific simulated territory. A similar metro string, an old market row or a high research score might be mistaken for genuine buyer demand.
- Data in source-owner counters and source queue had to remain in the original permissions and evidence category. Source marks `verified_product_economics` in some cases, but its embedded economics are expressly a **founder policy scenario**, not actual accepted price, CAC, settled revenue or cost.

## Built and tested

### 1. Territory evidence source

New `empire_os/predictive_market_evidence_binding.py`:

`review_revenue_gps_territory_evidence(snapshot, *, as_of)`

It accepts one **existing** original `empire.market_sweep_revenue_gps.v1` snapshot from:

`/srv/empire_os/runtime/market_sweeps/revenue_gps_latest.json`

It validates:

- Source schema, OBSERVE mode, `execution_authority=none`, outbound disabled, restricted aggregate research scope, no inferred buyer/market share/revenue, explicit zero unverified replies or positive reply classifications and a trustworthy timezone-aware generated timestamp.
- Source must be no older than 8 hours for this use; stale or future snapshots return **HOLD and zero source cards**.
- The exact total number of market rows, bounded 1–31-day observation period, commercial-demand market count and competitor coverage market count.
- Each row must have a bounded, legitimate niche and metro key; metro normalization turns **`little rock, ar` into `little_rock_ar`**, but does **not** silently equate `littlerock_ar` or other name/region aliases. Duplicate source rows and normalized colliding metro/niche keys fail closed.
- Every observed count is an actual nonnegative integer; no `True` as count, invented real revenue without a recognised event, incongruent supply/demand state, market-share proxy mislabelling, impossible/commercial source claim, overwritten price, or missing unverified source flags.
- Commercial demand summary is internally consistent with source-reported commercial replies, commercial terms and verified payment counts. **Even if a count is positive, it is not independently authenticated to one purchaser, sale, cohort or pilot.** A market-research score or company record is not a purchase probability.
- Competitor-pressure values are strictly a **modeled signal-density research proxy** or unavailable. `0.0` with zero competitive signals is still a model result for a company density denominator, not evidence that competitors are absent or a market is uncontested.
- The source research queue is checked for non-execution and no underlying unsupported or duplicate geography. The new feature does **not** dispatch or write its requests.
- Source `verified_product_economics` legitimately has **two states**: `available=false` sentinel when no approved policy/cat­alogue scenario is available; otherwise a verified *catalogue's founder policy hypothesis*, always with `prediction=false`, `actual_revenue=false`, `actual_cost_observed=false`. Neither state is verified selling price or actual costs.

The report emits safe, per-market research cards with an independent source-epoch revision fingerprint, niche and normalised metro, company/prospect research counts, source-reported commercial reply/terms/payment counts, competitor-signal coverage, missing authentication prerequisites and an existing-owner research next step.

**SHA256 here is an anti-drift marker from the current snapshot**, not a signed provenance authority, payment signature, user identity proof, original Quant forecast or immutable registry record. No original company/person/email, raw source URLs, replies or buyer contact details are emitted.

### 2. Economic twin research connection

`bind_territory_research_to_market_twin(registry, twin)`

- Takes only the above held/validated source-review result and the existing `empire.predictive_revenue.market_economic_twin.v1` hypothetical output.
- Requires **exact niche + metro key**. Does not infer country, jurisdiction, coordinates, weather event, legal service territory, direct buyer seat or real supply. An ambiguous alias or market with the right location but wrong niche has `TWIN_TERRITORY_SOURCE_NOT_EXACTLY_MATCHED`; it is never silently attached.
- When matched, exposes the source-revision identifier, research score and missing commercial proof next to the existing original pilot design hash. **It does not insert the original research count as an actual future demand/capacity input**, change a model weight, authenticate a customer price, register an original forecast or release a playbook.
- Requires the twin still be hypothetical, with no registered forecast, no authenticated market claims and no production shock application.

### 3. Private operator

`scripts/review_predictive_market_evidence_binding_20261020.py`

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_market_evidence_binding_20261020 \
  --read-only

# Narrow the displayed cards without mutating the underlying source
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_market_evidence_binding_20261020 \
  --read-only --niche hvac
```

Only the allowlisted aggregate JSON file is read; no network crawling, SQL, commerce data, private email, arbitrary file traversal or new persistent snapshots.

## Real observed snapshot at first successful live test, 20 October 2026

The existing owner source generated **07:20:12 UTC** on 20 October contained **11 distinct niche/metro records**, **0 markets with observed commercial demand evidence**, and **2 markets with competitive source coverage**.

Representative safe research findings:

| Niche | Source metro | Source prospect acquisitions | Original buying/terms/payments within that market |
| --- | --- | ---: | --- |
| General contractor | NYC | 47 | None in source |
| Plumbing | Little Rock, AR | 5 | None in source |
| HVAC | Little Rock, AR | 2 | None in source |
| Roofing | Little Rock, AR | 2 | None in source |
| Predictive Revenue enterprise | Brooklyn, Irvine, Middletown, New York, San Francisco, Tampa, Tysons | 1 per metro | None in source |

**A high source research priority (e.g. 80 for NYC general contractors) is not buying likelihood, model confidence or customer profitability**. Likewise the system cannot conclude that *zero market-wide sales* occurred: the source has limited observation rights/coverage and only reports what those sources contain.

For the targeted HVAC Little Rock corridor, the live read-only operator returned `TERRITORY_LEVEL_MARKET_RESEARCH_JOIN_READY` and the research next step `FIND_ORIGINAL_DIRECT_PURCHASER_DEMAND_AND_BUYBOX`. This is guidance to the *existing* buyer/market owner, not permission to contact someone.

The existing competitor feed and storm snapshot were separately observed as **stale** in the prior economic-twin source-readiness check. They must not be used to calibrate current prices, weather-driven property damage or actual capacity. Revenue GPS's fresh aggregate market signals do not by themselves supersede those freshness requirements.

## Test coverage and source drift

`tests/test_predictive_market_evidence_binding.py` is built against the original `market_sweep_revenue_gps.normalize_market_sweep` producer, with synthetic supplement fields reflecting the *richer current production* aggregate contract. The feature-branch producer currently lacks the explicit unverified-reply indicators emitted by production; production requires them and **the bridge fails closed if they are absent**. This is intentional; source producer owner must agree on the final immutable schema before deployment.

Tests cover:
- Realistic 11-market source characteristics and exact normalized Little Rock niche-specific match.
- Zero real buying evidence with high acquisition/competitor research scores.
- Source-reported positive commercial terms/payments still not independent verification.
- Source epoch/digest drift and global counts vs market-row consistency.
- Invalid geography aliases, ambiguous/colliding city keys, personal-address-like inputs, duplicate territories and wrong niches.
- Forged revenue, published prices, model status, buyer claims, market share and phantom purchases.
- Unverified replies/false-positive classifications and unauthorized research queue dispatch.
- Original hypothetical twin not becoming an authenticated paid forecast and no source file mutations.

### Exact next owners and gates

1. **Market GPS / Source Intelligence owner:** maintain the current producer's signed/versioned source contract, source-specific rights, observation windows, market/territory normalization and demand-evidence counters. Verify source producer revision before merge.
2. **Geographic/Spatial owner:** attach **canonical geographical identifiers** (country, metro/state/ZIP or corresponding UK unit) and source epoch to the market research records, not string-matched guesswork. Match storms/property/service zones only after geographic and source rights verification.
3. **Buyer Qualification / Commerce / CRM owner:** bring in first-party commercial replies/accepted buying terms, paid unit, currency, eligible territory, quantity, payout, refunds and direct buyer capacity, not marketplace/supplier-only statements.
4. **Market / competitor / materials / weather / operational capacity owners:** supply permitted, independently timestamped local real observations, maintenance and labour price feeds, stock/fulfilment constraints, and competitor price movements for each target corridor.
5. **Scientific Quant / Original Registry owner:** make a prospective, signed/read-backed prediction with immutable original source identifiers **before** outcomes. The scenario engine can then use calibrated probability distributions rather than research priority as a probability.
6. **Finance / Economic Memory:** reconcile original price, paid order, delivery, net cost, refunds and realized gross/operating profit to the exact previous prediction. Company-wide Revenue Pulse profit cannot calibrate one market opportunity.
7. **Decision Control / existing playbook owner:** consume source-verified, cohort-consistent market economic opportunities under permitted capital, risk and contact policies. Before that, all suggested actions remain research-only.

## Release boundaries

**Not deployed.** No source service/timer, agent code, database schema, website, outbound queue, billing system, model weights, contact rights, marketing spend or account payments were altered. The feature is designed for future reviewed integration by the original market and twin owners, not automated production mutation.

The vital proof chain is:

**Territory source evidence → verified identity/rights → original calibrated economic assumptions → registered prospective forecast → controlled action → authenticated purchase, fulfilment, refund and cost → realized margin → original forecast error → Economic Memory → better allocation.**

We have built the **source-level territory research binding**. The latter verified-purchase and registered-original-forecast stages remain unavailable to this feature and must not be represented as completed.
