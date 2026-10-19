# Empire AI Predictive — Customer Value & Purchasing Demand Intelligence

**19 October 2026 | Predictive owner | feature/predictive-decision-control-20261018**

## Why this matters

Predictive Revenue must identify **what people are trying to accomplish**, how they currently solve it, which *products/apps/services/data feeds* they compare and buy, where they waste time or cash, and where a new or improved offer delivers a genuinely useful result. It should work across **US/UK, consumer and business markets, all verticals**—not merely lead generation, storm restoration or roofing.

**Business principle:** offer solutions that demonstrably save customers time, reduce real costs, improve a specific outcome or help them earn more, and be paid for measurable value. Do not assume a keyword search, complaint, shopping listing, web traffic spike or LLM label means a person bought a product. Avoid exploiting vulnerable people or misrepresenting savings. There is no real user-level purchase tracking here.

## Added feature code and interfaces

- `empire_os/predictive_customer_value_demand.py` is additive pure review code: (A) `review_existing_community_needs(snapshot, as_of=...)` bridges **already aggregated** pain-to-solution briefs from `empire_os/community_intent.py` and `pain_solution_engine.SOLUTION_MAP`; (B) `review_customer_value_observations(records, as_of=...)` accepts bounded, tightly typed, externally originated observation *receipts* for consumer/business, product/app/service/data_product, job-to-be-done key and market; (C) `compare_monthly_customer_value_scenario(...)` evaluates a **what-if** comparison with separately entered time, ordinary costs and incremental subscription/product cost, and optional user-assigned hourly value.
- `scripts/review_predictive_customer_value_demand_20261019.py --read-only` reads only `runtime/community_intent/latest.json` via the existing Predictive owner worktree. It neither collects nor emits raw social messages, comments, authors, search clicks, consumer identifiers, company contacts, licence tokens or source URLs.
- `tests/test_predictive_customer_value_demand.py` exercises public interest vs claimed purchase, four product types and two audiences, duplicate source origins, malformed rights/time, privacy, synthetic example savings, negative/missing benefits, source catalogue custody and retention.

### Current real observation (not purchasing data)

The observed `empire.community_intent.v2` aggregate currently contains **five** mapped problem themes: `lead_generation`, `search_visibility`, `revenue_growth`, `sales_conversion`, `automation_ops`. The current source covers only part of B2B/community needs and is **not** a representative survey of the total products/apps/services market. The code correctly returns `independent_purchase_data_connected=false` and `time_or_money_benefit_verified=false`.

## Exact evidence hierarchy

1. **Public problem:** discussion, dissatisfaction, app/service review, difficulty doing a task; signal of a problem or sentiment, **not** a sale.
2. **Exploration and comparison:** searches, searches comparing products, reviews, marketplace/catalog listings; **not** a sale.
3. **Claimed purchase:** stated user purchase or first-party sales record awaiting origin/transaction authentication; still only an **unverified claim** in this module.
4. **Verified sale / activation:** only after existing Commerce/CRM/payment/App Analytics owner produces independently checked, rights-cleared source-of-truth receipts (purchase, paid subscription, cancellation, return, fulfilment) with timestamps, coverage denominator, product taxonomy, region, dedup and refund reconciliation. **No such authenticated adapter is connected to this module yet.**
5. **Measured customer gain:** only after independent, timestamped before-and-after task/cost/usage evidence with same unit and time horizon, incremental expense, alternative explanations and appropriate consent. The what-if calculator never reports `customer_roi_verified=true` or `income_or_profit_realized=true`.

### Why the source classes are separate

`review_customer_value_observations` accepts *public_problem*, *public_comparison*, *public_review*, *app_review*, *public_search*, *seller_marketing*, *catalog_listing*, *buyer_purchase_claim*, *first_party_receipt_claim*. The last two only increment **purchase-claim counts**, not independently verified purchases or paying demand. All rows require privacy-safe market/job/product-class codes, a bounded exact permission scope `INTERNAL_AGGREGATE_RESEARCH_ONLY`, a timezone-aware 90-day observation, source-origin/content digests and no extra raw-text fields. Duplicate origin digests within one market/audience/product/job cluster count once. Digests are deduplication receipts, **not proof of customer identity, purchase or rights**. Research points sort a human-review queue, never model a sale probability, demand share, revenue or market size.

