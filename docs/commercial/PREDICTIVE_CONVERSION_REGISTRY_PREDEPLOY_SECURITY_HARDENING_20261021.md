# Original conversion forecast registry: predeployment immutability hardening
2026-10-21. Source: staged SQL and Python in existing Predictive branch. The live EmpireDB dedicated registry state remains **unverified** because remote sudo execution is blocked. No migration applied.

## Confirmed weaknesses and staged corrections
1. PostgreSQL row-level UPDATE/DELETE triggers do NOT fire on `TRUNCATE`. The prior staged append-only register blocked UPDATE and DELETE, but allowed a sufficiently privileged owner to TRUNCATE. The revised staged migration installs an additional `BEFORE TRUNCATE FOR EACH STATEMENT` guard that raises `CONV_REG_APPEND_ONLY`. This protects normal owner code paths, not superusers who can disable triggers/drop objects.
2. The original registry accepted a 64-character client SHA-256 without computing a separate DB-side digest of the JSONB payload. The revised staged `original_conversion_predictions` table has `server_payload_sha256`, computed by PostgreSQL `sha256(convert_to(p_payload::text,'UTF8'))` at registration, and checked in idempotent replay. Original reader returns both the stored SHA-256 and `server_payload_integrity_valid`, recomputed against the stored JSONB. Python `inspect_prospective_registry_readback` rejects missing, mismatched or unverified DB fingerprints.
3. Metadata-only authenticated catalogue probe now expects the new 15-column shape and both immutability triggers. A partially deployed or older schema fails closed pending DBA reconciliation; it must not auto-apply or patch DDL.

## Limits retained deliberately
- The client-submitted hash still binds only the client-side serialization claim, **not** a trusted source issuer signature or ground-truth proof. The DB-computed hash is not a digital signature; privileged administrators can still alter both data and local digests. Independent custody/replication and authenticated readback remain essential.
- These checks do not validate prediction accuracy, original evidence licences, tenant/feature temporal provenance, actual payment settlement, or that prediction was recorded *before the independent commercial outcome*. Scientific and customer-facing gates remain CLOSED.
- No independent ASTRA GPT-6 review has been executed. A model reviewing only its own code does not replace an independent external reviewer.

## Isolated tests
The disposable PostgreSQL 18 integration test, `scripts/check_original_conversion_isolated_pg_20261018.py`, creates its own Unix-socket-only test cluster under /tmp and destroys it after testing. It now checks idempotent insert, independent server digest readback/integrity, cross-tenant denial, UPDATE/DELETE/TRUNCATE guards, timestamp and tenant rejection, and concurrent writes. Production is never connected. The existing pytest module tests forged digest, missing integrity bit, client-hash disagreement and continued denial of calibration.

## Deployment decision
Do **not** apply `docs/commercial/STAGED_ORIGINAL_CONVERSION_REGISTRY_20261018.sql` yet. First obtain the authenticated production catalogue metadata result from the existing root operator; then perform DBA review of RLS, tenant resolver, table ownership, definer routines, isolated regression, rollback and recovery, and finally separate founder approval for the exact migration and subsequent gated role/credential activation.
