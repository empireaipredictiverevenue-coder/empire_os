# Product-specific competitive intelligence — implementation and release

Owner: existing Predictive Intelligence / Predictive Cloud, 21 Oct 2026. Read-only comparison release; original revenue forecasts and customer economics still held.

## Previous defect
The original comparison mapped **all 86 different products** to the same six CRM/revenue-intelligence vendors. Although the tool correctly flagged feature parity as unverified, this overstated relevance for solar maps, local search, property intelligence, capital intelligence, public records and unrelated recovered-MRR SKUs.

## Implemented remediation
Added `empire_os/predictive_product_specific_competitors.py` with deterministic SKU/lane classification, official vendor source URLs and original pricing units where publicly observed. It explicitly recognises product markets:
- Revenue forecasting / operations: existing founder-approved flagship ladder and forecasting SKUs; vendor-adjacent HubSpot, Microsoft, Zoho, Clari, Gong, Databox.
- Search intelligence: Ahrefs, Semrush, BrightLocal, based on SEO/visibility categories.
- Local-search grid/AI visibility: BrightLocal Track and Semrush Local Base.
- Solar opportunity maps: Regrid Property App, PropStream property platform, Semrush Local — *adjacent only*, **not verified substitutes for solar market opportunity maps**.
- Sales/prospecting/lead enrichment/lead routing: Apollo, Clay and BuiltWith where the SKU code indicates a matching adjacent market.
- Property intelligence: PropStream and Regrid.
- Permit intelligence: ConstructConnect project data and Regrid parcels — **neither is proof of identical original permit API coverage**.
- Private capital roll-up intelligence: Dealroom Premium.
- Unrecognised/broad SKUs, including Meetily and All Access, have *zero* mapped adjacent vendors until real scope is verified; absence of a defensible comparator is better than fabricated parity.

One lane can contain multiple adjacent products. These are not verified functional equivalence, procurement quotes, exact contract-cost comparisons, independent licences, or validated willingness to pay. Published prices remain unconverted source-currency, billing-unit references, never direct Empire tariff suggestions.

## Original vendor references
- https://www.semrush.com/pricing/seo-ai-search/
- https://ahrefs.com/pricing/
- https://www.brightlocal.com/pricing/
- https://www.semrush.com/pricing/local/
- https://www.apollo.io/pricing
- https://www.clay.com/pricing
- https://builtwith.com/plans
- https://www.propstream.com/pricing
- https://app.regrid.com/plans
- https://www.constructconnect.com/pricing
- https://dealroom.co/pricing-usd
- Existing original reference URLs in `predictive_competitive_product_comparison.py` for HubSpot, Microsoft, Zoho, Clari, Gong and Databox.

Research observations as of 2026-10-21. Published numbers are subject to changes, plan restrictions, onboarding, licence scope, tax, available volume and currency. Any subsequent external commercial comparison must recheck original vendor prices and dates.

## Tests and governance
- 86 original SKUs keep their exact price amount, currency and billing unit.
- Founder policy ceilings (26) and customer-verification holds remain unchanged.
- Every mapped vendor contains source URL, original unit, and `comparison_type=ADJACENT_MARKET_REFERENCE_ONLY`.
- Every candidate retains `feature_parity_verified=false`, `total_price_comparability_verified=false`, `price_justified_by_benchmark=false`.
- All unmatched SKUs expose an empty list and `no_reliable_direct_comparator_yet=true`.
- Existing `empire-predictive-comparison --all` returns per-product mapping; the summary reports `adjacent_reference_count` and `products_without_adjacent_reference`.
- No automatic repricing, new customer assertions, DB grants/migrations, payment activation, outbound, or model promotion.

## ASTRA GPT-6
ASTRA's **separate independent review remains NOT EXECUTED** until an independent reviewer explicitly examines the exact pinned release, original marketplace pages, price/seat/contract comparability, product scope, technical tests, observed delivery economics, customer value and claimed scientific benefits. This module adds research evidence; it must not self-approve products or claim an independent review occurred.

## Guarded production boundary
Commit to the existing Predictive branch, run adversarial+existing harness, build via existing immutable OBSERVE-only release builder, recheck its manifest and both `comparison` and `comparison-all` commands, and update only the reversible private user alias. The Cloud materializer timer, Founder API, EmpireDB and commercial activation switches are outside this release.