The output is always `mode=OBSERVE`, `execution_authority=none`, with no CRM write, payment, outbound, crawler, model calibration or original Quant registry mutation. **No magic universal data coverage** is claimed.

## Research programme for expansion (existing owners; not automated)

Use existing **Search Fabric / DataForSEO / public market research, Commerce owner, community source atlas, app marketplace research, and permitted customer usage or transaction analytics** under their own separate permissions and data usage terms. Scope by:

- Who: consumers vs firms, region, language, use case and buying unit; avoid protected demographic targeting and sensitive inferred traits.
- Need: time lost, unnecessary expense, customer acquisition, reliability, process friction, quality, user cancellation or unmet demand.
- Options: physical products, software/apps/subscriptions, human services/bookings and licensed data/API products.
- Purchase evidence: real paid orders/renewals, returns/refunds, verified bookings/invoices and app paid activations; distinguish platform estimates/reviews from verified purchase records. Avoid scraping private marketplace accounts or bypassing terms.
- Value validation: before/after measured time, cost, user-paid incremental fees, reliability and quality; pilot design, attrition, sample size, negative outcomes. Avoid assuming results transfer between cities/verticals/customer segments.
- Delivery: if real demand is independently proven, Business Development validates supply and lawful customer purchase terms; Quant registers an **original prospective forecast** before outcomes are seen, Economic Memory later calibrates against authentic payments and negative outcomes.

### User-utility example — what-if, not a claim

An app is hypothetically tested on monthly admin tasks: 900 baseline minutes, 660 with the app; £80 baseline expense and £55 after; £15 monthly app cost. The scenario returns **240 minutes saved**, **£10 net cash avoided**, and, if the user separately assigns an illustrative £10/hour to their own time, another **£40 of time value** (not cash); illustrative combined equivalent **£50/month**. This is arithmetic on example inputs, **not proven time saved, app performance, adoption, conversion, revenue, pricing or buyer satisfaction**.

The next genuine result requires permitted original purchase/usage receipts from the independent owner and supervised A/B/pilot before commercial claims.

## Run (read-only)

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_customer_value_demand_20261019 --read-only

PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -B \
  -m pytest -q tests/test_predictive_customer_value_demand.py
```

**Release gate:** feature worktree only. No production merge, SQL, new crawling, public data activation, customer data access, outbound, payment or customer marketing promise. Coordinate with existing Community, Commerce, Research/SEO, CRM/BD, and Quant owners to add strictly consented, independently validated receipts without crossing their files or performing duplicate ingestion.

## Cross-market research blueprint (unexecuted; explicitly optional)

`build_cross_market_customer_value_research_blueprint()` adds **20 bounded research questions** spanning UK/USA, consumers/businesses and four product classes. The underlying job-to-be-done themes are **household bills, personal admin, trustworthy home services, product comparisons, subscription waste, manual business work, lead conversion, supplier costs, purchasing decisions and customer-support delays**. Each has an appropriate customer-value outcome to test (minutes, net cost, return-adjusted purchase value, service quality, real margin) and three missing-evidence research tasks. This is a **scope plan**, not 20 observed needs, 20 opportunities or 20 sales. No new search/data collection, provider account access or outbound was activated.

Run the optional expanded operator:

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_customer_value_demand_20261019 \
  --read-only --include-research-blueprint
```

The blueprint distinguishes supported *future source-owner research* from the currently available five observed Community Intent pain themes. Its fields `real_world_search_executed=false`, `buyer_data_or_spend_observed=false`, `research_questions_are_detected_market_needs=false` should remain false until independently substantiated by the existing owners. This is designed to keep Predictive's opportunity discovery broad while respecting source provenance and scientific calibration rules.
