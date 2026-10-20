# Predictive Revenue | Catalogue + Enterprise Integration & Astra Review Gate
20 October 2026. OWNER: Predictive Revenue; authority: OBSERVE. Design and isolated candidate only.

## Production source truth
- Existing EmpireDB-derived commercial_catalog/latest.json reports 86 SKUs across eight families. 26 are catalogue-declared terms-ready; this alone does not independently establish customer entitlement, settlement or deployment.
- Five flagship enterprise SKUs exist: Diagnostic USD 25k, Command Center USD 50k starting, Intelligence OS USD 100k starting, Autonomous OS USD 200k starting, Private Strategic USD 250k+ floor. None of the five currently reports binding-terms-ready in the canonical catalogue snapshot.
- Original canonical founder sales reconciliation: zero sales acquisitions, zero predictive acquisitions and zero founder-visible sales prospects; status NO_CANONICAL_SALES_ACQUISITION_OBSERVED. No real canonical customer evidence for product learning is thereby established.
- Production source owners: commercial_product_catalog.py, predictive_revenue_products.py, predictive_intelligence.py, predictive_revenue_enterprise_delivery.py, predictive_revenue_product_workbench.py, predictive_revenue_enterprise_forecast_scorecard.py, predictive_revenue_enterprise_census_shadow.py, predictive_revenue_self_serve.py; CRM/Finance dedicated restricted owner readers. Source owners work concurrently in other worktrees. Do not overwrite their implementations.

## Product principle
ONE tenant-scoped Predictive Intelligence + Economic Memory engine with PRODUCT-SPECIFIC contracts for every existing SKU. No duplicate AI model per SKU, new DB, price change, unapproved commercial authority or new agency. A catalogue entry is neither an authenticated customer order nor a fulfilled product.

Every product-specific contract defines: canonical product_code/family/version, legal rights and source provenance, tenant and regional scope, original signals and snapshots, source freshness, forecast target and frozen baseline, evidence threshold and confidence interval, advisory next actions with human gates, actual matched outcome, economic/settlement verification and customer entitlements. A verified signal can create an advisory opportunity, but cannot become a probability, binding sale or realized revenue without separately verified original events.

The isolated module empire_os/predictive_catalog_intelligence_contracts.py projects these contracts WITHOUT importing any personal customer data, performing IO, computing predictions, authenticating upstream snapshots or activating products. It deliberately emits NULL predicted values and false commercial authority. Independent source provenance must be checked by the owning reader.

## Family-specific intelligence

| Family | Evidence scope | Advisory intelligence when source-approved | Original actual needed for learning |
|---|---|---|---|
| search_intelligence (22) | dated SERP/AI visibility, search provenance | opportunity and demand shift / decay ranking | attributed qualified customer acquisition |
| recovered_mrr (51) | first-party CRM/retention/pipeline or product-specific evidence | Forecast revenue intervals; LeadScore conversion calibration; Closer sales risk; SEO/content organic trends; other products require their own target | verified retained/recovered revenue or accepted outcome and actual costs |
| commercial_exchange (4) | buyer acceptance and capacity, matched terms, accepted events | fill probability and net contribution | accepted matched event, settled revenue, verified costs |
| opportunity_intelligence (1) | canonical entity, fresh trigger and evidence | opportunity rank and why-now | verified converted opportunity |
| public_record_intelligence (1) | authoritative permits, geo, rights and dates | permitted project demand and territorial rank | accepted project opportunity |
| property (1) | property, physical and permit changes | property lifecycle and risk trend | accepted property/commercial result |
| private_capital (1) | portfolio entities, source disclosures, rights | portfolio consolidation and strategy scenarios | verified transaction/portfolio outcomes |
| predictive_revenue (5) | authenticated tenant CRM, Finance, terminal outcomes | revenue/profit forecast, calibration, scenarios, executive action priorities | recognized revenue and realized profit with matched lineage |

Never mix cohorts between tenant, product, geography, time or entity. Each SKU must map to its own outcome measure; use UNKNOWN rather than 0 where no original evidence exists.

