# Empire AI Predictive Revenue — Commerce & Customer Value Outcome Custody

**19 October 2026 | Predic­tive Decision Control | isolated feature worktree**

## Purpose

Continue the existing EmpireOS **Predictive Revenue** build from commit `246014c2`. Join consumer and B2B research to measurable commercial outcomes across physical products, apps, service bookings and licensed-data subscriptions, **without** inventing purchasers, sales, customer savings or calibrated forecasting accuracy. This feature owns no Commerce, billing, CRM, customer-success, Economic Memory or production code.

### Four new additive interfaces

- `empire_os/predictive_customer_value_commerce_evidence.py`: `review_customer_value_commerce_evidence(pilot, receipts, tenant_ref_sha256, as_of)`. Pure event-ledger preflight. Requires the **same original unregistered pilot revision, scoped opaque tenant ref and source-owner** for all records; no PII, raw source texts, user emails or URLs. Source type is explicit: product / app / service / data_product. The provider classes are `commerce_orders`, `app_subscription_billing`, `service_booking_billing`, `licensed_data_billing`.
- `empire_os/predictive_customer_value_measurement_evidence.py`: `review_customer_value_measurement_evidence(pilot, measurements, tenant_ref_sha256, as_of)`. Supports only original preselected primary metric, unit and comparison design; paired baseline/follow-up observations and optional randomized treatment/control arms. Rejects changed arms, duplicate measurements, future data, invalid units, source-rights escalation and cross-tenant observations. Calculates **unverified, source-reported signed differences**; never infers experimental sample integrity, statistically significant causality, independent people or verified savings.
- `empire_os/predictive_customer_value_outcome_readiness.py`: `review_customer_value_outcome_readiness_runtime(repo_root, as_of)`. Reads only the existing `runtime/predictive_intelligence/latest.json` and `runtime/buyer_capacity_readiness/latest.json` aggregate snapshots. Validates original producer schema, current clock, consistency and negative commercial authority; does not touch raw billing, buyer identities, private events or other owners' services.
- `scripts/review_predictive_customer_value_outcome_readiness_20261019.py --read-only`: safe private operator for the above existing live source readiness.

### Commercial event custody details

- `paid` and `renewed` require an original positive charge, a unique bounded source event reference and a distinct purchase/renewal-period reference.
- `booked`, `fulfilled`, `returned` and `cancelled` are **not** charges. A booking alone never creates money or a sale.
- Refunds/chargebacks reference their preceding charge, must be timestamped after it, and cannot cumulatively exceed what was originally paid. Refund settlement may fall up to 30 days after the original trial's final observation; it does not rewrite the originally fixed forecast horizon.
- Costs and charges are in the same minor currency unit; GBP, USD and EUR cannot be mixed without an authenticated external FX owner. **Negative margins remain possible**. The net is labelled `source_reported_net_after_reversals_and_variable_cost_minor_unverified`; it is never recognised accounting revenue or an independently checked result.
- All owner input statuses must equal `SOURCE_OWNER_REPORTED_UNAUTHENTICATED`. A source-owner name, text claim, URL, hash or transaction ID is **not** an actual signed or authenticated payment receipt. The adapters do not assert a finished sample, complete refund set, original registered forecast, tenant authentication, verified savings or model calibration.
- Owner event/purchase/cohort/tenant references are SHA256-form opaque digest fields required for privacy-limited handoff. This requirement does not itself prove a digest is private, independent, authorised or signed.

### Value-measurement custody details

The pilot's specified primary metric and unit are fixed. Baseline observations must precede the pilot start within the original baseline window; follow-up observations must occur within the planned pilot window and must have been available by the review timestamp. Two original sample arms are recognised for randomized holdout designs; before-and-after designs are treatment-only. A source-reported signed difference between arms is **not a causal claim** and can be affected by sampling, randomization failures, missing outcomes, refunds, attrition, measurement bias, seasonality and lack of original pre-registration. The feature never sets `time_or_cash_saved_verified`, `causal_lift_verified` or `customer_value_calibration_ready` to true.

### Latest live findings (read-only point-in-time, NOT enterprise-wide audited totals)

- Existing `empire.predictive_intelligence.v1`: 26 verified *catalogue* products; **0 source outcomes and 0 probability-ready product models**.
- Existing `empire.buyer_capacity_readiness.v1`: **0** populated verified terms and **0** verified buyer capacity in its observed buyer inventory.
- The original prospective conversion registry's **authenticated activation/readback remains unproven by this read-only adapter**. No original frozen, tenant-bound registered forecast or authentic customer-value experimental outcome has been supplied.
- None of the features in this commit were deployed or permitted to send email, write payment/CRM records, copy raw customer data, create synthetic wins, activate visitor tracking, or update model weights.

### Runbook

```bash
cd /home/ubuntu/empire_agents/predictive_decision_control_20261018
PYTHONPATH=. /srv/empire_os/.venv/bin/python -B \
  -m scripts.review_predictive_customer_value_outcome_readiness_20261019 --read-only

PYTHONPATH=.:tests /srv/empire_os/.venv/bin/python -B -m pytest -q \
  tests/test_predictive_customer_value_commerce_evidence.py \
  tests/test_predictive_customer_value_measurement_evidence.py \
  tests/test_predictive_customer_value_outcome_readiness.py
```

### Exact next owner integrations

1. **Commerce/App/Booking/Data Billing owners**: provide authorised, deduplicated source event projections for purchases, renewals, cancellations, refunds, chargebacks and fulfillment; the owner must validate provider signatures, settlement and refunds against their primary account data *before* issuing a verified outcome. Integrate these projections through the new contracts rather than scraping accounts or extending privileges to Predictive.
2. **Customer Success/Analytics**: consented pilot enrollment, source-verified before/after tasks, time/cost/quality outcome definitions, control/baseline sample integrity and negative result inclusion. This module reads none of those personal records today.
3. **Scientific Quant / Original Prediction Registry**: independently registered original prospective forecast and tenant-bound readback **before** outcomes are available. `original_conversion_registry_transport.py` is separately gated; this feature **never** attempts to enable its writer or reader.
4. **Existing Economic Memory/Outcome owners**: authenticated terminal win/loss and original payment/fulfillment/revenue linkage, *then* the existing `outcome_feedback.py` and `predictive_calibration.py` can accept scoped labels under their own permissions. No model training or customer ROI claims from claim-only data.

**Prohibited shortcut:** do not call catalogue products, public buyer intent, a booking count, an illustrative monthly value calculation, a customer-reported purchase, or an unregistered Quant preview a verified sale or predictive accuracy.

### Known limitations

These source-owner data structures are validation contracts, not connected provider feeds or production RPCs. Hash references cannot prove legal identity, absence of duplicates outside one bounded batch, rights or genuine payment. A signed source custody and original registration phase must precede calibration. Aggregates are point-in-time snapshots and cannot be interpreted as a single same-cohort funnel.
