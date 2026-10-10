# TAM restricted-reader production conflict — 10 October 2026

**Status: OBSERVE / DATABASE MIGRATION HELD / NO CREDENTIAL MUTATIONS.**

## Verified runtime outcome

On **2026-10-10T13:16:15Z**, the existing `empire-market-gps.service` executed with its own protected systemd credential and wrote owner-private evidence at `runtime/market_sweeps/tam_reader_capability_latest.json`.

Evidence readback:

- `restricted_login_verified: true`
- `capability_role_verified: true`
- `source_tables_present: true`
- `function_exists: false`
- `capability_execute_verified: false`
- `source_table_direct_read_grants: true` (field name historical; PostgreSQL `has_table_privilege()` proves **effective** privileges rather than the origin of each grant)
- `migration_028_contract_verified: false`
- `status: RESTRICTED_CATALOG_CONTRACT_INCOMPLETE`

The functioning Market GPS snapshot was generated successfully in that same run. **No** TAM market record read, migration, grant, credential change or outbound occurred.

## Exact reason migration 028 is incompatible with the current reader

The production-tracked bootstrap `deploy/empiredb/intelligence_materializer.sql` grants the long-standing `empire_intelligence_materializer` role **SELECT** on `public.prospect_entity_links` and `public.business_entities` because that role serves other live intelligence consumers.

The held `migrations/empiredb/028_tam_country_evidence_restricted_reader.sql` uses the **same role** and deliberately fails if that role has ANY SELECT/INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER privilege on either table. Its role guard prevents a privileged materializer from being repurposed as the isolated TAM market reader.

This conflict is reproduced by `test_held_migration_028_rejects_existing_market_gps_materializer_selects` in a **disposable PostgreSQL cluster**. The production database was not altered by that test.

**Do not** simply run migration 028, revoke the materializer's table grants, relax the migration guard or reinterpret the old role as a least-privilege TAM role. These approaches could break Market GPS, entity resolution and other live services, or violate the intended isolation boundary.

## Recommended single corrective release — founder approval required before writes

Retain the old Market GPS/materializer entirely unchanged. Replace the **held** TAM activation design with an isolated TAM capability:

1. **Separate DB identity.** Prepare a non-login capability role, e.g. `empire_tam_market_reader`, and a separate non-superuser `empire_tam_market_login` with no inherited general-purpose intelligence privileges. Ensure neither is a member of `empire_intelligence_materializer`, `empiredb_migrator`, `empiredb_app` or any outbound/payment role. Verify effective permissions (including any PUBLIC/column grants) on acquisition, identity and company tables are NONE.
2. **Bounded function.** Deploy the existing migration 028 source-row selection logic under a SECURITY DEFINER STABLE `public.get_tam_market_observations(integer)` function owned by the verified non-login `empiredb_migrator`, with empty search path, explicit source references, hard 1–5000 row limit and read-only result. Only the *new TAM capability role* receives EXECUTE. Revoke from PUBLIC, the old materializer/login, `empiredb_app` and ordinary roles. Verify no source-table direct permissions on the new TAM capability.
3. **Separate secret.** Provision a dedicated owner-private systemd `LoadCredential` for `empire_tam_market_login`. **Do not** copy or reuse the working `market-gps.dsn`, expose it in logs/process arguments or store it in the repository. The current `EMPIRE_INTELLIGENCE_MATERIALIZER_DSN` binding in `empire_os/tam_market_runtime.py` must then be adapted to the explicitly named restricted TAM credential.
4. **No duplicate schedulers.** Run a bounded on-demand TAM preflight / snapshot under the authorised protected execution context. Reuse the existing Revenue Completion Supervisor and Opportunity Radar; no additional recurring loop/agent is needed.
5. **Activation proof, strictly ordered.** Existing role/grant readback and backups → founder-specific DDL approval → disposable PG contract tests → scoped migration and post-migration catalog readback → known market-scope parameters → first bounded data-read test → true `0600` snapshot → Radar evidence admission as research only → validate Market GPS regression on the unchanged old identity.
6. **Rollback.** Revoke EXECUTE on the new function/role, disable the new TAM read context, remove only the newly introduced IAM/DB grants/credential according to the approved rollback runbook. Do not revoke/change legacy materializer permissions or delete company evidence.

**Important:** this is **a design proposal, not a released SQL migration**. No DDL or login credential provisioning is authorised by this document. Founder's approval must specify both (a) creation of a separate TAM-only role/login/function and (b) dedicated credential provisioning, with guarded backup and rollback. Actual execution requires production DBA verification and exact DB-schema compatibility first.

## Existing verified engineering work

- **Repo:** `empire_os/revenue_completion_supervisor.py` now reports both specific failure codes `TAM_RESTRICTED_RPC_MISSING` and `MATERIALIZER_HAS_EFFECTIVE_SOURCE_TABLE_PRIVILEGES`, with next task `DESIGN_ISOLATED_TAM_CAPABILITY_AND_SEEK_SEPARATE_FOUNDER_APPROVAL`.
- **No false positive:** `tam_market_intelligence/latest.json` remains absent and `tam_runtime.available` remains false. No verified TAM population, buyer intent, executed campaign, payments or revenue have been inferred.
- **Tests:** `tests/test_empiredb_tam_country_evidence_restricted_reader.py` reproduces the incompatible held migration with production-like grants in ephemeral PostgreSQL. Passive catalog regression asserts evidence scope and no mutation authority.

## Commercial next action

TAM is a research input, not an earning stream itself. Keep the other **14** commercial streams and the working **Market GPS** research active while the isolated TAM reader is prepared. Revenue work should continue on real warm buyers, search products and insurance/carrier qualification independently of the held migration.
