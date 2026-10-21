# Empire AI — Predictive Intelligence and Predictive Cloud architecture research
As of 21 October 2026. Owner: existing Predictive Revenue/Predictive Cloud worktree. This is a research and implementation contract, not a deployment or migration approval.

## Executive thesis
Build ONE revenue evidence loop: independently attributable signal -> entity and source provenance -> tenant-authenticated and point-in-time feature -> prospectively immutable model prediction -> separately gated recommendation -> approved action -> independent commercial outcome and finance settlement -> model calibration and Economic Memory. Model scores are not money, source JSON is not issuer authentication, and a deployed component is not a customer-ready forecast.

Predictive Intelligence answers **what is likely, for whom, when, under what evidence and uncertainty?**
Predictive Cloud answers **who can use it, under what tenant/policy, with what reliability and evidence, and which decision should be prepared?** Predictive Revenue answers **what was sold and actually earned?**

## Verified local baseline
- Live `runtime/predictive_intelligence/latest.json`: status `GLOBAL_SOURCE_EMPTY_BUT_ISSUER_UNVERIFIED`, 0 matched outcomes, 0 probability-ready product cohorts. The global legacy outcome RPC is quarantined by the candidate `predictive_intelligence.refresh_predictive_intelligence`.
- Predictive Cloud status v2: 28 component artifacts available, 25 fresh. `founder_directives` stale; `commercial_loop` and `astra` lack reliable timestamps. Artifact availability is not source quality.
- Cloud trend/formula materializers report `source_admission_state=UNVERIFIED_LOCAL_SNAPSHOT_ONLY`, `prediction_ready=false`; the two-minute service and local optimisation refresh are live.
- The existing tenant restricted reader authenticated in EmpireDB, with policy inventory passing for buyers, orders, outcomes and events. Its bounded original tenant-cohort read found 0 terminal candidates. Its separate directional `predictive_forecasts` audit returned `EXISTING_READER_REGISTRY_NOT_ADMITTED`, **count unknown, not 0**.
- The older `predictive_forecasts` is a directional revenue metric registry, not a conversion-probability registry. The dedicated `original_conversion_predictions` is staged-only SQL and isolated-tested, not known to be deployed or authenticated to the running tenant. Do not substitute a permission expansion on the old table.
- Python runtime inspection: NumPy, Pandas, SciPy, OR-Tools, OpenTelemetry and psycopg installed. scikit-learn, StatsForecast, MLflow, Feast, Evidently, LightGBM, XGBoost and Temporal are not confirmed installed (StatsForecast not directly checked). No paid traffic or unrestricted cloud resources.

## Predictive Intelligence — seven targeted capability lanes
### 1. Source intelligence and entity resolution
Reuse Opportunity Radar, Market GPS, source health, community intent, Buyer Scout and canonical CRM. Add one typed `signal_observation` envelope with source_ref, license/consent, observed_at, received_at, first_available_at, tenant_binding, niche, geography, entity_id, source_revision, dedupe fingerprint, confidence **about measurement only**, and admissibility/blockers. Source confidence must not become probability of purchase.
Deduplicate sources/people/organisations with deterministic keys first; record uncertain entity joins and human review. Avoid contaminating tenants or matching similar phone numbers across unrelated buyer contexts. Embed/semantic-search signals only for retrieval, not verified commercial truth.

### 2. Temporal feature intelligence
Point-in-time as-of retrieval MUST satisfy source `first_available_at <= decision_at`, not merely source event timestamp <= decision_at. Corrections/backfills received later must not appear in earlier hypothetical decisions. Keep append-only feature revisions in EmpireDB and derive tenant/niche snapshots at a frozen decision timestamp. Use TTL, missingness, source cost, rights and feature validity rules. Research analogue: Feast point-in-time joins with created timestamp filtering.
Outputs: reproducible `feature_snapshot_ref`, `model_input_sha256`, feature set version, source coverage and a counterfactual replay test.

### 3. Multi-head commercial predictions
Keep separate, versioned outcome heads:
- conversion/acceptance probability for a precisely defined buyer/lead cohort;
- time-to-contact, response and time-to-settlement with right-censoring (not false negatives when window still open);
- payable call qualification, duplicate/exclusion eligibility and buyer capacity rules;
- revenue and gross contribution conditional on verified buyer terms and real costs;
- long-range demand/territory trend (aggregate scenario, not lead-specific propensity);
- repeat purchase, subscriber churn and customer value when genuine longitudinal history exists.
Start with Beta-binomial cohort baseline already in `predictive_intelligence.build_product_estimate`; add logistic or gradient-boosted conditional forecasts only after enough authenticated, prospective labels exist. Use hierarchical/partial-pooling only with explicit cross-tenant consent and governance.

