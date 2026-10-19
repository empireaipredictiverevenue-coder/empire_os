# Empire AI Predictive Revenue — Customer Value → Radar → Prospective Quant Evidence

**19 October 2026 | owner: Predictive Decision Control | isolated feature branch**

## Purpose

Continue the **existing Predictive Revenue** build. Business Development, Buyer Scout, CRM, approved Search Fabric, analytics, e-commerce, community connectors and payment systems are separate owners. This change supplies the missing scientific custody bridge from already observed customer problems and existing Radar opportunities to a falsifiable value proposition and **prospective** measurement plan. It does not add a new crawler, buyer scorer, parallel qualification agent, transaction database or scheduled service.

The business objective: learn which problems people need solved, what products/apps/services/data they explore or actually buy (distinguishing claims from independently authenticated purchases), and which solutions can **measurably** save time, reduce cost, improve reliability or deliver paid conversion value. Scope includes both B2B and consumer markets, not only construction or lead sales.

## Implementation

- `empire_os/predictive_customer_value_radar_bridge.py` — `review_customer_value_radar_bridge(community,radar,as_of=...)` and a bounded, read-only live snapshot wrapper. It imports and validates the previously committed `predictive_customer_value_demand.py` aggregate source contract, then requires an exact match between `Community Intent`'s observed timestamp and `Opportunity Radar`'s declared source revision. It also requires Radar to be generated after the original source (maximum 30 minutes) and observed in the last six hours; otherwise returns a hold with **no opportunity cards**.
- Matching is **exact**: only `community_pain:<pain>` keys promoted by the existing Community Intent source can create linked cards. The immutable offer key, products, evidence-strength class and mention counts must agree with original source. Duplicate or invented opportunities, drifted counts, a different community source revision, inferred buyer intent, revenue claims or external authority fail closed. All other radar records are counted as *market research* or *other research* **without attributing unobserved customer demand**.
- Each valid linked card contains a deterministic source-revision fingerprint; preserved original opportunity and product hypothesis; **proposed** primary value measurement; proposed commercial validation outcome; prospective baseline/holdout comparator, and explicit `quant_ready=false`. The source-revision digest is an anti-drift *identifier*, not a verified signed receipt, model probability or customer identification.
- `empire_os/predictive_customer_value_pilot_preflight.py` — `review_prospective_customer_value_pilot(source_bridge,design,as_of=...)`. It rejects a pilot design unless the opportunity and revision are exact, metrics are fixed from the existing mapped hypothesis, planned dates are in the future (maximum 90-day window), participant count and baseline window are bounded, and the design commits **before outcomes** to negative events, refunds/cancellations, consent and prospective original forecast timing. Supports a separately labelled randomized holdout or observational before-and-after. Even a valid plan is explicitly **UNREGISTERED** and does not attest consent, actual enrollment, study power, causal lift, signed buyer terms, realized margin, customer savings, registered forecast, or any Quant calibration.
- `scripts/review_predictive_customer_value_radar_bridge_20261019.py --read-only` — loads **only** existing `runtime/community_intent/latest.json` and `runtime/opportunity_radar/latest.json`, not raw posts, account names, contacts, payments or URLs; never writes JSON or schedules external work.
- `tests/test_predictive_customer_value_radar_bridge.py` and `tests/test_predictive_customer_value_pilot_preflight.py` cover original builder integration, source-epoch mismatch, drifted immutable products/offers/intent, duplicate IDs, forecast leakage, future-time gates, cross-revision pilot poisoning, model-proof boundary, and no writes/private-data copying.

## Latest read-only live evidence

At the verified checkpoint the Community Intent source had **five** distinct problem themes, of which **two** had actually produced Radar `community_pain` opportunities: `sales_conversion` and `search_visibility`. The same Radar snapshot contained **11 separate market-research** records. The customer-value research blueprint has **20 unexecuted UK/US consumer-and-business questions** spanning physical products, apps, services and data products. These numbers fluctuate with the upstream source cycle, so the operator validates the exact current revision every run.

For the two observed problem themes, suggested real-world experiments include:

- `sales_conversion`: measure original, attributable inbound-to-sale conversion and real contribution margin **after delivery costs and invalid/refunded transactions**.
- `search_visibility`: measure qualified search traffic and subsequent independently verified paid acquisitions, rather than impressions, rankings or search volume as revenue.

A positive scenario or public discussion isn't a buyer. No original paid cohort, price/terms, baseline, retained customer savings or authenticated outcome receipts are connected to this feature yet. The live `runtime/predictive_intelligence/latest.json` also showed **zero probability-ready products and zero source outcomes** during this review. Do not describe the linked cards as model predictions or proven product demand.

## Next implementation dependencies (respect source ownership)

1. Existing Community/Research, SEO/Search Fabric, marketplace/app sources and Commerce owners provide **rights-cleared, deduplicated, timestamped** observed comparison, paid purchase, refund, cancellation, booking and usage receipts. The public-opinion and marketplace counts must remain separate from first-party sales.
2. Existing CRM/BD owner supplies independently authenticated buyer/tenant, buying unit, price, terms, delivery, lawful processing rights and evidence of capacity. The buyer-quality gate in the other worktree is independent and must not be edited here.
3. Original Scientific/Quant owner must **register an actual prospective prediction before** sales or customer outcomes are observed. A preflight is not the signed registry. Outcomes then flow through existing Economics/Quant/Economic Memory under permitted access, including negative outcomes and cohort denominator. Only then can calibration or verified conversion metrics be computed.
4. Existing customer-success/analytics owner runs an approved consented pilot with original baseline, control or properly qualified observational comparison, elapsed task minutes, real cash expenses, product price, refunds, service quality and sample-bias analysis. A monthly illustrative time-value is **not cash profit**.

## Run in the isolated worktree

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018

PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_customer_value_radar_bridge_20261019 --read-only

PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_predictive_customer_value_radar_bridge.py \
  tests/test_predictive_customer_value_pilot_preflight.py \
  tests/test_predictive_customer_value_demand.py
```

**Production approval gates:** owner review and conflict-safe merge before a scheduled research integration. This addition has no permission to deploy, crawl marketplaces, send messages, create canonical buyers, activate customer tracking, enroll participants, accept terms, move funds, register original forecasts, or train/live-promote a model. All returned commercial/output verification fields explicitly remain false/unknown until independent original evidence is provided.
