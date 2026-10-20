# Empire AI — Precision Market and Revenue Gap Intelligence

**20 October 2026 | Predictive Decision Control owner branch | READ-ONLY**
**Scope:** additive economic diagnostics, no launch, source mutation, automation, paid feeds, email or website changes.

## Business objective

Find real economic opportunities and **why value fails to materialise**, then compare feasible remedies with strict source provenance and original profitability:

**Observed market/commerce evidence → causal hypotheses → scenario stress → cost/cash/capacity/time constraints → authorised experiment → measured revenue and realised gross profit → original forecast error → improved allocation.**

The system must never conflate a missing buyer, recently imported old building permit, news headline, stale storm report, preliminary BLS PPI, or reported outbound stage counter with a verified revenue gap. Precision matters more than an impressive-looking score.

## The crucial distinction: four truth classes

1. **Observed source-stage fact:** a source-owned, timestamped count or record legitimately observed in its bounded window. May be incomplete and not authenticated to the same economic cohort.
2. **Modelled structural shortfall:** e.g., hypothesised 1,400 eligible requests and 1,000 deliveries suggests 400 *simulated unserved attempts*—not 400 lost sales.
3. **Possible cause or intervention:** e.g., service capacity, customer response friction, inflated materials, CAC, buyer eligibility or collection lags. The cause remains unknown without source-specific testing.
4. **Authenticated economic outcome:** original prospectively registered forecast, original first-party buyer, accepted price and capacity, payments, cancellations, refunds, fulfilment, paid input costs and original coherent cohort. Only this may support reliable forecast error and learning.

Unknown is represented as **null**. Reported zero is not a global assertion of no demand. Hypothetical profit denominated in minor currency units remains hypothetical.

## Existing owner systems reused

- `market_sweep_revenue_gps`, restricted market reader, source revision/territory bridge;
- `commercial_funnel` original materialized snapshot and owner stage algorithm;
- `predictive_profitability_playbooks` original unit economics, three original downside/base/upside hypothesis books;
- `predictive_market_economic_twin` demand, supply, price, conversion, CAC, fulfilment and refund shocks;
- `predictive_bls_cost_index` owner-reviewed official statistical index and explicitly unverified cost translation;
- `predictive_storm_measurement`, `permit_project_intelligence`, `predictive_primary_source_economic_bridge`;
- `original_conversion_registry`, Finance, Customer Value and Economic Memory as future *original outcome* truth owners.

**No parallel buyer scout, forecast, finance ledger, campaign manager, Storm collector or Newsjack agent has been added.**

## New engine: Structural Revenue Gap Diagnostics

`empire_os/predictive_structural_revenue_gaps.py`

`review_structural_market_revenue_gaps(pilot,economic_plan,market,interventions,as_of)`

Inputs: one original unregistered prospective pilot, its unchanged price/cost/payment-cohort hypothetical plan, one original hypothetical niche/geography market baseline, and up to 10 **explicitly supplied** structural interventions with:

- a typed research cause such as `capacity_constraint`, `demand_acquisition`, `conversion_friction`, `cost_pressure`, `price_pressure`, `fulfilment_risk` or `regulatory_delay`;
- a compatible *existing* economic twin driver, e.g. `labor_capacity`, `material_cost`, `channel_distribution`, `consumer_preference`, `competitor_response` or `regulatory_change`;
- explicit demand, available capacity, selling price, conversion, acquisition cost, fulfilment cost and refunds what-if multipliers;
- independently supplied **one-off implementation cash expenditure** and **estimated days until effect**, clearly not observed implementation cost or measured speed.

The **existing Market Economic Twin** recalculates each intervention's full original weighted operating profit, worst-case loss, cash outflow and capacity effect. The gap lens then conservatively adds one-off implementation expenditure *exactly once* to modeled cash and subtracts it from hypothetical incremental operating profit, without changing original cohort assumptions.

