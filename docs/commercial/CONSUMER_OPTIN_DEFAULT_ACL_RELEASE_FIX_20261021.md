# Consumer opt-in: exact-table ACL inheritance release correction

**Date:** 2026-10-21
**Status:** isolated PostgreSQL fixture and unit tests PASS; revised production release **NOT AUTHORISED OR APPLIED**.

## Original failed production attempt

Founder ran the previously explicitly approved guarded schema installation. Backup metadata was healthy (newest completed backup 16.2 hours old, two completed, one healthy stanza) and `--read-only` preflight showed `empiredb_migrator=true`, `consumer_writer=false`, `consumer_table_count=0`.

The exact approved installer then returned:
```json
{"status":"CONSUMER_INSTALL_HELD","reason":"COMPANY_CRM_READ_ACCESS_DETECTED","database_mutation_completed":false}
```
The installer transaction rolls back on this failed postcondition. No committed application was reported. The absence of the role/table should still be rechecked in production before another apply.

## Why it failed

An established EmpireDB migration fixture (`scripts/test_empiredb_direct_bsc_capability_acl_048_ephemeral.sh`) intentionally models **existing per-schema default privileges for `empiredb_migrator`**, granting `empiredb_app` SELECT/INSERT/UPDATE/DELETE and `empiredb_readonly` SELECT whenever that migrator creates a table in `public`. Its separate 048 ACL-sealing migration preserved global defaults and revoked only an individual protected object.

Those defaults provide a strong evidence-based explanation for the consumer installer hold; **the exact current live default ACL must still be confirmed with the revised read-only preflight**. Do not infer actual production role membership or grant origins beyond the evidence.

## Surgical corrective release

- `migrations/empiredb/059_consumer_optin_default_acl_seal_20261021.sql`: after consumer 057 creates its five RLS-sealed tables, but **before** consumer 058 grants the dedicated writer, inspect the freshly created table ACLs and revoke from `PUBLIC`, `empiredb_app` and `empiredb_readonly` **on those exact five tables only**. Require the documented grant types without grant options; unknown grants, role membership, an unexpected owner or missing RLS cause a HOLD and rollback.
- No `ALTER DEFAULT PRIVILEGES`. No global ACL change, change to existing tables, broad membership grants, outward/email authority, nor production customer import.
- `scripts/guarded_install_consumer_schema_20261021.py`: 057 → 059 → 058 under **one outer transaction** with a post-installation access check. Read-only output includes current migrator default-table ACL metadata. A failing guard rolls the whole schema and role back.
- The approval fingerprint now also binds the **installer's executable source bytes** in addition to the roles and the three migrations.

**Replacement release SHA-256:**
`fe9da8e0a8871e78103941729fb893c891a542286531a283e0d40f2846026cd1`

**New checksum-verified operator bundle:**
`/var/tmp/empire-consumer-db-20261021.TyGac614`

**Old release SHA-256 `2fa878eb0d93d011dc55b1cba0e9c37b58603944b9c99abb4959a1238b80de0c` is SUPERSEDED. Do not rerun the old bundle. The original approval cannot authorise modified SQL or installer code.**

## QA evidence

Three independent disposable PostgreSQL 18 fixtures passed:

1. Existing default grants: app SELECT/INSERT/UPDATE/DELETE and readonly SELECT as documented; the corrected installer committed all five tables, five restricted policies and NOLOGIN writer, with neither app nor PUBLIC SELECT/INSERT.
2. Pre-existing unsafe LOGIN writer: hold and **zero new tables**.
3. Unexpected third-party default-ACL role: hold `CONSUMER059_UNEXPECTED_DEFAULT_TABLE_ACL`, **zero new tables and no writer role**.

A full selected regression of **136 tests passed**, one existing third-party deprecation warning.

## Next owner action (new approval required)

The owner should first review the new digest and the `--read-only` preflight (which now lists sanitized migrator default ACLs), then explicitly authorise the replacement production install if it shows only the documented permitted defaults and no unexpected role membership. The run must recheck privileged backup metadata freshness. The guarded installer must be run as the PostgreSQL OS operator in the exact staged bundle, never run from the worktree inaccessible to that account.

**Even after eventual successful DB install, the private login, encryption key custody, real email verification/withdrawal, legal privacy notice and exact website release are still separate holds.** No real subscriber capture, consumer data sale, payment or outbound follows from this schema installation.
