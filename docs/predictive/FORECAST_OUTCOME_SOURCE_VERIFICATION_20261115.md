# Predictive Revenue — forecast and outcome source verification
2026-11-15 | Existing EmpireOS Predictive Revenue owner | Read-only

The previous broad runtime observer counts operational records, not independently verified customer forecasts. The forecast-separation audit now explicitly recognises two formats: dated tenant forecast reports and the original V3 predictive registry `forecast_key / dimension_key / generated_at / predicted_value` rows. A format match is not an authenticated registry row.

The audit imports the existing `enterprise_finance_evidence_readiness.review_finance_source_readiness` to show the original financial proof gaps. It neither reads EmpireDB directly nor accepts claimant-provided "actual_verified" flags as financial evidence.

Original real source results reviewed:
- REV053 on 2026-10-18 found no *qualifying existing single event*; not a certified daily zero.
- 2026-11-15 original V4.21 finance review found three internal snapshots and **seven** independent proofs not admitted: ORIGINAL_CUSTOMER_LEDGER_CUSTODY, RECOGNISED_EVENT_ORDER_MATCH, SETTLEMENT_AND_REFUND_FINALITY, COMPLETE_DAY_CENSUS, BUYER_COMMERCIAL_AUTHORITY, FORECAST_OUTCOME_CALIBRATION, CUSTOMER_REPORT_RELEASE.
- Current `predictive_cloud/status_latest.json` reports customer forecast and frozen original registry authentication as false.
- The current `ubuntu` shell has no authorised PostgreSQL role. No privileged registry or customer-ledger read was performed. **Zero in JSON snapshots is not proof of zero database forecasts or revenue.**

Next verifiable source path: reuse `inspect_tenant_bound_predictive_registry` for a count-only trusted-tenant RLS inventory; independently verify immutable forecast existence *before* target outcomes; use existing restricted `read_recognized_revenue_event` plus a complete mature-day, settlement and refund census; then evaluate exact tenant/horizon/metric pairs with the existing V4.14 baseline and enterprise forecast scorecard. No imputed zero actuals, no training, no outbound and no customer accuracy claims until these proofs exist.

Status: source-format separation implemented, independently verified forecast/outcome calibration not yet supported by available genuine evidence.

## 15 November: speed, precision and JEV reasoning enhancement

The scanner now uses the installed ripgrep as a fast candidate-file prefilter and runs the **same** conservative forecast classifiers. The initial full original run took ~90 seconds; the updated 15 Nov live run took **7.32 seconds** (about 12x faster). It examined 132,869 nested nodes from selected runtime files. The system explicitly reports `source_prefilter=ripgrep_partial`, `fast_prefilter_failed_or_unavailable=true` and `source_scan_exhaustive=false` because permissions prevent exhaustive runtime-file coverage. Consequently, zero found forecast records **cannot prove** none exist elsewhere.

The audit reuses the original JEV Cloud observer's identity/freshness/schema/read-only contract. The currently fresh JEV research snapshot is available, with **zero model calls**. It is research evidence, not model output or financial truth. The separate `decision_support` section uses the existing EmpireOS `DecisionState` and `CandidateType` vocabulary to choose `VERIFY_EXISTING_TENANT_BOUND_FORECAST_REGISTRY` and explain the evidence gaps. It never executes the recommendation or invents confidence, actual revenue, forecast accuracy or calibration readiness.

Focused regression: **62 tests passed** covering forecast evidence separation, original JEV signal composition, Predictive Cloud/JEV observer, V4.21 forecast custody and original predictive registry. Independent customer forecast-to-outcome pairs remain zero observed; model calibration and promotion remain held.

## 15 November: authenticated source preflight, outcome benchmark gate

Implemented `empire_os/predictive_revenue_source_preflight.py`, invoked through the existing `scripts/audit_predictive_revenue_forecasts.py --authenticated-source-preflight`. It reuses the original restricted tenant-bound forecast registry inspector and restricted completed-day census reader, with no source, permission, tenant or schema changes. It exports **only sanitized statuses and bounded source counts**, not connection strings, tenant identifiers, customer rows or predictions. Simulated readers used in tests are never reported as authenticated production source sessions. A positive role-scoped read remains insufficient for immutable pre-outcome forecast custody or finalized revenue; model calibration stays held.

Source preflight on the EmpireOS host at 2026-11-15T14:43 UTC: the ordinary `ubuntu` execution session did not have an explicit canonical tenant identity, registry-reader DSN or independent census-reader DSN. The preflight returned `CANONICAL_TENANT_SCOPE_UNAVAILABLE` for each source, with no DB attempt. The audit now includes that status as **secondary evidence** and chooses `RESTORE_EXISTING_RESTRICTED_REGISTRY_READER_SESSION` rather than claiming an empty database. The authenticated session, origin custody, independent daily revenue finality, calibration cohorts and verified customer forecast-error metrics remain unproven.

The first live source-read step must run under the *already authorized* owner/DBA restricted reader sessions. Never extract secrets from running services, elevate the unprivileged CLI, disable RLS, backfill fabricated events or use caller-set tenant identity as authentication. Only then can the existing 12+ mature cohort scorecard be attempted against genuinely independent customer outcomes.