Intervention verdicts are RESEARCH labels only:
- `RESEARCH_CONDITIONALLY_FEASIBLE_UNVERIFIED`: **under supplied assumptions only**, the case fits the original planning horizon and cash cap, has positive incremental and net weighted profit, and is nonnegative in the modeled worst case; no buyer, capacity, root cause or effect has been verified;
- `RESEARCH_PROFITABILITY_OR_DOWNSIDE_UNDER_ASSUMPTIONS`;
- `RESEARCH_CASH_LIMIT_UNDER_ASSUMPTIONS`;
- `RESEARCH_TIMING_BEYOND_ECONOMIC_HORIZON`.

A ranking among these is an **ordinal research heuristic**, not a posterior probability, real ROI, or calibrated economic value of information. Scenario weights are not measured frequencies. Results cannot grant purchase, marketing, consumer contact or model training authority.

**Example (FICTIONAL, not live Empire revenue):** model 1,400 possible HVAC requests and 1,000 capacity units. The diagnostic reports 400 *hypothetical unserved attempts*, then evaluates capacity investment against its actual extra cash requirement, potential material inflation, customer pricing and time-to-effect. Profit upside can be rejected as impractical if the scenario needs too much cash or doesn't improve worst-case downside. No currency conversion or inferred profit is attributed to the 400 attempts.

### Gap taxonomy: what to study next

| Gap type | Real proof required | Possible structural repair | Economic check |
| --- | --- | --- | --- |
| Demand uncovered / underserved corridor | Valid original purchase intent by canonical geography/time, negative examples, actual eligibility | Better source/marketing focus, service partnerships | Marginal paid demand, true achievable capacity, acquisition cost and incremental margin |
| Supply and delivery mismatch | Verifiable contractor availability, service radius, materials and schedules | Add authorised supplier capacity, alternative fulfilment | Unit COGS, travel, cancellation risk, cash needed before payment |
| Buyer qualification / buybox mismatch | Original buyer decision authority, accepted terms, permissible traffic/product type | Offer alignment, better qualification, partner terms | True attainable unit price and payout, returns, expected win rate |
| Conversion or reply stagnation | Provider-authenticated same-cohort stages and elapsed time | Message/offer experiments, response systems, contract process repairs | Time to sale, actual conversion, no fake success denominators |
| Pricing / margin leakage | Invoices, owner approved tariffs and actual costs by purchased SKU | Adjust terms, cross-sell, packaging, sourcing changes | Incremental gross profit minus CAC, fixed costs, fees and refunds |
| Revenue collection and cash gap | Provider payment status, invoicing, late funds and chargebacks | Improve terms, shorten approved collection cycles, reserves | Cash exposure and capital constraint, cost of finance and downside |
| Regulatory, procurement or weather timing | Official original issuance/tender deadline/event, jurisdiction and rights | Early research/authorised bids or helpful response | Probability only when calibrated; fulfilment and timely delivery |

This framework is multi-industry: HVAC, roofing, solar, home services, professional services, B2B digital software, data products, apps and services—not construction-only.

## New instrument: Founder Commercial Funnel stage quality

`empire_os/predictive_funnel_gap_instrument.py`

Reads only the **existing** `runtime/commercial_funnel/latest.json`, validates original `empire.founder_commercial_funnel.v1`, OBSERVE authority, bounded integer stage counters, source epoch, and the original `commercial_funnel._commercial_stage` logic.

Owner snapshot must be within **48 hours** for current tactical advice. Older source returns `FOUNDER_FUNNEL_SOURCE_STALE_HOLD`, with current counts **null**, never 0.

The source owner publishes counts in separate, potentially overlapping windows/cohorts, and some different funnel stages have different denominators. Consequently, **do not divide or subtract stages to infer closed-funnel response/conversion percentages or lost money**.

A fresh source may warrant investigation if delivered events exist but no commercial replies are recorded, if reply evidence exists but terms aren't approved, or if approved terms exist but no verified payment evidence is recorded. The suspected cause remains unknown until the original provider, tenant and buying authority have been authenticated.