### 4. Uncertainty and abstention
Return calibrated probability or distribution, outcome definition, horizon, interval and OOD/coverage flags. Abstain when missing original issuer, registry, cohort, buyer rules, settlement, model validation or source timestamp. Do not transform LLM opinions, rank, SERP volume or a trust score into 90% conversion probability. Model metrics must distinguish small-sample uncertainty from actual accuracy; prediction intervals need verified residuals/coverage.

### 5. Scientific measurement
Reuse `predictive_calibration`, `predictive_product_scientific_holdout`, `lead_shadow_calibration_benchmark`, Economic Memory and Scientific Agent. Need original DB-generated prediction recorded_at and independently authenticated readback, followed by outcome timestamp and original customer/payment proof. Use chronological/rolling-origin holdouts, probability reliability, Brier/log loss, baseline lift, per-niche and geography slices, uncertainty coverage and drift. Existing 20-history/12-evaluation minima are **harness minimums**, never automatic commercial accuracy proof. Prevent survivorship leakage and outcome maturation bias.

### 6. Decision intelligence and uplift
Reuse `predictive_decision_control`, `optimization_status` and installed OR-Tools. Optimise payable gross contribution under explicit capacity, geographic buyer terms, allowed contact, suppression, budget and fulfilment constraints. An accurate prediction of conversion does **not** show an action causes incremental revenue. Reserve uplift/causal inference for measured treatment/control interventions, not observational correlation. Present `recommendation`, explanation/evidence, estimated EV, alternative and human-approved action; never auto-dispatch because a score rose.

### 7. Economic feedback
Use a stable `forecast_ref -> decision_ref -> action_ref -> order/fulfilment/outcome_ref -> finance_evidence_ref` chain. Independently verify accepted payment/settlement/refunds/costs before `realized_revenue` or model training. Keep negative and unresolved outcomes distinct. System may learn from deterministic decision-policy diagnostics before financial validation, but not treat these as real customer labels.

## Predictive Cloud — seven targeted capability lanes
### 1. Separated planes without new infrastructure
CONTROL PLANE: tenancy, entitlements, approval gates, model versions, quotas, audits, policy. DATA/EVIDENCE PLANE: canonical EmpireDB, FORCE RLS, tenant-scoped immutable original evidence and bounded readers. COMPUTE PLANE: tested immutable releases, two-minute status/materializer, inference/science jobs, CPU-first optimisation. SERVING PLANE: loopback Founder API plus authenticated tenant APIs when authorised. BUSINESS PLANE: existing CRM, buyer and finance owners. Keep actual service identities independent and least-privilege.

### 2. Three health grades rather than one
`runtime_operational`: processes up and fresh.
`scientifically_validated`: original prospective registry/outcome calibration and uncertainty passed.
`commercially_enabled`: terms, entitlements, fulfillment, payments, approvals and consumer availability passed.
Dashboard must show separate badges/unknowns, never infer commercial readiness from 28/28 available artifacts or 25/28 fresh.

### 3. Durable evidence and job custody
Keep original issue receipt, readback, source revision, model version and validation score as auditable append-only records. Jobs need idempotency, retry budget, dead-letter/held diagnostics, heartbeat, cancellation and immutable job-contract hashes. The existing systemd job/timer is adequate for current workload; introduce Temporal or message infrastructure only after measured multi-step recovery/volume needs justify it.

### 4. Multi-tenant performance isolation
Enforce DB tenant from authenticated session, not payload fields; FORCE RLS and default deny; read/write separate capability roles; entitlement per product and API. Add per-tenant fair queues, concurrency, quotas, resource budgets, audit logs and cross-tenant negative test harnesses. At scale use deployment stamps/isolated workers for enterprise customers; don't replicate the whole platform now.

### 5. Model serving and confidence policy
Offer `/forecast` only for authenticated eligible tenant+model+cohort; output immutable forecast_ref, frozen issued_at, model_revision, horizon, uncertainty, source coverage, reason for abstention. Founder preview can display research scenarios as visibly **research** and no predictions if source lacks science. Define pre-registered champion/challenger test and rollback; compare predictions before changing production model aliases.

### 6. Observability, resilience and cost
Reuse installed OpenTelemetry and `otel_telemetry.py` / `telemetry.py`. Traces: source_read, tenant_admission, feature_snapshot, original_forecast_write/readback, inference, decision, approved_action, outcome_verified, settlement_verified, feedback. Redact tenant, phone, buyer PII and protected evidence from traces. Track API 5xx/latency, source freshness, issuance-to-verification delay, registry readback failures, delayed outcomes, quota, duplicate actions, backup recovery and per-tenant CPU/AI compute cost. Define end-to-end SLOs beyond service uptime.

