# Predictive Revenue Product Science — 20 October 2026

Scope: the EXISTING 86-product catalogue, including flagship enterprise product ladder. OBSERVE candidate in isolated worktree, not a deployed customer forecast/model.

## Actual technical capability added

1. A deterministic **per-tenant and per-catalog-product** conversion calibration evaluator consumes the existing `empire.commercial_prediction_calibration.v1` packets. Each original prediction and terminal outcome is recomputed through the existing typed forecast-feedback review and `validate_verified_feedback` functions. Version-verified catalogue `product_id -> product_code` mapping is required; duplicate prediction, terminal outcome or fulfillment order is rejected; cross-tenant and cross-SKU records fail closed.
2. Product forecasts are compared against **past-only resolved historical conversion baselines**. Each baseline uses only outcomes that became available strictly before that evaluated forecast was issued. The evaluator calculates model and baseline Brier, observed skill, average calibration gap and the 95% Wilson interval for *observed frequency*, which is explicitly NOT a per-customer prediction interval. Its bounded input is at most 500 original calibration packets; minimum 20 past resolved outcomes and 12 prospective evaluations.
3. PII-free results retain `original_registry_readback_authenticated=false`, `original_source_issuer_authenticated=false`, `forecast_eligible_for_customer=false`, `economic_memory_update_eligible=false`. Synthetic local tests can yield excellent Brier scores, but they never demonstrate actual model performance or customer revenue.
4. A restricted **read-only source-snapshot integration** reads canonical root-owned EmpireDB catalog and predictive_intelligence files with open-file safe custody; validates type, age, aggregate counts and version, does NOT read or write original DB records. Its output is 86 SKU evidence-readiness statuses, with no numeric future predictions unless owner-authorized evidence later actually exists (and even then it remains held until independent issuer and original forecast registry proof).
5. The pinned launcher supports `empire-predictive-observe science`; the default output is a bounded privacy-safe summary. No timer, service, model registration, new product, database role, financial or outbound authority was created.

## First original read of current state
- Original catalog: 86 SKUs, 35 active, 26 declared binding-terms ready, all eight families and five flagship tiers present.
- Existing root-owned `runtime/predictive_intelligence/latest.json` on 20 Oct: 0 source outcomes, 0 matched, 0 product estimates, 0 probability-ready and 0 time-to-revenue-ready cohorts, no tenant binding. Minimum advertised samples: 20 terminal, 8 timing.
- Therefore final original science status `NO_PRODUCT_TERMINAL_OUTCOMES_OBSERVED`. The successful technical fixture tests are NOT original outcomes.

## Next genuine source-owner handoff and launch readiness
- Existing Sales/CRM source owner collects real opted-in first party acquisition and its exact tenant lineage. The Hermes canonical source handoff was queued as `predictive-canonical-sales-owner-evidence-20261020-v1`; being queued is NOT being merged or production-ready.
- Existing Finance/Outcomes owner must verify original accepted terms, payment, fulfilment, recognized revenue, refunds and actual costs independently under least privilege. This is *not* implied by catalogue pricing.
- Original Quant/Forecast Registry owner must register a real conversion prediction **before** its corresponding future outcome and subsequently independently read back exact bytes. Without this no customer-facing calibration or Economic Memory learning.
- Existing Enterprise owner must verify private tenant access, entitlements, model-version pinning, data-rights expiry, audit and rollback.
- Model progress measured by original immutable forecast/outcome pairs, count, Brier skill vs past-only baseline, calibration gap and holdout drift. A high score on a synthetic or supplier-reported packet does not satisfy launch.
- Founder will decide when to invoke GPT-6 Astra independent architecture/science/security challenge; this step is NOT automated or currently invoked.
- Financial/outbound/go-live activation remains separately gated and OFF.
