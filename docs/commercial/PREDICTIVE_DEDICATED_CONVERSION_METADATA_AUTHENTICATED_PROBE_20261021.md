# Dedicated original-conversion registry — authenticated production catalogue probe

Date: 2026-10-21. Owner: existing Predictive Decision Control branch. Source of truth: canonical EmpireDB PostgreSQL. This is **not** a migration, admission of forecast records, training activation, product launch or price change.

## Problem
The prior `empire-predictive-founder-reader both` verified the existing restricted tenant reader can inspect source-order/outcome policy and found no authenticated terminal cohort candidates. The separate `run_guarded_predictive_registry_readonly_20261021.sh` returned `EXISTING_READER_REGISTRY_NOT_ADMITTED` for **`public.predictive_forecasts`**, a distinct directional revenue forecast registry. That denial and a null record count cannot establish whether the **dedicated** conversion-probability registry exists. Do not solve it by adding the directional table SELECT grant.

The dedicated `public.original_conversion_predictions` migration and its writer/readback functions are staged in `docs/commercial/STAGED_ORIGINAL_CONVERSION_REGISTRY_20261018.sql`. The migration has NOT been applied by this work and its production state cannot be inferred from source code alone.

## New probe
`empire_os/predictive_original_conversion_catalogue.py` uses the **existing original authenticated `empire_verified_order_tenant_login`** and narrow `empiredb_tenant_reader` role, first setting transaction READ ONLY and checking canonical tenant identity and role authority. It then runs only catalogue SELECTs (`pg_class`, `pg_roles`, `pg_proc`, `pg_attribute`, `pg_policies`, `pg_trigger`, and `to_regclass/to_regprocedure`) to inspect:
- Dedicated table and exact declared writer, reader and immutable trigger-function names.
- Dedicated NOLOGIN/NOBYPASSRLS role presence and unexpected login membership (no new grants).
- Force-RLS/table permissions.
- Exact source-described 15 columns, tenant-scoped read/insert policy metadata, function volatility/SECURITY DEFINER shape and both original UPDATE/DELETE and TRUNCATE guard triggers.

Metadata matching is only a candidate for further DBA review. It cannot prove trigger code correctness, original transactions, source tenant isolation, immutable registration, recorded-before-outcome chronology, actual receipts or customer readiness.

Results are privacy-safe and do not expose tenant IDs, original forecast rows, original opportunity keys, secrets, customer values, database error details or role credentials:
- `DEDICATED_ORIGINAL_CONVERSION_REGISTRY_NOT_INSTALLED` only after successful original authenticated catalogue read where all expected registry objects and capability roles are missing.
- `DEDICATED_CONVERSION_PARTIAL_OR_SECURITY_DRIFT_HOLD` on any inconsistent/missing/extra object or security metadata.
- `DEDICATED_CONVERSION_OBJECTS_PRESENT_REVIEW_REQUIRED` when the expected object **metadata** is observed and the security shape passes, without granting access or scientific admission.
- `DEDICATED_CONVERSION_CATALOGUE_AUTHENTICATION_HELD` when the original restricted credential or catalogue authority is unavailable. This must not be reinterpreted as an empty or absent registry.

## Immutable privileged-custody wrapper
`scripts/run_guarded_conversion_catalogue_readonly_20261021.sh --check FULL_GIT_SHA` performs code and file availability preflight only. The `--run-read-only` form must be executed by the existing privileged root operator, checks the exact SHA-256 file inventory from the pinned Git commit, installs only four required Python files in a root-owned non-group-writable immutable `/opt/empire/original_conversion_catalogue_<SHA>` directory, and reads the already-existing protected `/etc/empire/verified-order-reader/reader.pgpass` credential without printing it. The source is executed through `python -P -B` in a clean environment. No historical root operator install, Cloud service, DB role, grants, RLS, finance or customer forecast settings change.

Do not use the routine ASTRA dispatcher, API keys, production migrations, or a new tenant membership to run this. Its job is to identify the *actual* existing production installation state, not deploy the staged migration.

## Next gate
If the authenticated read confirms the original registry is absent: separately inspect the staged migration's tenant resolver and SECURITY DEFINER/trigger security model, perform isolation tests and rollback plan, then obtain specific founder/DBA authorization before any live schema or credential work. If objects are present or partially present: independently review exact schema function definitions, owner permissions, RLS behavior and source recordings; do not auto-issue or ingest customer predictions. At every stage the original commercial-outcome cohort remains unverified until independent source and financial receipts are admitted.