### 7. Trusted economics of Cloud formula
`predictive_cloud_formula.py` computes portfolio ERV * geometric mean of trust factors * (1-residual_uncertainty). Preserve as a **heuristic decision score** only, not an automatically calibrated expected-revenue or accounting statement. It assumes the factors are bounded, meaningful and comparable. Correlated factors can double count quality or uncertainty; a high score can be unjustified without actual held-out realized outcomes. Backtest separately and measure empirical calibration before describing `cloud_adjusted_value` as dollar-value forecast. Keep formula gates fail-closed.

## Decisions and open-source options
**REUSE NOW:** EmpireDB, local immutable release+harness, installed OR-Tools, NumPy/SciPy/Pandas, OTel, existing Scientific Agent, Economic Memory and Founder API. PostgreSQL can cover event and historical feature storage at this stage.
**OPTIONAL WHEN EVIDENCED:** scikit-learn probability calibration; StatsForecast rolling-origin time series; MAPIE interval calibration; Evidently drift reports; MLflow experiment lineage; Feast if online/offline feature consistency becomes operationally hard; pgvector for tenant-isolated semantic *retrieval*, not financial proof; Temporal for durable multistep orchestration. Verify license, versions and memory before installation.
**DEFER:** Kubernetes, Kafka/Flink, independent feature-store servers, GPU model zoo, cross-tenant data pooling and external paid cloud providers until verified product traction/loads justify them.

## Phased build, source owners and acceptance gates
P0 Intelligence custody: verify exact live identity/grants for dedicated original conversion registry without changing DB; implement an audited prospectively append-only registry only after separately approved DBA migration; independently verify actual tenant outcome and finance events. Acceptance: genuinely original forecast created before a later verified outcome, read back via separate role, no tenant leakage.
P0 Cloud truth: preserve the live guarded Cloud materializer and Founder API; repair `founder_directives` stale and `commercial_loop`/`astra` timestamp gaps with original producer receipts, not a fabricated refresh time. Acceptance: real source-owned observation timestamps and no premature science/customer claims.
P1 Temporal feature layer: build append-only feature snapshots and historical as-of retrieval; replay and leakage harness. Acceptance: new backfilled event cannot alter prior forecast features.
P1 Scientific baseline: strict tenant+niche cohort definition, no false negatives from open cases, real chronological holdout, Brier/calibration/baseline comparisons. Acceptance: only authenticated matches produce metrics and all deficient cohorts remain held.
P1 Decision economics: attach existing Buyer Scout/CRM/call/finance evidence to OR-Tools portfolio recommendation, without commercial execution. Acceptance: source-supported constraints, reproducible optimiser, no duplicate/suppressed action.
P2 SaaS control plane: entitlements, per-tenant quotas, jobs and billing evidence, model revisions, observability and recovery SLOs. Acceptance: negative cross-tenant tests, quota tests, failure injection, rollback and immutable releases.
P2 Optional platforms only after measured bottlenecks.

## Critical anti-drift decision
Never redefine three differently scoped products as one model:
- Predictive Intelligence: probability / trends / timing / outcome-risk from evidence.
- Predictive Cloud: tenant-safe orchestration, service, traceability, experimentation, governance.
- Predictive Revenue: actual commercial lifecycle and recognized economic outcomes.
The pipeline is proven only when the three meet on *genuine pre-outcome forecast receipts and independently verified customer economics*.

## External references consulted 21 October 2026
- Feast point-in-time + creation-time filtering: https://github.com/feast-dev/feast/blob/master/docs/getting-started/concepts/point-in-time-joins.md
- scikit-learn probability calibration: https://scikit-learn.org/stable/api/sklearn.calibration.html
- StatsForecast rolling-window cross-validation: https://nixtla.github.io/statsforecast/docs/tutorials/crossvalidation.html
- MAPIE intervals and exchangeability: https://mapie.readthedocs.io/en/stable/
- Google MLOps training-serving skew and monitoring: https://docs.cloud.google.com/architecture/guidelines-for-developing-high-quality-ml-solutions
- PostgreSQL RLS: https://www.postgresql.org/docs/17/ddl-rowsecurity.html
- MLflow model lineage: https://www.mlflow.org/docs/latest/registry/
- Azure SaaS multitenancy and deployment stamps: https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/approaches/overview
- OpenTelemetry Python: https://opentelemetry.io/docs/languages/python/
- OpenLineage dataset/run events: https://openlineage.io/apidocs/openapi/
- Temporal durable workflow semantics: https://docs.temporal.io/workflows
- pgvector multi-tenant vector search caveats: https://github.com/pgvector/pgvector
- Google SRE end-to-end SLO guidance: https://sre.google/resources/practices-and-processes/product-focused-reliability-for-sre/