## Flagship five products share the engine, not the same customer surface
1. Diagnostic: bounded source audit, leakage/bottleneck analysis, confidence grade and advisory prioritization. No guaranteed ROI.
2. Command Center: authenticated tenant-scoped CRM/Finance/market status, executive scorecards and alert/forecast windows.
3. Intelligence OS: cross-department demand, cohort normalization, revenue forecast, economic memory and prediction-vs-actual calibration.
4. Autonomous OS: Intelligence OS plus advisory next-best-action, bounded agent workflow, independent approvals and audit; SKU does not authorize external execution.
5. Private Strategic: dedicated tenant/portfolio boundary, custom model registry and feed rights, optional white-label, backup/SLO/security and enterprise acceptance.

The existing product workbench covers only Diagnostic and Intelligence OS. Enterprise delivery code maps capabilities for all five but contains evidence/acceptance holds. Forecast shadow evaluation does not itself certify original financial outcomes.

## Runtime lifecycle (not an auto-promotion pipeline)
CATALOGUED > INTERESTED > TENANT_VERIFIED > SOURCE_CUSTODY_OK > FORECAST_ELIGIBLE > HUMAN_REVIEWED > TERMS_ACCEPTED > FULFILLED > ACCEPTED_OUTCOME > SETTLEMENT_RECONCILED > ECONOMIC_MEMORY_ELIGIBLE.

These are independently gated states. Product interest != purchasing authority; a research lead != customer; accepted terms != paid; payment != profit; forecast != actual revenue.

Product response should carry: product_code, tenant binding state, source provenance and as_of, cohort size, model version, frozen baseline, confidence/interval or UNKNOWN, evidence-linked advisory decision, approval gates, original outcome state and settlement status. No personal IDs in customer-facing summaries. Entitlements and API usage metering must be enforced outside predictive scoring.

## Implementation work to complete
1. Map all original product_codes with exact eight family lanes and all five flagship tier semantics (isolated candidate + unit tests).
2. Connect existing restricted original CRM, sales, Finance and catalogue owners after Hermes delivers canonical reconciliation adapter. Validate original source receipts; supplied JSON alone is not proof.
3. Tenant-product-specific forecasts with exact samples, time-ordered holdouts, baselines, confidence/coverage, drift, prior forecast registry and no lookahead. Scientific claims must beat deterministic baselines under original outcome audit.
4. Join real outcomes and actual costs to Economic Memory only once canonical ledger and settlement reconcile.
5. Provide read-only versioned API/workbench entitlements per product and enterprise tier; publish no invented ROI, price readiness or human approval.
6. Test cross-tenant denial, revoked data rights, duplicate/ambiguous entities, delayed outcomes, stale sources, billing rights, downgrades, numerical outliers, rollback and all price/forecast/profit authority boundaries.

## Independent GPT-6 Astra technical review: PREPARED, NOT STARTED
The user explicitly wants the review AFTER the build and wants to DECIDE when to run it. Do not auto-launch an agent, automation, model, deployment, trial, outbound, payment or customer activation now.

At the founder's later explicit decision, prepare: pinned source commit, immutable release manifest, focused and regression tests, 86-SKU contract coverage, real cohort provenance and original anonymized holdout proof, forecast/baseline comparative errors, drift/distribution tests, tenant security threat model, enterprise SKU capability parity and delivery gates, exact costs, scaling and SLO evidence, go/no-go/rollback checklist.

Astra challenge checklist: numerical reliability, leakage, uncertainty calibration, source/tenant spoofing, backtests versus time-frozen baselines, SKU-specific outcomes, enterprise entitlements, auditability, threats/PII, operational cost/latency, product utility, external integration risk and money/authority gates. Request severity-ranked technical patches and proof of reproducible tests.

Astra recommendations remain proposed. Founder reviews changes before an independent exact-byte retest; any production release, live customer onboarding, outbound, commitments and payments require their OWN explicit gates. Until then: OBSERVE.
