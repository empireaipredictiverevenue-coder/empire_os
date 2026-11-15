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

## 15 November: authoritative original database catalogue verification

The existing `predictive_revenue_forecast_origin.py` confirms that the old `predictive_forecasts` table definition was found in the Supabase migration tree, not verified in first-party EmpireDB. The existing REV052 proof authenticates **only the single-event read function and dedicated role**; it does not certify the registry table, FORCE RLS, registry reader role, or completed-day census function.

The smallest source-owner action is now implemented as `scripts/probe_predictive_original_source_catalog_readonly.py --read-only`: a root-only, single transaction `BEGIN READ ONLY` query through the *original existing* `pg()` Postgres peer helper. It outputs only schema-fixed booleans indicating presence and policy of the exact registry and day-census objects, plus prior single-event capability. It executes no DDL, SELECT from revenue tables, finance report, role change, restart, or customer read. Non-root sessions return `EXPLICIT_ROOT_READ_ONLY_SESSION_REQUIRED` without attempting the DB.

Founder/DBA operator command on the original host, **only in an authorised root-capable SSH session**, if desired:

```sh
cd /srv/empire_os
sudo timeout --signal=INT --kill-after=5s 30s \
  /srv/empire_os/.venv/bin/python -B -m scripts.probe_predictive_original_source_catalog_readonly --read-only
printf 'EXIT_CODE=%s\\n' "$?"
```

Do not enter or print credentials. Review boolean results: if either `forecast_registry_table_exists`, `forecast_registry_force_rls`, `forecast_registry_reader_role_safe` or `restricted_day_census_function_exists` is false, there is **no authenticated source pair to calibrate from**; source ownership must determine the original deployed architecture and approve any restoration separately. Even if all catalogue fields pass, forecast timestamps, tenant read, actual outcome completeness, independent financial finality and baseline out-of-sample score remain unverified. No migration or source entitlement changes are authorized by this probe.

## 15 November: EmpireDB-native forecast registry replacement (held)

The founder's 2026-11-15 root read-only catalogue probe definitively showed `public.predictive_forecasts` absent, forecast-reader role absent, FORCE RLS absent for that table, and the daily-census function absent on **canonical EmpireDB**. The existing REV052 single-event reader and tenant identity resolver were present.

A **new and independent** EmpireDB-only PostgreSQL 18 registry migration now exists at `migrations/empiredb/076_predictive_forecast_registry_native_held.sql`. It intentionally does not import or run old `supabase/migrations` files or grant vendor `anon`, `authenticated` or `service_role` privileges. It uses the first-party `empire_current_tenant_id()` trusted session-user resolver, a NOLOGIN/NOINHERIT/NOBYPASSRLS reader role, select-only RLS with FORCE RLS, and an initially unwritable registry. It creates no login, tenant bindings, forecast data, writer RPC, source-day census or commercial entitlement; it cannot manufacture historical calibration examples. It is **NOT approved for production apply**.

The disposable-PostgreSQL-18 fixture `scripts/test_empiredb_rev076_ephemeral_20261115.sh` executed the exact proposed DDL in an isolated Unix-socket-only cluster and verified a scoped forecast is visible to each matching tenant, unavailable to an unbound tenant, denied deletion through the restricted reader, and FORCE RLS enabled. Test fixture data are explicitly synthetic and never imported into EmpireDB. The very first fixture run lacked schema-CREATE privilege for its simulated migrator; this was corrected in the fixture, not by weakening the production proposed migration. The subsequent isolated execution passed.

**Remaining native EmpireDB work:** Independently review and authorise the new schema under the original DBA release gate; design a strictly future-facing append-only writer with trusted DB timestamps and origin proof; implement and independently validate the missing tenant-bound daily actuals census against canonical commercial events/orders, including refunds and financial finality; register only genuinely original forecasts; then benchmark mature forecast/outcome pairs using the existing enterprise scorecard and baseline. No DDL was applied to live EmpireDB and accuracy is not measurable yet.

REV076 follow-up test strengthened: a required EmpireDB migrator `CREATE` privilege is checked explicitly before DDL; attempting the same proposed migration twice fails closed in the disposable PostgreSQL 18 cluster. Tenant isolation, default-deny unbound tenants, restricted write denial and FORCE RLS continue to pass. Production status remains HELD / NOT APPLIED.

## 15 November — native EmpireDB daily revenue source census (REV077 HELD)

The existing Wave-35 Python source reader had no installed EmpireDB stored function. New founder/DBA-**held** `migrations/empiredb/077_predictive_daily_revenue_census_native_held.sql` defines only `public.read_predictive_revenue_day_v1(date,text)` owned by the existing `empiredb_migrator`, granted exclusively to the existing REV051 NOLOGIN evidence-reader role. It uses the original trusted `session_user` tenant resolver, never a caller-provided GUC as proof, and performs a single read-only, bounded UTC-day source census against the canonical EmpireDB commercial-events, fulfilment-orders and buyers ledger. It performs no inserts, updates, deletes, payments, recognition, role grants to logins, customer publication or legacy Supabase calls.

For each completed UTC day, counts include every `revenue_recognized` event in the original ledger; invalid/orphaned global records are included as **invalid** rather than silently excluded. A candidate tenant event must match the order, buyer, product, amount, settlement-state metadata, and non-empty causal lineage, with trusted tenant binding. A missing or invalid global event makes the whole source-day candidate fail closed. A drift check rejects later changes that could silently restrict the definer's global source visibility (source owner/FORCE RLS). Results follow the **existing** eight-column `predictive_revenue_daily_census.py` reader contract; they are **source candidates, never financially finalized daily actuals**. Independent bank settlement, refunds, chargebacks, backfill completeness, currency conversion and customer delivery remain unverified.

The disposable PostgreSQL 18 proof `scripts/test_empiredb_rev077_ephemeral_20261115.sh` tests the exact proposed DDL and then calls the original Python reader through authenticated synthetic per-tenant database sessions; two tenants receive only their own candidate amounts; unknown tenant and cross-tenant requests fail, direct ledger SELECT is denied, orphan events block all calibration, a clean day yields only an internal source candidate, duplicate migration fails, and later FORCE RLS source-policy drift is denied. No synthetic fixture data ever enters the original EmpireDB.

The integration test exposed an existing reader timing bug: the DB's fresh snapshot timestamp is a few milliseconds later than the caller's `as_of`, so valid live results were rejected. The original integrated reader is preserved with a small correction to validate source snapshot timestamps against observed **read completion**, while its direct validator continues to reject future snapshots. Added direct regressions for valid and invalid chronology, incomplete sources and financial-claim abstention. **80 focused Python tests passed** and the real PostgreSQL 18 fixture passed. SQL migration is installed as a **held source file only**, not applied to production EmpireDB. DBA review, backup and release gates are unchanged.

Next decision is the original DBA/founder-reviewed REV076 + REV077 production release, followed by future-only independently timestamped forecast writes and independently finalized customer-outcome admission. No accepted original forecast–actual cohort, calibration score or customer sale can be inferred from this change.
