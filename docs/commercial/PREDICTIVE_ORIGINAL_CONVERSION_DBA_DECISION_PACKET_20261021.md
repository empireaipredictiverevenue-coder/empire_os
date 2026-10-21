# Empire AI Predictive Revenue — dedicated conversion registry DBA decision packet

Date: 21 October 2026. Scope: canonical **EmpireDB PostgreSQL**, not Supabase. Owner: existing Predictive Decision Control branch. **No production DDL has been executed. No customer forecasting, training, payment or outbound activation is authorised.**

## 1. Production finding — explicit owner operator receipt

The founder ran the root-owned, SHA-pinned `run_guarded_conversion_catalogue_readonly_20261021.sh` against the existing restricted tenant reader at source commit `313f56709381b554f8a025d14cf51c4b77bb628c`.

Its output showed `authenticated_tenant_session=true`, `transaction_read_only_verified=true`, `catalogue_metadata_completeness_verified=true`, `status=DEDICATED_ORIGINAL_CONVERSION_REGISTRY_NOT_INSTALLED`, all four dedicated `object_presence` fields false, `expected_dedicated_roles_present=0`, `original_conversion_rows_queried=false`, `database_writes=false`, `execution_authority=none`.

**This is owner-supplied authenticated operator stdout, not a signed log fetched by the engineering shell**. Recheck immediately before any approved migration. It proves dedicated registry absence at the time checked, not lifetime absence of forecasts from other unrelated historical registries. Never substitute the old `predictive_forecasts` table, whose scoped reader had previously returned `EXISTING_READER_REGISTRY_NOT_ADMITTED`.

## 2. Exact staged release candidate

- SQL source: `docs/commercial/STAGED_ORIGINAL_CONVERSION_REGISTRY_20261018.sql` (staged ONLY; never automatically applied).
- Python request/readback: `empire_os/original_conversion_registry.py` and `empire_os/original_conversion_registry_transport.py`; transport default `enabled=False`.
- Metadata probe: `empire_os/predictive_original_conversion_catalogue.py` and root-owned check wrapper `scripts/run_guarded_conversion_catalogue_readonly_20261021.sh`.
- Disposable PG18 tests: `scripts/check_original_conversion_isolated_pg_20261018.py`.
- Immutable source-review packet: `scripts/review_original_conversion_release_candidate_20261021.py --read-only --commit FULL_SHA`. It reads only SHA-pinned repository files, checks exact source digests and critical security conditions, and outputs `DBA_REVIEW_CANDIDATE_NOT_AUTHORIZED_TO_DEPLOY`. It **does not** run migrations, read source DB or independently attest backups.

### Tested security upgrades
- Tenant identity bound to PostgreSQL `session_user` via existing `empire_current_tenant_id()`; SQL preflight verifies restricted migrator role and the tenant resolver's stable SECURITY DEFINER owner shape. A changed role binding fails closed.
- Dedicated NOLOGIN/NOBYPASSRLS writer and reader capability roles, **no membership grants or credentials**. FORCE RLS; deny runtime direct SELECT/INSERT/UPDATE/DELETE on table.
- `record_original_conversion_prediction_v1(text,text,text,text)` now receives the exact raw UTF-8 JSON text used by the client and checks `sha256(convert_to(p_payload_text,'UTF8'))` equals the client-submitted SHA before decoding to JSONB. Forged 64-hex client digests and oversized input are rejected by PostgreSQL.
- Independently computed `server_payload_sha256` on PostgreSQL JSONB, readback recomputes the stored digest; Python fails closed on missing/mismatched digest or verification bit.
- Immutable-row UPDATE/DELETE trigger **and a separate TRUNCATE trigger**. Stable prediction identity and ON CONFLICT idempotency, prospective timestamp bounds, cross-tenant rejection and concurrent submission pass isolated PG tests.
- Database-local digest and triggers **do not prove independent custody** against a privileged admin or source issuer integrity; independently held receipts, backups and financial evidence remain necessary.

## 3. Mandatory release gates **before explicit founder approval**

1. DBA independently confirms the current EmpireDB tenant resolver implementation and owner, migrator role attributes, public function grants, runtime-role membership boundaries, `SECURITY DEFINER` search path, table ownership, and absence of conflicting dedicated objects. Source-script checks alone are insufficient.
2. Obtain an original, recent recoverable pgBackRest backup/archive and tested restore/PITR evidence for **this specific** migration's rollback window. Do not rely only on old health snapshots.
3. Re-run the isolated PostgreSQL integration and full regressions against the exact commit and record test receipts and hashes. Run `--read-only --commit FULL_SHA` before staging; reject dirty source/version drift.
4. Validate migration's transactional DDL on a production-like disposable copy with realistic schema roles and tenant resolver, resource budgets and lock impact. Ensure migrations are not wired to auto-run.
5. Human review of user-facing privacy/data retention, forecast provenance, tenant isolation, lifecycle evidence custody, incident response and fulfilment/settlement data dependencies.
6. Seek separate explicit founder approval **for the exact commit/hash and only the dedicated registry schema/NOLOGIN roles**, not writer role membership, new credentials, customer forecasts, live outbound, money movement, scientific training or automatic commercial pricing.
7. After any separately approved DDL, rerun the existing read-only catalogue probe, inspect the table/roles/policies/trigger/function definitions independently, and confirm forecast row access stays disabled and tenant-secure. Only then consider later, distinct approvals for tenant-bound writer/reader login and first controlled forecasting experiment.

## 4. Rollback policy

- Before COMMIT: staged migration is a PostgreSQL transaction; failure should abort without persistent DDL. Confirm rollback state and object absence using authenticated metadata read.
- After COMMIT: **do not drop the registry or original evidence** as an automatic rollback. If access was separately enabled later, revoke only explicitly approved runtime capability memberships through a DBA-controlled transaction; preserve original immutable forecasts and settlement/evidence records for audit. Check backup/PITR and initiate a specific incident change request for any destructive schema reversal.
- Existing Cloud materializer, Founder API, comparison CLI and existing CRM/order readers remain unchanged throughout.

## 5. Honest exit status

The code can reach **staged candidate for DBA review** only. Live forecast issuance and scientific calibration are BLOCKED: original registry not installed as observed, protected production DDL action not approved, independent outcome/settlement receipts absent, ASTRA GPT-6 review not independently executed. No customer revenue is claimed.
