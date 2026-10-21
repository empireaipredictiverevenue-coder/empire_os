# Predictive Revenue — source-backed internal price-policy headroom, NOT realised margin

Owner: existing Predictive and Commercial Catalogue read-only reviewer. Date: 21 October 2026.

## Original evidence read
The exact root-owned catalogue snapshot currently contains 86 SKUs across eight families and six currencies. 61 list nominal prices, 25 omit prices. Five enterprise deployments retain their already approved founder price floors. **No amount was modified.**

Twenty-six catalogue SKUs have all four source-reported objects marked `VERIFIED`: price basis, acquisition policy ceiling, fulfilment policy ceiling and minimum-margin founder policy. These objects are policy assumptions, **not actual delivered costs**. The other 60 SKUs do not have a complete analogous policy bundle.

## Improvement implemented
`empire_os/predictive_price_policy_evidence.py` evaluates only complete consistent policy claims with exactly matching currency, per-unit billing basis, and common source provenance, supporting both founder-approval-reference and dated localized-solar policy formats. The dated cost ceilings must not exceed their bps policy caps. Any contradictory source shape fails closed.

For each complete SKU, calculate in **original currency minor units**:
- Cost-cap scenario = acquisition ceiling + fulfilment ceiling.
- Scenario contribution before unbudgeted fees = original listed price minus above ceiling.
- Scenario margin bps = floor(scenario contribution / original listed price * 10000).
- Minimum accepted policy margin bps = original founder policy.
- Extra cost capacity (minor units) = floor(price * (10000 - required bps) / 10000) - approved ceilings.

Under the current **policy assumptions**, all 26 complete SKU cases meet the internal minimum; none currently signals an internal margin-ceiling shortfall. This does **not** prove the stated caps are sustainable, real, comprehensive or actually achieved.

Example: `solar_opportunity_map_gb` price GBP 249.00 per map, approved maximum acquisition GBP 49.80 and maximum fulfilment GBP 49.80, cost-cap contribution GBP 149.40 (60.00% of price), internal policy floor 55%. This **is not evidence of GBP 149.40 realised profit**: provider licences, original provider rights, actual labour, payment fees, refunds, VAT/tax, overhead and cash settlement require separate original receipts.

The existing full-catalogue `empire-predictive-comparison` summary exposes: `approved_cost_ceiling_scenarios_available`, `approved_ceiling_scenarios_meeting_margin`, `approved_ceiling_scenarios_below_margin` and `approved_cost_ceiling_scenario_is_actual_margin=false`. `--all` provides source-custody-safe policy scenarios per SKU. The older builder and original local catalogue are not changed.

## Adversarial harness and deployment
The harness rejects malformed provenance, different currencies/units, future or mismatched policy dates, contradictory bps ceilings, invalid costs and reclassification of assumptions as actual. It checks all 86 existing SKU identities/currencies/amounts remain unchanged and forecast authority, model training, auto repricing, outbound and payments stay OFF.

Ship only as a **new immutable private read-only release**, replacing the dedicated operator alias after checksum validation. Existing Cloud materializer, Founder API, tenant RLS and DB permissions remain on their separate live releases.

## ASTRA GPT-6 independent review requirement
Present full 86-SKU report, original price and cost-policy source metadata, vendor URLs with observation dates, original accepted customer requirements, original delivery labour and compute invoices, security/SLA/support costs, and actual accepted billing/settlement/returns when available. ASTRA must challenge pricing gaps, including what is excluded from the ceiling scenario, and compare apples-to-apples licences versus bespoke total contract scope. The current ASTRA status stays `NOT_EXECUTED`; this policy check is not an independent GPT-6 price certification.