This instrument does not read contacts, messages or private leads, nor does it send any follow-up.

## New live review operator

`scripts/review_predictive_gap_intelligence_20261020.py --read-only`

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_gap_intelligence_20261020 --read-only
```

Combines existing source-reader statuses for original Founder Funnel, restricted GPS research, Storm, Permit and optionally BLS. If a hypothetical scenario bundle is supplied by its owner, it also reviews the original pilot and structural remedies **without acting on any of them**.

```bash
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_gap_intelligence_20261020 --read-only \
  --hypothesis-bundle /path/to/original_owner_hypothesis.json \
  --bls-owner-review /path/to/approved_owner_bls_review.json
```

The optional bundle must contain exactly `pilot`, `economic_plan`, `market`, `interventions`. The BLS input comes from its **existing source owner**. No new access tokens, HTTP calls or synthetic live purchases.

### Live source checkpoint, 20 October 2026

| Source | Observation status | Precise implication |
| --- | --- | --- |
| Founder commercial funnel | **STALE**, about 668 hours old (last snapshot 22 Sep) | Can't diagnose **current** conversion bottlenecks or lost revenue |
| Market GPS | 11 researched market records | Research coverage, not real market-wide demand and not buyer terms |
| Storm | **STALE**, historical saved snapshot 5 Oct | Cannot claim current storm-created buyer need |
| Permit | 136 recent imports of *historical* NYC filings; 0 original recent filings among them | A recent import is not a newly opened real construction job |
| BLS | Original reviewed source **not connected** | No actual index data or real current supplier cost calibration |
| Original matched paid outcomes and Quant profit prediction | Not authenticated by this gate | Actual monetary gap and model forecast error remain **unknown** |

This is a **source-readiness diagnosis**, not a claim that Empire AI has no genuine customers or that markets contain no opportunity. Refreshing the source-owner funnel under its own restricted role is the first prerequisite for reliable real-world revenue leakage analysis. Source permissions and production changes require their original owners.

## Intelligence upgrades to build after this source groundwork

1. **Cohort lineage graph:** original buyer/product/territory/consent identifiers across all stages, immutable stage event IDs and timestamps; include negative outcomes. Needed before conversion leakage or causal inference.
2. **Authenticated unit-economics cost observatory:** original supplier quote, actual purchased invoice/contract, labour hours, service fulfilment, payment fees, refunds, and time to collect, joined to a tenant/product SKU. Link index vintages only as supporting statistical context.
3. **Uncertainty and selection-bias diagnostics:** missing-label fractions, small-denominator intervals, drift, calibration/reliability curves from registered-before-outcome forecasts; don't produce percentages of unobserved outcomes.
4. **Causal playbooks:** controlled/consented experiments where permitted, comparable untreated regions/cohorts, uplift and opportunity costs. Different simultaneous interventions should not be treated as independently additive without tests.
5. **Scenario stress & intervention frontier:** original expected, downside, cash and time-to-effect comparisons across price, conversion, fulfilment and demand levers; bound financing/capacity and scenario dependency, not fabricated point ROI.
6. **Value-of-information allocation:** after the uncertainties and real economics are measured, prioritise which buyer call, supplier quote, data coverage, or original labelling task is worth obtaining next. Current P0/P1 priority categories are **heuristics**, not £/$ expected value.
7. **Periodic source freshness/rights audits:** source owner, data licence, revision, first-published, observed and processed clocks, historic vs recently imported changes, and unsupported joins. Do not silently fill missing outcomes.

## Release boundaries

No production deploy, new network collector, marketing/website write, customer outreach, BLS API spend, cash movement, schema migration, CRM change, Quant registration, or automatic model training. Gap outcomes are **unverified hypothetical**, source-stage observations remain source-scoped, and no market-wide revenue gap is claimed.

**The next actual commercial milestone is an authenticated original buyer/payment and a registered forecast with matching costs, as opposed to adding more research counts.**
